import unittest
import sys
import os
import cv2
import numpy as np
import logging

# Ensure project root is in path to import app modules
current_dir = os.path.dirname(os.path.abspath(__file__))
# app/processor/tests -> app/processor/src
src_path = os.path.abspath(os.path.join(current_dir, '../src'))
sys.path.append(src_path)

try:
    from detection_strategy import TwoStageStrategy, SingleStageStrategy
except ImportError:
    TwoStageStrategy = None  # type: ignore
    SingleStageStrategy = None  # type: ignore

# Sample regional species list in Philadelphia area.
regional_species = ['Northern Cardinal', 'Dark-eyed Junco', 'Tufted Titmouse', 'American Crow', 'Mourning Dove', 'Blue Jay', 'Carolina Wren', 'White-breasted Nuthatch', 'White-throated Sparrow', 'Downy Woodpecker', 'Red-bellied Woodpecker', 'Song Sparrow', 'European Starling', 'American Goldfinch', 'House Finch', 'Carolina Chickadee', 'House Sparrow', 'American Robin', 'Northern Mockingbird', 'Black-capped Chickadee', 'Eastern Bluebird', 'Northern Flicker', 'Hairy Woodpecker', 'Rock Pigeon', 'Golden-crowned Kinglet', 'Yellow-rumped Warbler', 'Pileated Woodpecker', 'American Tree Sparrow', 'Red-winged Blackbird', 'Red-breasted Nuthatch', 'Brown Creeper', 'Common Raven', 'Cedar Waxwing', 'Yellow-bellied Sapsucker', 'Common Grackle', 'Purple Finch', 'Pine Siskin', 'Horned Lark', 'Hermit Thrush', 'Swamp Sparrow', 'Ruby-crowned Kinglet', 'Eastern Towhee', 'Winter Wren', 'Fox Sparrow', 'Brown-headed Cowbird', 'Field Sparrow', 'Squirrel']


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
    def __init__(self, track_ids, confidences, boxes_norm, boxes_abs):
        self.id = _FakeTensor(track_ids)
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
        self.project_root = os.path.abspath(os.path.join(current_dir, '../../..'))
        
        # Paths
        self.binary_model_path = os.path.join(self.project_root, "app/processor/models/detection/nabirds_yolo11n_binary/weights/best_ncnn_model")
        self.classifier_model_path = os.path.join(self.project_root, "app/processor/models/classification/nabirds_yolo11n_cls/weights/best_ncnn_model")
        self.single_model_path = os.path.join(self.project_root, "app/processor/models/detection/nabirds_yolov8n_ncnn_model")
        self.sample_img_path = os.path.join(self.project_root, "app/data/samples/photos/1.jpg")

        # Check if resources exist
        self.two_stage_models_exist = (
            os.path.exists(self.binary_model_path) and 
            os.path.exists(self.classifier_model_path)
        )
        self.single_stage_exists = os.path.exists(self.single_model_path)
        self.img_exists = os.path.exists(self.sample_img_path)

        if not self.img_exists:
            self.logger.warning("Sample image not found. Using blank frame for tests.")
            self.frame = np.zeros((720, 1280, 3), dtype=np.uint8)
        else:
            self.frame = cv2.imread(self.sample_img_path)

    def test_two_stage_strategy_integration(self):
        if TwoStageStrategy is None:
            self.skipTest("TwoStageStrategy not available (import failed).")
        if not self.two_stage_models_exist:
            self.skipTest("Two-stage NCNN detection models not found.")
            
        self.logger.info("--- Testing TwoStageStrategy Integration ---")
        
        # Initialize
        strategy = TwoStageStrategy(
            self.binary_model_path, 
            self.classifier_model_path, 
            regional_species=regional_species
        )
        
        # Detect
        results = strategy.detect(self.frame, "bytetrack.yaml", 0.1)
        
        # Assertions
        self.logger.info(f"TwoStage Results: {results}")
        
        if self.img_exists:
            # We expect a Blue Jay in the sample image
            self.assertGreater(len(results), 0, "Should detect at least one bird in sample image")
            
            blue_jay_detected = any("Blue Jay" in res.class_name for res in results)
            self.assertTrue(blue_jay_detected, f"Should detect Blue Jay. Got: {[r.class_name for r in results]}")
            
            # Check properties
            first = results[0]
            self.assertIsNotNone(first.bbox)
            self.assertGreater(first.confidence, 0.0)

    def test_single_stage_strategy_integration(self):
        if SingleStageStrategy is None:
            self.skipTest("SingleStageStrategy not available (import failed).")
        if not self.single_stage_exists:
            self.skipTest("Single-stage NCNN model not found.")

        self.logger.info("--- Testing SingleStageStrategy Integration ---")
        
        # Initialize
        strategy = SingleStageStrategy(
            self.single_model_path,
            regional_species=regional_species
        )

        # Detect
        results = strategy.detect(self.frame, "bytetrack.yaml", 0.1)

        # Assertions
        self.logger.info(f"SingleStage Results: {results}")

        if self.img_exists:
            self.assertGreater(len(results), 0, "Should detect at least one bird in sample image")
            
            blue_jay_detected = any("Blue Jay" in res.class_name for res in results)
            self.assertTrue(blue_jay_detected, f"Should detect Blue Jay. Got: {[r.class_name for r in results]}")

    def test_blur_detection_logic(self):
        if TwoStageStrategy is None:
            self.skipTest("TwoStageStrategy not available (import failed).")
        self.logger.info("--- Testing Blur Detection Logic ---")
        strategy = TwoStageStrategy(
            self.binary_model_path, 
            self.classifier_model_path,
            blur_threshold=100.0
        )
        
        # 1. Create a sharp image (random noise often has high variance, or use a drawing)
        sharp_img = np.zeros((100, 100, 3), dtype=np.uint8)
        cv2.rectangle(sharp_img, (10, 10), (90, 90), (255, 255, 255), -1) # High contrast
        cv2.circle(sharp_img, (50, 50), 20, (0, 0, 0), -1)
        
        is_blurry, variance = strategy.is_blurry(sharp_img)
        self.logger.info(f"Sharp image variance: {variance}")
        self.assertFalse(is_blurry, "Sharp image should not be detected as blurry")
        
        # 2. Create a blurry image
        blur_img = cv2.GaussianBlur(sharp_img, (21, 21), 0)
        is_blurry, variance = strategy.is_blurry(blur_img)
        self.logger.info(f"Blurred image variance: {variance}")
        self.assertTrue(is_blurry, "Blurred image should be detected as blurry")

    def test_coco_auto_filter_constant_is_bird_only(self):
        if SingleStageStrategy is None:
            self.skipTest("SingleStageStrategy not available (import failed).")
        from detection_strategy import _COCO_BIRD_ONLY_CLASS_NAMES

        self.assertEqual(_COCO_BIRD_ONLY_CLASS_NAMES, frozenset({'bird'}))

    def test_single_stage_skips_frame_when_tracker_ids_absent(self):
        if SingleStageStrategy is None:
            self.skipTest("SingleStageStrategy not available (import failed).")

        class _Boxes:
            id = None

            def __len__(self):
                return 1

        class _Result:
            boxes = _Boxes()

        strategy = SingleStageStrategy.__new__(SingleStageStrategy)
        strategy.model = type(
            'FakeModel',
            (),
            {
                'track': lambda *args, **kwargs: [_Result()],
                'names': {0: 'bird'},
            },
        )()
        strategy.classes = None

        results = strategy.detect(np.zeros((128, 128, 3), dtype=np.uint8), 'bytetrack.yaml', 0.1)

        self.assertEqual(results, [])

    def test_single_stage_regional_filter_matches_normalized_common_names(self):
        if SingleStageStrategy is None:
            self.skipTest("SingleStageStrategy not available (import failed).")

        from detection_strategy import _normalize_species_filter_text

        strategy = SingleStageStrategy.__new__(SingleStageStrategy)
        strategy.logger = self.logger
        strategy.model = type(
            'FakeModel',
            (),
            {
                'names': {
                    0: 'Garrulus glandarius (Eurasian Jay)',
                    1: 'Parus_major_(Great_Tit)',
                    2: 'KNOB_BILLED_DUCK',
                },
            },
        )()
        strategy.regional_species = ['Eurasian Jay', 'Great Tit', 'Hooded Crow']
        regional_keys = [_normalize_species_filter_text(x) for x in strategy.regional_species]

        classes = [
            cid
            for cid, label in strategy.model.names.items()
            if any(key and key in _normalize_species_filter_text(label) for key in regional_keys)
        ]

        self.assertEqual(classes, [0, 1])

    def test_single_stage_regional_filter_matches_hyphenated_common_names(self):
        if SingleStageStrategy is None:
            self.skipTest("SingleStageStrategy not available (import failed).")

        from detection_strategy import _normalize_species_filter_text

        strategy = SingleStageStrategy.__new__(SingleStageStrategy)
        strategy.logger = self.logger
        strategy.model = type(
            'FakeModel',
            (),
            {
                'names': {
                    0: 'Columba palumbus (Common Wood-Pigeon)',
                    1: 'Poecile-montanus-(Willow-Tit)',
                },
            },
        )()
        strategy.regional_species = ['Common Wood Pigeon', 'Willow Tit']
        regional_keys = [_normalize_species_filter_text(x) for x in strategy.regional_species]

        classes = [
            cid
            for cid, label in strategy.model.names.items()
            if any(key and key in _normalize_species_filter_text(label) for key in regional_keys)
        ]

        self.assertEqual(classes, [0, 1])

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
            'FakeBinaryModel',
            (),
            {
                'track': lambda *args, **kwargs: [_Result()],
            },
        )()
        strategy._classification_index = 0
        strategy.max_blur_checks = 3

        results = strategy.detect(np.zeros((128, 128, 3), dtype=np.uint8), 'bytetrack.yaml', 0.1)

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
            'FakeBinaryModel',
            (),
            {'track': lambda *args, **kwargs: [_FakeDetectResult(boxes)]},
        )()
        strategy.classifier_model = _FakeClassifierModel(
            {0: 'Blue_Jay', 1: 'Great_Tit', 2: 'Eurasian_Jay'},
            {
                10: [0.9, 0.05, 0.05],
                20: [0.05, 0.9, 0.05],
                30: [0.05, 0.05, 0.9],
            },
        )
        strategy.classes = None
        strategy.regional_species = None
        strategy.logger = self.logger
        strategy.min_center_dist = 0.0
        strategy.min_box_size_px = 1
        strategy.blur_threshold = 100.0
        strategy.max_blur_checks = 3
        strategy.max_classifications_per_frame = 2
        strategy._classification_index = 0
        strategy.is_blurry = lambda crop: (False, 250.0)

        first_results = strategy.detect(frame, 'bytetrack.yaml', 0.1)
        second_results = strategy.detect(frame, 'bytetrack.yaml', 0.1)

        first_classified = {res.track_id: res.class_name for res in first_results if res.class_name}
        second_classified = {res.track_id: res.class_name for res in second_results if res.class_name}

        self.assertEqual(first_classified, {1: 'Blue Jay', 2: 'Great Tit'})
        self.assertEqual(second_classified, {1: 'Blue Jay', 3: 'Eurasian Jay'})

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
            'FakeBinaryModel',
            (),
            {'track': lambda *args, **kwargs: [_FakeDetectResult(boxes)]},
        )()
        strategy.classifier_model = _FakeClassifierModel(
            {0: 'Blue_Jay', 1: 'Great_Tit', 2: 'Eurasian_Jay', 3: 'Robin'},
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
        strategy.min_center_dist = 0.0
        strategy.min_box_size_px = 1
        strategy.blur_threshold = 100.0
        strategy.max_blur_checks = 2
        strategy.max_classifications_per_frame = 3
        strategy._classification_index = 0
        strategy.is_blurry = lambda crop: (False, 250.0)

        results = strategy.detect(frame, 'bytetrack.yaml', 0.1)

        classified = {res.track_id: res.class_name for res in results if res.class_name}

        self.assertEqual(classified, {1: 'Blue Jay', 2: 'Great Tit'})


class _FakeBoxesNoTrackId:
    """ByteTrack edge case: detections present but ``boxes.id`` is None."""

    def __init__(self):
        self.id = None
        self.conf = _FakeTensor([0.9])
        self.cls = _FakeTensor([0])
        self.xyxyn = _FakeTensor([[0.2, 0.2, 0.6, 0.6]])
        self.xyxy = _FakeTensor([[100, 100, 300, 300]])

    def __len__(self):
        return 1


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
                [0.9],
                [[0.1, 0.1, 0.4, 0.4]],
                [[1, 1, 50, 50]],
            )
            return [_FakeDetectResult(good)]

        model = type('M', (), {'track': track_fn})()
        frame = np.zeros((64, 64, 3), dtype=np.uint8)
        results = _track_maybe_retry(model, frame)
        self.assertEqual(len(calls), 2)
        self.assertIsNotNone(results[0].boxes.id)
        self.assertEqual(results[0].boxes.id.tolist(), [42])

    def test_two_stage_returns_empty_when_ids_stay_none(self):
        if TwoStageStrategy is None:
            self.skipTest('TwoStageStrategy not available (import failed).')
        frame = np.zeros((400, 400, 3), dtype=np.uint8)
        boxes = _FakeBoxesNoTrackId()
        strategy = TwoStageStrategy.__new__(TwoStageStrategy)
        strategy.binary_model = type(
            'FakeBinaryModel',
            (),
            {'track': lambda *args, **kwargs: [_FakeDetectResult(boxes)]},
        )()
        strategy.classifier_model = _FakeClassifierModel({0: 'X'}, {10: [1.0]})
        strategy.classes = None
        strategy.regional_species = None
        strategy.logger = logging.getLogger('test')
        strategy.min_center_dist = 0.0
        strategy.min_box_size_px = 1
        strategy.blur_threshold = 0.0
        strategy.max_blur_checks = 3
        strategy.max_classifications_per_frame = 2
        strategy._classification_index = 0
        strategy.is_blurry = lambda crop: (False, 250.0)

        results = strategy.detect(frame, 'bytetrack.yaml', 0.1)
        self.assertEqual(results, [])


if __name__ == '__main__':
    unittest.main()
