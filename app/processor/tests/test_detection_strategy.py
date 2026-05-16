import unittest
import sys
import os
import cv2
import numpy as np
import logging
import types
from unittest.mock import MagicMock, patch

# Ensure project root is in path to import app modules
current_dir = os.path.dirname(os.path.abspath(__file__))
# app/processor/tests -> app/processor/src
src_path = os.path.abspath(os.path.join(current_dir, "../src"))
sys.path.insert(0, current_dir)
import heavy_skip  # noqa: E402

sys.path.append(src_path)

# Реальный ultralytics в Docker/CI — не подменять до импорта, иначе интеграционные тесты YOLO скипаются.
try:
    import ultralytics as _ultralytics_real  # noqa: F401

    _ULTRALYTICS_STUB = False
except ImportError:
    _ULTRALYTICS_STUB = True
    _ultra = types.ModuleType("ultralytics")

    class _StubYOLO:
        def __init__(self, *args, **kwargs):
            raise RuntimeError("ultralytics.YOLO stub should not be instantiated in this test")

    _ultra.YOLO = _StubYOLO
    sys.modules["ultralytics"] = _ultra

try:
    from detection_strategy import (
        TwoStageStrategy,
        _regional_class_ids,
        binary_track_ultralytics_conf_floor,
        bird_skip_classifier_area_limit,
        build_binary_track_ultralytics_extras,
        openvino_binary_bird_score_scale,
        per_label_binary_conf_threshold,
        should_skip_bird_species_classifier,
    )
except ImportError:
    TwoStageStrategy = None  # type: ignore
    build_binary_track_ultralytics_extras = None  # type: ignore
    _regional_class_ids = None  # type: ignore
    binary_track_ultralytics_conf_floor = None  # type: ignore
    bird_skip_classifier_area_limit = None  # type: ignore
    openvino_binary_bird_score_scale = None  # type: ignore
    per_label_binary_conf_threshold = None  # type: ignore
    should_skip_bird_species_classifier = None  # type: ignore


class _FakeTensor:
    def __init__(self, values):
        self._values = np.array(values)

    def int(self):
        return _FakeTensor(self._values.astype(int))

    def cpu(self):
        return self

    def tolist(self):
        return self._values.tolist()

    def numpy(self):
        return self._values


class _FakeBoxes:
    def __init__(self, track_ids, class_indexes, confidences, boxes_norm, boxes_abs):
        self.id = _FakeTensor(track_ids)
        self.cls = _FakeTensor(class_indexes)
        self.conf = _FakeTensor(confidences)
        self.xyxyn = _FakeTensor(boxes_norm)
        self.xyxy = _FakeTensor(boxes_abs)

    def __len__(self):
        return len(self.conf.tolist())


class _FakeDetectResult:
    def __init__(self, boxes):
        self.boxes = boxes


class _FakeProbs:
    def __init__(self, values):
        self.data = np.array(values, dtype=float)
        self.top1 = int(np.argmax(self.data))
        self.top1conf = np.array(self.data[self.top1])


class _FakeClassifierResult:
    def __init__(self, names, probs):
        self.names = names
        self.probs = _FakeProbs(probs)


class _FakeClassifierModel:
    def __init__(self, names, per_crop_probs):
        self.names = names
        self._per_crop_probs = per_crop_probs

    def __call__(self, crop, verbose=False):
        crop_key = int(crop[0, 0, 0])
        return [_FakeClassifierResult(self.names, self._per_crop_probs[crop_key])]


class TestDetectionStrategy(unittest.TestCase):
    def setUp(self):
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger("TestDetectionStrategy")

        # Resolve project root from this file location: app/processor/tests/ -> ../../../
        current_dir = os.path.dirname(os.path.abspath(__file__))
        self.project_root = os.path.abspath(os.path.join(current_dir, "../../.."))

        # PyTorch two_stage (.pt): см. scripts/fetch-processor-weights.sh и Dockerfile.
        self.binary_model_path = os.path.join(self.project_root, "app/processor/models/detection/weights/yolo11n.pt")
        self.classifier_model_path = os.path.join(
            self.project_root, "app/processor/models/classification/weights/best.pt"
        )
        self.sample_img_path = os.path.join(self.project_root, "app/data/samples/photos/1.jpg")

        self.two_stage_models_exist = os.path.isfile(self.binary_model_path) and os.path.isfile(
            self.classifier_model_path
        )
        self.img_exists = os.path.exists(self.sample_img_path)

        if not self.img_exists:
            self.logger.warning("Sample image not found. Using blank frame for tests.")
            self.frame = np.zeros((720, 1280, 3), dtype=np.uint8)
        else:
            self.frame = cv2.imread(self.sample_img_path)

    def test_two_stage_strategy_integration(self):
        heavy_skip.maybe_skip_heavy(self)
        if TwoStageStrategy is None:
            self.skipTest("TwoStageStrategy not available (import failed).")
        if _ULTRALYTICS_STUB:
            self.skipTest("ultralytics is not installed in this environment.")
        if not self.two_stage_models_exist:
            self.skipTest("Two-stage .pt models not found (run scripts/fetch-processor-weights.sh).")

        self.logger.info("--- Testing TwoStageStrategy Integration ---")

        # Без regional_species: список из теста US/NABirds почти не пересекается с EU-классификатором
        # и оставляет один класс вроде Rodent — ломает смысл интеграции.
        strategy = TwoStageStrategy(
            self.binary_model_path,
            self.classifier_model_path,
            regional_species=None,
        )

        # Detect
        results = strategy.detect(self.frame, "bytetrack.yaml", 0.1)

        # Assertions
        self.logger.info(f"TwoStage Results: {results}")

        if self.img_exists:
            self.assertGreater(len(results), 0, "Should detect at least one bird in sample image")
            names = [r.class_name for r in results]
            # Реальные веса EU/US и снимок 1.jpg дают разный top-1 (в CI было GYRFALCON).
            # Инвариант интеграции: геометрия + уверенность; имя — None (ожидание кадра) или
            # непустая строка вида из species head (без привязки к конкретному таксону).
            for n in names:
                self.assertTrue(
                    n is None or (isinstance(n, str) and len(n.strip()) >= 2),
                    f"class_name must be None or a non-trivial label, got {n!r} in {names}",
                )
            self.assertTrue(
                any(n is not None for n in names),
                f"Expected at least one species classification on sample image, got: {names}",
            )

            # Check properties
            first = results[0]
            self.assertIsNotNone(first.bbox)
            self.assertGreater(first.confidence, 0.0)

    def test_blur_detection_logic(self):
        heavy_skip.maybe_skip_heavy(self)
        if TwoStageStrategy is None:
            self.skipTest("TwoStageStrategy not available (import failed).")
        if _ULTRALYTICS_STUB:
            self.skipTest("ultralytics is not installed in this environment.")
        if not self.two_stage_models_exist:
            self.skipTest("Two-stage .pt models not found (run scripts/fetch-processor-weights.sh).")
        self.logger.info("--- Testing Blur Detection Logic ---")
        strategy = TwoStageStrategy(self.binary_model_path, self.classifier_model_path, blur_threshold=100.0)

        # 1. Create a sharp image (random noise often has high variance, or use a drawing)
        sharp_img = np.zeros((100, 100, 3), dtype=np.uint8)
        cv2.rectangle(sharp_img, (10, 10), (90, 90), (255, 255, 255), -1)  # High contrast
        cv2.circle(sharp_img, (50, 50), 20, (0, 0, 0), -1)

        is_blurry, variance = strategy.is_blurry(sharp_img)
        self.logger.info(f"Sharp image variance: {variance}")
        self.assertFalse(is_blurry, "Sharp image should not be detected as blurry")

        # 2. Create a blurry image
        blur_img = cv2.GaussianBlur(sharp_img, (21, 21), 0)
        is_blurry, variance = strategy.is_blurry(blur_img)
        self.logger.info(f"Blurred image variance: {variance}")
        self.assertTrue(is_blurry, "Blurred image should be detected as blurry")

    def test_regional_class_ids_matches_normalized_common_names(self):
        if _regional_class_ids is None:
            self.skipTest("_regional_class_ids not available")
        names = {
            0: "Garrulus glandarius (Eurasian Jay)",
            1: "Parus_major_(Great_Tit)",
            2: "KNOB_BILLED_DUCK",
        }
        regional = ["Eurasian Jay", "Great Tit", "Hooded Crow"]
        self.assertEqual(_regional_class_ids(names, regional), [0, 1])

    def test_regional_class_ids_matches_hyphenated_common_names(self):
        if _regional_class_ids is None:
            self.skipTest("_regional_class_ids not available")
        names = {
            0: "Columba palumbus (Common Wood-Pigeon)",
            1: "Poecile-montanus-(Willow-Tit)",
        }
        regional = ["Common Wood Pigeon", "Willow Tit"]
        self.assertEqual(_regional_class_ids(names, regional), [0, 1])

    def test_two_stage_skips_frame_when_tracker_ids_absent(self):
        if TwoStageStrategy is None:
            self.skipTest("TwoStageStrategy not available (import failed).")

        class _Boxes:
            id = None

            def __len__(self):
                return 1

        class _Result:
            boxes = _Boxes()

        strategy = TwoStageStrategy.__new__(TwoStageStrategy)
        strategy.binary_model = type(
            "FakeBinaryModel",
            (),
            {
                "track": lambda *args, **kwargs: [_Result()],
            },
        )()
        strategy._classification_index = 0
        strategy.max_blur_checks = 3

        results = strategy.detect(np.zeros((128, 128, 3), dtype=np.uint8), "bytetrack.yaml", 0.1)

        self.assertEqual(results, [])

    def test_two_stage_classifies_multiple_tracks_per_frame_with_budget(self):
        if TwoStageStrategy is None:
            self.skipTest("TwoStageStrategy not available (import failed).")

        frame = np.zeros((120, 120, 3), dtype=np.uint8)
        frame[0:30, 0:30] = 10
        frame[30:60, 30:60] = 20
        frame[60:90, 60:90] = 30

        boxes = _FakeBoxes(
            track_ids=[1, 2, 3],
            class_indexes=[14, 14, 14],
            confidences=[0.9, 0.85, 0.8],
            boxes_norm=[
                [0.0, 0.0, 0.25, 0.25],
                [0.25, 0.25, 0.5, 0.5],
                [0.5, 0.5, 0.75, 0.75],
            ],
            boxes_abs=[
                [0, 0, 30, 30],
                [30, 30, 60, 60],
                [60, 60, 90, 90],
            ],
        )

        strategy = TwoStageStrategy.__new__(TwoStageStrategy)
        strategy.binary_model = type(
            "FakeBinaryModel",
            (),
            {
                "track": lambda *args, **kwargs: [_FakeDetectResult(boxes)],
                "names": {14: "bird"},
            },
        )()
        strategy.classifier_model = _FakeClassifierModel(
            {0: "Blue_Jay", 1: "Great_Tit", 2: "Eurasian_Jay"},
            {
                10: [0.9, 0.05, 0.05],
                20: [0.05, 0.9, 0.05],
                30: [0.05, 0.05, 0.9],
            },
        )
        strategy.classes = None
        strategy.regional_species = None
        strategy.logger = self.logger
        strategy.detector_scope = {"Bird", "Rodent"}
        strategy.min_center_dist = 0.0
        strategy.min_box_size_px = 1
        strategy.blur_threshold = 100.0
        strategy.max_blur_checks = 3
        strategy.max_classifications_per_frame = 2
        strategy._classification_index = 0
        strategy.is_blurry = lambda crop: (False, 250.0)

        first_results = strategy.detect(frame, "bytetrack.yaml", 0.1)
        second_results = strategy.detect(frame, "bytetrack.yaml", 0.1)

        first_classified = {res.track_id: res.class_name for res in first_results if res.class_name}
        second_classified = {res.track_id: res.class_name for res in second_results if res.class_name}

        self.assertEqual(first_classified, {1: "Blue Jay", 2: "Great Tit"})
        self.assertEqual(second_classified, {1: "Blue Jay", 3: "Eurasian Jay"})

    def test_two_stage_limits_blur_scan_with_max_blur_checks(self):
        if TwoStageStrategy is None:
            self.skipTest("TwoStageStrategy not available (import failed).")

        frame = np.zeros((160, 160, 3), dtype=np.uint8)
        frame[0:30, 0:30] = 10
        frame[30:60, 30:60] = 20
        frame[60:90, 60:90] = 30
        frame[90:120, 90:120] = 40

        boxes = _FakeBoxes(
            track_ids=[1, 2, 3, 4],
            class_indexes=[14, 14, 14, 14],
            confidences=[0.9, 0.85, 0.8, 0.75],
            boxes_norm=[
                [0.0, 0.0, 0.2, 0.2],
                [0.2, 0.2, 0.4, 0.4],
                [0.4, 0.4, 0.6, 0.6],
                [0.6, 0.6, 0.8, 0.8],
            ],
            boxes_abs=[
                [0, 0, 30, 30],
                [30, 30, 60, 60],
                [60, 60, 90, 90],
                [90, 90, 120, 120],
            ],
        )

        strategy = TwoStageStrategy.__new__(TwoStageStrategy)
        strategy.binary_model = type(
            "FakeBinaryModel",
            (),
            {
                "track": lambda *args, **kwargs: [_FakeDetectResult(boxes)],
                "names": {14: "bird"},
            },
        )()
        strategy.classifier_model = _FakeClassifierModel(
            {0: "Blue_Jay", 1: "Great_Tit", 2: "Eurasian_Jay", 3: "Robin"},
            {
                10: [0.9, 0.05, 0.03, 0.02],
                20: [0.05, 0.9, 0.03, 0.02],
                30: [0.03, 0.05, 0.9, 0.02],
                40: [0.02, 0.05, 0.03, 0.9],
            },
        )
        strategy.classes = None
        strategy.regional_species = None
        strategy.logger = self.logger
        strategy.detector_scope = {"Bird", "Rodent"}
        strategy.min_center_dist = 0.0
        strategy.min_box_size_px = 1
        strategy.blur_threshold = 100.0
        strategy.max_blur_checks = 2
        strategy.max_classifications_per_frame = 3
        strategy._classification_index = 0
        strategy.is_blurry = lambda crop: (False, 250.0)

        results = strategy.detect(frame, "bytetrack.yaml", 0.1)

        classified = {res.track_id: res.class_name for res in results if res.class_name}

        self.assertEqual(len(classified), 2)
        self.assertIn(1, classified)
        self.assertTrue(set(classified.values()).issubset({"Blue Jay", "Great Tit", "Eurasian Jay", "Robin"}))


class _FakeBoxesNoTrackId:
    """ByteTrack edge case: detections present but ``boxes.id`` is None."""

    def __init__(self):
        self.id = None
        self.conf = _FakeTensor([0.9])
        self.cls = _FakeTensor([14])
        self.xyxyn = _FakeTensor([[0.2, 0.2, 0.6, 0.6]])
        self.xyxy = _FakeTensor([[100, 100, 300, 300]])

    def __len__(self):
        return 1


class _FakeBoxesNoTrackIdParam:
    """Several boxes without track ids — для regen IoU fallback."""

    def __init__(self, boxes_norm, boxes_abs, confidences=None):
        self.id = None
        n = len(boxes_norm)
        c = confidences if confidences is not None else [0.9] * n
        self.conf = _FakeTensor(c)
        self.cls = _FakeTensor([14] * n)
        self.xyxyn = _FakeTensor(boxes_norm)
        self.xyxy = _FakeTensor(boxes_abs)

    def __len__(self):
        return len(self.conf.tolist())


class TestTrackIdMissingBehavior(unittest.TestCase):
    """Regression: never use per-frame indices as track_id (#201)."""

    def test_track_maybe_retries_once_when_first_id_is_none(self):
        from detection_strategy import _track_maybe_retry

        calls = []

        def track_fn(*args, **kwargs):
            calls.append(1)
            if len(calls) == 1:
                return [_FakeDetectResult(_FakeBoxesNoTrackId())]
            good = _FakeBoxes(
                [42],
                [14],
                [0.9],
                [[0.1, 0.1, 0.4, 0.4]],
                [[1, 1, 50, 50]],
            )
            return [_FakeDetectResult(good)]

        model = type("M", (), {"track": track_fn})()
        frame = np.zeros((64, 64, 3), dtype=np.uint8)
        results = _track_maybe_retry(model, frame)
        self.assertEqual(len(calls), 2)
        self.assertIsNotNone(results[0].boxes.id)
        self.assertEqual(results[0].boxes.id.tolist(), [42])

    def test_track_maybe_does_not_retry_when_first_id_exists(self):
        from detection_strategy import _track_maybe_retry

        calls = []

        def track_fn(*args, **kwargs):
            calls.append(1)
            good = _FakeBoxes(
                [7],
                [14],
                [0.9],
                [[0.1, 0.1, 0.4, 0.4]],
                [[1, 1, 50, 50]],
            )
            return [_FakeDetectResult(good)]

        model = type("M", (), {"track": track_fn})()
        frame = np.zeros((64, 64, 3), dtype=np.uint8)
        results = _track_maybe_retry(model, frame)

        self.assertEqual(len(calls), 1)
        self.assertEqual(results[0].boxes.id.tolist(), [7])

    def test_two_stage_live_iou_fallback_keeps_detection_when_ids_stay_none(self):
        if TwoStageStrategy is None:
            self.skipTest("TwoStageStrategy not available (import failed).")
        frame = np.zeros((400, 400, 3), dtype=np.uint8)
        boxes = _FakeBoxesNoTrackId()
        strategy = TwoStageStrategy.__new__(TwoStageStrategy)
        strategy.binary_model = type(
            "FakeBinaryModel",
            (),
            {
                "track": lambda *args, **kwargs: [_FakeDetectResult(boxes)],
                "names": {14: "bird"},
            },
        )()
        strategy.classifier_model = _FakeClassifierModel({0: "X"}, {0: [1.0]})
        strategy.classes = None
        strategy.regional_species = None
        strategy.logger = logging.getLogger("test")
        strategy.detector_scope = {"Bird", "Rodent"}
        strategy.min_center_dist = 0.0
        strategy.min_box_size_px = 1
        strategy.blur_threshold = 0.0
        strategy.max_blur_checks = 3
        strategy.max_classifications_per_frame = 2
        strategy._classification_index = 0
        strategy.is_blurry = lambda crop: (False, 250.0)

        results = strategy.detect(frame, "bytetrack.yaml", 0.1)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].track_id, 1)


class TestGreedyIoUTrackIds(unittest.TestCase):
    def test_greedy_match_reuses_prev_id_when_iou_high(self):
        from detection_strategy import _greedy_match_iou_track_ids

        prev = np.array([[0.2, 0.2, 0.55, 0.55]])
        curr = np.array([[0.21, 0.21, 0.56, 0.56]])
        ids, nid = _greedy_match_iou_track_ids(prev, [42], curr, iou_thr=0.25, next_id=100)
        self.assertEqual(ids, [42])
        self.assertEqual(nid, 100)

    def test_greedy_match_allocates_next_id_when_iou_low(self):
        from detection_strategy import _greedy_match_iou_track_ids

        prev = np.array([[0.1, 0.1, 0.2, 0.2]])
        curr = np.array([[0.8, 0.8, 0.9, 0.9]])
        ids, nid = _greedy_match_iou_track_ids(prev, [1], curr, iou_thr=0.25, next_id=7)
        self.assertEqual(ids, [7])
        self.assertEqual(nid, 8)


class TestRegenSyntheticTrackIds(unittest.TestCase):
    def test_two_stage_regen_iou_fallback_stable_id_across_frames(self):
        if TwoStageStrategy is None:
            self.skipTest("TwoStageStrategy not available (import failed).")
        try:
            import app_config.app_config as ac_mod
        except ImportError:
            self.skipTest("app_config not available on PYTHONPATH")

        frame = np.zeros((320, 320, 3), dtype=np.uint8)
        frame[60:180, 60:180] = 77

        b1 = _FakeBoxesNoTrackIdParam([[0.15, 0.15, 0.52, 0.52]], [[48, 48, 166, 166]])
        b2 = _FakeBoxesNoTrackIdParam([[0.16, 0.16, 0.53, 0.53]], [[51, 51, 170, 170]])
        rounds = [{"box": b1}, {"box": b2}]

        def fake_track_model():
            ri = {"i": 0}

            def track(*a, **k):
                bx = rounds[ri["i"]]["box"]
                ri["i"] += 1
                return [_FakeDetectResult(bx)]

            return track

        strategy = TwoStageStrategy.__new__(TwoStageStrategy)
        strategy.binary_model = type(
            "FakeBinaryModel",
            (),
            {
                "track": fake_track_model(),
                "names": {14: "bird"},
            },
        )()
        strategy.classifier_model = _FakeClassifierModel({0: "Great_Tit"}, {77: [1.0], 0: [1.0]})
        strategy.classes = None
        strategy.regional_species = None
        strategy.logger = logging.getLogger("test_regen_iou")
        strategy.detector_scope = {"Bird", "Rodent"}
        strategy.min_center_dist = 0.0
        strategy.min_box_size_px = 1
        strategy.blur_threshold = 0.0
        strategy.max_blur_checks = 3
        strategy.max_classifications_per_frame = 2
        strategy.classification_scheduler = "priority"
        strategy._classification_index = 0
        strategy.binary_imgsz = 640
        strategy.inference_backend = "torch"
        strategy._for_track_regen = True
        strategy._regen_iou_prev_boxes = None
        strategy._regen_iou_prev_ids = None
        strategy._regen_iou_next_id = 1
        strategy.is_blurry = lambda crop: (False, 250.0)

        cfg_map = {
            "processor.track_regen_iou_id_fallback": True,
            "processor.track_regen_iou_match_threshold": 0.22,
            "processor.binary_track_missing_id_extra_retries": 0,
            "processor.min_confidence_binary_bird": 0.12,
            "processor.min_confidence_binary_rodent": 0.12,
            "processor.max_classifications_per_frame": 4,
            "processor.min_box_size_px": 1,
            "processor.binary_imgsz": 640,
        }

        def _cfg_get(key, default=None):
            return cfg_map.get(key, default)

        mock_cfg = MagicMock(get=MagicMock(side_effect=_cfg_get))
        with patch.object(ac_mod, "app_config", mock_cfg):
            r1 = strategy.detect(frame, "bytetrack.yaml", 0.12)
            r2 = strategy.detect(frame, "bytetrack.yaml", 0.12)

        self.assertEqual(len(r1), 1)
        self.assertEqual(len(r2), 1)
        self.assertEqual(r1[0].track_id, 1)
        self.assertEqual(r2[0].track_id, 1)


class TestBinaryPredictClassAllowlist(unittest.TestCase):
    def test_allowlist_parses_processor_key(self):
        if TwoStageStrategy is None:
            self.skipTest("TwoStageStrategy unavailable")
        from processor_runtime_profile import RuntimeProfileConfigOverlay

        s = TwoStageStrategy.__new__(TwoStageStrategy)

        def _g(k, d=None):
            if k == "processor.binary_predict_class_allowlist":
                return [14, 99]
            return d

        mock = MagicMock(get=MagicMock(side_effect=_g))
        rt = RuntimeProfileConfigOverlay(mock, None)
        self.assertEqual(s._binary_class_allowlist(rt), {14, 99})

    def test_allowlist_empty_returns_none(self):
        if TwoStageStrategy is None:
            self.skipTest("TwoStageStrategy unavailable")
        from processor_runtime_profile import RuntimeProfileConfigOverlay

        s = TwoStageStrategy.__new__(TwoStageStrategy)

        def _g(k, d=None):
            return [] if k == "processor.binary_predict_class_allowlist" else d

        mock = MagicMock(get=MagicMock(side_effect=_g))
        rt = RuntimeProfileConfigOverlay(mock, None)
        self.assertIsNone(s._binary_class_allowlist(rt))


class TestBinaryConfHelpers(unittest.TestCase):
    def test_conf_floor_min_of_per_label_and_base(self):
        if binary_track_ultralytics_conf_floor is None:
            self.skipTest("detection_strategy import failed")
        cfg = {
            "processor.min_confidence_binary_bird": 0.55,
            "processor.min_confidence_binary_rodent": 0.22,
        }
        self.assertAlmostEqual(binary_track_ultralytics_conf_floor(0.30, cfg), 0.22)

    def test_conf_floor_reads_legacy_min_confidence_binary_squirrel_key(self):
        if binary_track_ultralytics_conf_floor is None:
            self.skipTest("detection_strategy import failed")
        cfg = {
            "processor.min_confidence_binary_bird": 0.55,
            "processor.min_confidence_binary_squirrel": 0.22,
        }
        self.assertAlmostEqual(binary_track_ultralytics_conf_floor(0.30, cfg), 0.22)

    def test_per_label_thresholds(self):
        if per_label_binary_conf_threshold is None:
            self.skipTest("detection_strategy import failed")
        cfg = {
            "processor.min_confidence_binary_bird": 0.5,
            "processor.min_confidence_binary_rodent": 0.2,
        }
        self.assertAlmostEqual(per_label_binary_conf_threshold("Bird", 0.3, cfg), 0.5)
        self.assertAlmostEqual(per_label_binary_conf_threshold("Rodent", 0.3, cfg), 0.2)
        self.assertAlmostEqual(per_label_binary_conf_threshold("Squirrel", 0.3, cfg), 0.2)

    def test_openvino_track_conf_cap_lowers_floor(self):
        if binary_track_ultralytics_conf_floor is None:
            self.skipTest("detection_strategy import failed")
        cfg = {
            "processor.min_confidence_binary_bird": 0.55,
            "processor.min_confidence_binary_rodent": 0.22,
            "processor.openvino_binary_track_ultralytics_conf": 0.05,
        }
        self.assertAlmostEqual(binary_track_ultralytics_conf_floor(0.30, cfg, inference_backend="torch"), 0.22)
        self.assertAlmostEqual(binary_track_ultralytics_conf_floor(0.30, cfg, inference_backend="openvino"), 0.05)

    def test_openvino_bird_threshold_override(self):
        if per_label_binary_conf_threshold is None:
            self.skipTest("detection_strategy import failed")
        cfg = {
            "processor.min_confidence_binary_bird": 0.5,
            "processor.openvino_min_confidence_binary_bird": 0.19,
        }
        self.assertAlmostEqual(
            per_label_binary_conf_threshold("Bird", 0.3, cfg, inference_backend="openvino"),
            0.19,
        )
        self.assertAlmostEqual(per_label_binary_conf_threshold("Bird", 0.3, cfg, inference_backend="torch"), 0.5)

    def test_openvino_bird_score_scale_helper(self):
        if openvino_binary_bird_score_scale is None:
            self.skipTest("detection_strategy import failed")
        self.assertAlmostEqual(
            openvino_binary_bird_score_scale({}, inference_backend="torch"),
            1.0,
        )
        self.assertAlmostEqual(
            openvino_binary_bird_score_scale(
                {"processor.openvino_binary_bird_score_scale": 6.0},
                inference_backend="openvino",
            ),
            6.0,
        )

    def test_bird_skip_classifier_area(self):
        if should_skip_bird_species_classifier is None:
            self.skipTest("detection_strategy import failed")
        cfg = {"processor.bird_skip_classifier_max_area_frac": 0.02}
        self.assertTrue(should_skip_bird_species_classifier("Bird", 0.01, cfg))
        self.assertFalse(should_skip_bird_species_classifier("Bird", 0.05, cfg))
        self.assertFalse(should_skip_bird_species_classifier("Rodent", 0.01, cfg))
        self.assertIsNone(bird_skip_classifier_area_limit({}))


class TestBuildBinaryTrackUltralyticsExtras(unittest.TestCase):
    def test_extras_include_iou_and_max_det_when_valid(self):
        if build_binary_track_ultralytics_extras is None:
            self.skipTest("detection_strategy import failed")
        cfg = {
            "processor.binary_track_iou": 0.72,
            "processor.binary_track_max_det": 384,
        }
        self.assertEqual(
            build_binary_track_ultralytics_extras(cfg),
            {"iou": 0.72, "max_det": 384},
        )

    def test_extras_skip_invalid_or_out_of_range(self):
        if build_binary_track_ultralytics_extras is None:
            self.skipTest("detection_strategy import failed")
        self.assertEqual(
            build_binary_track_ultralytics_extras({"processor.binary_track_iou": 0.01}),
            {},
        )
        self.assertEqual(
            build_binary_track_ultralytics_extras({"processor.binary_track_max_det": 5000}),
            {},
        )


class TestTwoStageBirdSkipClassifier(unittest.TestCase):
    def test_tiny_bird_skips_classifier_when_area_limit_set(self):
        if TwoStageStrategy is None:
            self.skipTest("TwoStageStrategy import failed")
        try:
            import app_config.app_config as ac_mod
        except ImportError:
            self.skipTest("app_config not available on PYTHONPATH")

        frame = np.zeros((200, 200, 3), dtype=np.uint8)
        frame[0:40, 0:40] = 80
        # bbox ~8% area — ниже порога skip 0.10
        boxes = _FakeBoxes(
            track_ids=[1],
            class_indexes=[14],
            confidences=[0.95],
            boxes_norm=[[0.0, 0.0, 0.2, 0.2]],
            boxes_abs=[[0, 0, 40, 40]],
        )

        strategy = TwoStageStrategy.__new__(TwoStageStrategy)
        strategy.binary_model = type(
            "FakeBinaryModel",
            (),
            {
                "track": lambda *args, **kwargs: [_FakeDetectResult(boxes)],
                "names": {14: "bird"},
            },
        )()
        strategy.classifier_model = _FakeClassifierModel(
            {0: "Great_Tit"},
            {80: [1.0]},
        )
        strategy.classes = None
        strategy.regional_species = None
        strategy.logger = logging.getLogger("test")
        strategy.detector_scope = {"Bird", "Rodent"}
        strategy.min_center_dist = 0.0
        strategy.min_box_size_px = 1
        strategy.blur_threshold = 0.0
        strategy.max_blur_checks = 3
        strategy.max_classifications_per_frame = 2
        strategy._classification_index = 0
        strategy.is_blurry = lambda crop: (False, 250.0)

        def _cfg_get(key, default=None):
            if key == "processor.bird_skip_classifier_max_area_frac":
                return 0.10
            return default

        mock_cfg = MagicMock(get=MagicMock(side_effect=_cfg_get))
        with patch.object(ac_mod, "app_config", mock_cfg):
            results = strategy.detect(frame, "bytetrack.yaml", 0.1)

        self.assertEqual(len(results), 1)
        self.assertIsNone(results[0].class_name)
        self.assertIsNone(results[0].classifier_confidence)


class TestSmallObjectAutoRelax(unittest.TestCase):
    def test_auto_small_object_relax_recovers_small_box(self):
        if TwoStageStrategy is None:
            self.skipTest("TwoStageStrategy import failed")
        try:
            import app_config.app_config as ac_mod
        except ImportError:
            self.skipTest("app_config not available on PYTHONPATH")

        frame = np.zeros((120, 120, 3), dtype=np.uint8)
        frame[10:26, 10:26] = 33
        boxes = _FakeBoxes(
            track_ids=[7],
            class_indexes=[14],
            confidences=[0.23],
            boxes_norm=[[0.08, 0.08, 0.22, 0.22]],
            boxes_abs=[[10, 10, 26, 26]],
        )

        strategy = TwoStageStrategy.__new__(TwoStageStrategy)
        strategy.binary_model = type(
            "FakeBinaryModel",
            (),
            {
                "track": lambda *args, **kwargs: [_FakeDetectResult(boxes)],
                "names": {14: "bird"},
            },
        )()
        strategy.classifier_model = _FakeClassifierModel(
            {0: "Great_Tit"},
            {33: [1.0]},
        )
        strategy.classes = None
        strategy.regional_species = None
        strategy.logger = logging.getLogger("test_small_relax")
        strategy.detector_scope = {"Bird", "Rodent"}
        strategy.min_center_dist = 0.03
        strategy.min_box_size_px = 40
        strategy.blur_threshold = 0.0
        strategy.max_blur_checks = 3
        strategy.max_classifications_per_frame = 2
        strategy._classification_index = 0
        strategy.is_blurry = lambda crop: (False, 250.0)
        strategy.classification_scheduler = "priority"
        strategy.binary_imgsz = 640
        strategy._for_track_regen = False

        def _cfg_get(key, default=None):
            mapping = {
                "processor.auto_small_object_relax_enabled": True,
                "processor.auto_small_object_relax_min_box_size_px": 12,
                "processor.auto_small_object_relax_min_center_dist": 0.0,
                "processor.auto_small_object_relax_conf_delta": 0.08,
                "processor.auto_small_object_relax_max_candidates": 2,
                "processor.min_confidence_binary_bird": 0.24,
            }
            return mapping.get(key, default)

        mock_cfg = MagicMock(get=MagicMock(side_effect=_cfg_get))
        with patch.object(ac_mod, "app_config", mock_cfg):
            results = strategy.detect(frame, "bytetrack.yaml", 0.24)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].track_id, 7)


class TestEntropyMargin(unittest.TestCase):
    def test_entropy_and_margin_pure_numpy(self):
        from detection_strategy import entropy_and_margin_from_prob_vector

        p = np.ones(100, dtype=np.float64) / 100.0
        ent, margin = entropy_and_margin_from_prob_vector(p)
        self.assertGreater(ent, 4.5)
        self.assertAlmostEqual(margin, 0.0, places=5)

        peak = np.zeros(50)
        peak[0] = 1.0
        ent2, margin2 = entropy_and_margin_from_prob_vector(peak)
        self.assertAlmostEqual(ent2, 0.0, places=5)
        self.assertAlmostEqual(margin2, 1.0)


if __name__ == "__main__":
    unittest.main()
