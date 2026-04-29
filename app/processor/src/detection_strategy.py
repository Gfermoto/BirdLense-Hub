from abc import ABC, abstractmethod
import logging
import math
from typing import Any, List, Mapping, Optional, Tuple
from dataclasses import dataclass
import numpy as np
import cv2
from detector_labels import normalize_detector_label
from inference.torch_backend import load_yolo_classifier, load_yolo_detector
from inference.weight_contract import validate_detector_weight_contract
from processor_runtime_profile import RuntimeProfileConfigOverlay

logger = logging.getLogger(__name__)


def _rodent_binary_threshold_raw(app_config: Mapping[str, Any]) -> Any:
    """Новый ключ ``min_confidence_binary_rodent``; ``min_confidence_binary_squirrel`` — только совместимость со старым YAML."""
    raw = app_config.get("processor.min_confidence_binary_rodent")
    if raw is not None:
        return raw
    return app_config.get("processor.min_confidence_binary_squirrel")


def binary_track_ultralytics_conf_floor(base_min: float, app_config: Mapping[str, Any]) -> float:
    """
    Минимальный ``conf`` для YOLO ``track()``, чтобы кандидаты не отсекались до per-label фильтра.

    Если заданы отдельные пороги Bird/Rodent, берётся min(...) с базовым — иначе жёсткий
    порог на птицу отбросил бы грызунов на этапе движка.
    """
    try:
        base = float(base_min)
    except (TypeError, ValueError):
        base = 0.22
    b_raw = app_config.get("processor.min_confidence_binary_bird")
    s_raw = _rodent_binary_threshold_raw(app_config)
    bird_m = float(b_raw) if b_raw is not None else base
    rod_m = float(s_raw) if s_raw is not None else base
    return min(base, bird_m, rod_m)


def per_label_binary_conf_threshold(
    detector_label: str,
    base_min: float,
    app_config: Mapping[str, Any],
) -> float:
    """Порог confidence бинарника после нормализации метки (Bird / Rodent)."""
    try:
        base = float(base_min)
    except (TypeError, ValueError):
        base = 0.22
    b_raw = app_config.get("processor.min_confidence_binary_bird")
    s_raw = _rodent_binary_threshold_raw(app_config)
    bird_m = float(b_raw) if b_raw is not None else base
    rod_m = float(s_raw) if s_raw is not None else base
    if detector_label == "Bird":
        return bird_m
    if detector_label in {"Rodent", "Squirrel"}:
        return rod_m
    return base


def bird_skip_classifier_area_limit(app_config: Mapping[str, Any]) -> Optional[float]:
    """
    Если > 0: для боксов Bird с площадью <= этого порога (доля кадра) не вызывать классификатор вида.

    Снижает ложные «синицы» на мелком объекте (мышь), ошибочно помеченном бинарником как Bird.
    """
    raw = app_config.get("processor.bird_skip_classifier_max_area_frac")
    if raw is None:
        return None
    try:
        v = float(raw)
    except (TypeError, ValueError):
        return None
    if v <= 0.0:
        return None
    return min(v, 1.0)


def should_skip_bird_species_classifier(
    detector_label: str,
    box_area_norm: float,
    app_config: Mapping[str, Any],
) -> bool:
    lim = bird_skip_classifier_area_limit(app_config)
    if lim is None:
        return False
    if str(detector_label or "").strip() != "Bird":
        return False
    try:
        area = float(box_area_norm)
    except (TypeError, ValueError):
        return False
    return area > 0.0 and area <= lim


def _normalize_species_filter_text(name: str) -> str:
    return str(name or "").replace("_OR_", "/").replace("_", " ").replace("-", " ").strip().lower()


def entropy_and_margin_from_prob_vector(probs_flat: Any) -> tuple[float, float]:
    """
    Shannon entropy (nats) and top1−top2 margin from a classifier probability vector (#370, AL hooks).

    Accepts a 1D torch.Tensor or array-like (Ultralytics ``probs.data``).
    """
    try:
        import torch

        if isinstance(probs_flat, torch.Tensor):
            arr = probs_flat.detach().float().cpu().numpy().reshape(-1)
        else:
            arr = np.asarray(probs_flat, dtype=np.float64).reshape(-1)
    except Exception:
        arr = np.asarray(probs_flat, dtype=np.float64).reshape(-1)
    if arr.size == 0:
        return 0.0, 0.0
    p = np.clip(arr.astype(np.float64), 1e-12, 1.0)
    s = float(p.sum())
    if s <= 0:
        return 0.0, 0.0
    p = p / s
    entropy = float(-np.sum(p * np.log(p)))
    sorted_p = np.sort(p)[::-1]
    margin = float(sorted_p[0] - sorted_p[1]) if sorted_p.size >= 2 else float(sorted_p[0])
    if not math.isfinite(entropy):
        entropy = 0.0
    if not math.isfinite(margin):
        margin = 0.0
    return entropy, margin


def _regional_class_ids(
    names: dict,
    regional_species: List[str],
) -> List[int]:
    """Индексы классов YOLO, чьи подписи пересекаются с regional_species (после нормализации)."""
    regional_keys = [_normalize_species_filter_text(x) for x in regional_species]
    return [
        cid
        for cid, label in names.items()
        if any(key and key in _normalize_species_filter_text(label) for key in regional_keys)
    ]


def _track_maybe_retry(model, frame: np.ndarray, **kwargs):
    """ByteTrack иногда возвращает ``boxes.id is None`` на первом реальном кадре — повтор без нового кадра."""
    results = model.track(frame, **kwargs)
    if not results or len(results[0].boxes) == 0:
        return results
    if results[0].boxes.id is None:
        results = model.track(frame, **kwargs)
    return results


@dataclass
class ClassifierOutput:
    """Результат YOLO-cls по кропу: вид, уверенность top1, энтропия и margin (#370)."""

    species_name: Optional[str]
    top1_confidence: float
    entropy: float
    top1_top2_margin: float


@dataclass
class DetectionResult:
    """Одна детекция: track_id, вид, confidence, bbox, crop (опционально)."""

    track_id: int
    detector_label: str
    class_name: Optional[str]
    confidence: float
    detector_confidence: float
    bbox: List[float]
    classifier_confidence: Optional[float] = None
    classifier_entropy: Optional[float] = None
    classifier_top1_top2_margin: Optional[float] = None
    blur_variance: Optional[float] = None
    crop: Optional[np.ndarray] = None


class DetectionStrategy(ABC):
    def __init__(
        self,
        min_center_dist: float = 0.1,
        min_box_size_px: int = 64,
        blur_threshold: float = 100.0,
        max_blur_checks: int = 3,
    ):
        self.min_center_dist = min_center_dist
        self.min_box_size_px = min_box_size_px
        self.blur_threshold = blur_threshold
        self.max_blur_checks = max_blur_checks

    def is_blurry(self, image: np.ndarray) -> Tuple[bool, float]:
        """Лапласиан: выше variance — резче. (is_blur, variance)."""
        if image is None or image.size == 0:
            return True, 0.0

        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        variance = cv2.Laplacian(gray, cv2.CV_64F).var()

        is_blur = variance < self.blur_threshold
        if is_blur:
            logger.info(f"Blur detected: variance={variance:.1f} < threshold={self.blur_threshold}")
        return is_blur, variance

    @abstractmethod
    def detect(
        self,
        frame: np.ndarray,
        tracker_config: str,
        min_confidence: float,
        profile_overrides: Mapping[str, Any] | None = None,
    ) -> List[DetectionResult]:
        pass

    @abstractmethod
    def reset(self):
        pass

    def is_valid_detection(
        self,
        bbox: List[float],
        conf: float,
        min_confidence: float,
        *,
        min_center_dist: float | None = None,
    ) -> bool:
        """Центр не у краёв, confidence >= min."""
        x1, y1, x2, y2 = bbox
        center_x = (x1 + x2) / 2
        center_y = (y1 + y2) / 2
        center_dist = self.min_center_dist if min_center_dist is None else float(min_center_dist)
        if (
            center_x < center_dist
            or center_x > (1 - center_dist)
            or center_y < center_dist
            or center_y > (1 - center_dist)
        ):
            return False
        if conf < min_confidence:
            return False

        return True


class TwoStageStrategy(DetectionStrategy):
    def __init__(
        self,
        binary_model_path: str,
        classifier_model_path: str,
        regional_species: Optional[List[str]] = None,
        detector_scope: Optional[List[str]] = None,
        min_center_dist: float = 0.1,
        min_box_size_px: int = 64,
        blur_threshold: float = 100.0,
        max_blur_checks: int = 3,
        max_classifications_per_frame: int = 2,
        classification_scheduler: str = "priority",
        binary_imgsz: int = 320,
        *,
        weight_contract_mode: str = "warn",
        inference_backend: str = "torch",
        classifier_inference_backend: str = "torch",
    ):
        super().__init__(min_center_dist, min_box_size_px, blur_threshold, max_blur_checks)
        self.logger = logging.getLogger(self.__class__.__name__)
        self.inference_backend = (inference_backend or "torch").strip().lower()
        self.classifier_inference_backend = (classifier_inference_backend or "torch").strip().lower()
        self.weight_contract_mode = (weight_contract_mode or "warn").strip().lower()
        self.regional_species = regional_species
        self.max_classifications_per_frame = max(1, int(max_classifications_per_frame or 1))
        self.classification_scheduler = str(classification_scheduler or "priority").strip().lower()
        self.binary_imgsz = max(320, int(binary_imgsz or 320))
        raw_scope = detector_scope or ["Bird", "Rodent"]
        self.detector_scope = {normalize_detector_label(name) for name in raw_scope if str(name or "").strip()}

        self.logger.info(
            "TwoStageStrategy: detector_backend=%s classifier_backend=%s detector_weight_contract=%s detector_scope=%s",
            self.inference_backend,
            self.classifier_inference_backend,
            self.weight_contract_mode,
            sorted(self.detector_scope),
        )

        if self.inference_backend in ("torch", "openvino") and self.classifier_inference_backend in (
            "torch",
            "openvino",
        ):
            self.binary_model = load_yolo_detector(
                binary_model_path,
                backend=self.inference_backend,
            )
            self.classifier_model = load_yolo_classifier(
                classifier_model_path,
                backend=self.classifier_inference_backend,
            )
        else:
            raise NotImplementedError(
                "inference backend is not implemented (#371): "
                f"detector={self.inference_backend!r}, "
                f"classifier={self.classifier_inference_backend!r}.",
            )

        validate_detector_weight_contract(
            getattr(self.binary_model, "names", None),
            self.detector_scope,
            self.weight_contract_mode,
            self.logger,
        )

        # Round-robin index for classification scheduling
        self._classification_index = 0
        self._frame_index = 0
        self._track_stats = {}

        # Pre-calculate allowed class IDs for regional species
        self.classes = None
        if self.regional_species:
            self.logger.info(
                "Initializing with regional species filters: %s",
                self.regional_species,
            )
            self.classes = _regional_class_ids(self.classifier_model.names, self.regional_species)
            enabled_classes = [self._normalize_class_name(self.classifier_model.names[i]) for i in self.classes]
            self.logger.info(
                "Regional species filters active: %s classes enabled.",
                len(self.classes),
            )
            self.logger.info("Enabled classes: %s", enabled_classes)

        # Warmup
        self.binary_model.track(
            np.zeros((320, 320, 3), dtype=np.uint8), tracker="bytetrack.yaml", persist=True, verbose=False
        )
        self.classifier_model(np.zeros((224, 224, 3), dtype=np.uint8), verbose=False)

    def _normalize_class_name(self, name: str) -> str:
        """Blue_Jay → Blue Jay, Winter_OR_juvenile → Winter/juvenile."""
        return name.replace("_OR_", "/").replace("_", " ")

    def _normalize_detector_label(self, name: str) -> str:
        return normalize_detector_label(name)

    def _classify_crop(self, crop: np.ndarray) -> ClassifierOutput:
        """Классификация кропа: вид, top1 conf, энтропия и top1−top2 margin по полному вектору probs."""
        result_cls = self.classifier_model(crop, verbose=False)

        if not result_cls or not result_cls[0].probs:
            return ClassifierOutput(None, 0.0, 0.0, 0.0)

        probs = result_cls[0].probs
        ent, margin = entropy_and_margin_from_prob_vector(probs.data)

        if self.classes:
            # Filter for best regional species
            all_probs = probs.data
            valid_probs = {cid: all_probs[cid].item() for cid in self.classes if cid < len(all_probs)}

            if valid_probs:
                best_id, best_conf = max(valid_probs.items(), key=lambda x: x[1])
                return ClassifierOutput(
                    self._normalize_class_name(result_cls[0].names[best_id]),
                    float(best_conf),
                    ent,
                    margin,
                )
            return ClassifierOutput("Unknown", 0.0, ent, margin)

        top1_idx = probs.top1
        return ClassifierOutput(
            self._normalize_class_name(result_cls[0].names[top1_idx]),
            float(probs.top1conf.item()),
            ent,
            margin,
        )

    def _priority_score(self, box: dict) -> tuple:
        stats = self._track_stats.get(box["track_id"]) or {}
        classified_count = int(stats.get("classified_count") or 0)
        last_classified_frame = int(stats.get("last_classified_frame") or -1)
        frames_since_classified = (
            self._frame_index - last_classified_frame if last_classified_frame >= 0 else self._frame_index + 1
        )
        novelty_boost = 2 if classified_count == 0 else 0
        scarcity_boost = max(0, 3 - classified_count)
        return (
            novelty_boost,
            scarcity_boost,
            frames_since_classified,
            float(box.get("box_area_norm") or 0.0),
            float(box.get("conf") or 0.0),
            -int(box.get("track_id") or 0),
        )

    def detect(
        self,
        frame: np.ndarray,
        tracker_config: str,
        min_confidence: float,
        profile_overrides: Mapping[str, Any] | None = None,
    ) -> List[DetectionResult]:
        """Binary detect -> validate -> classify a bounded round-robin slice of tracks."""
        from app_config.app_config import app_config

        runtime_cfg = RuntimeProfileConfigOverlay(app_config, profile_overrides)
        if not hasattr(self, "_frame_index"):
            self._frame_index = 0
        if not hasattr(self, "_track_stats"):
            self._track_stats = {}
        if not hasattr(self, "classification_scheduler"):
            self.classification_scheduler = "priority"
        self._frame_index += 1
        imgsz = int(runtime_cfg.resolve_strategy_field("processor.binary_imgsz", self, "binary_imgsz", 320) or 320)
        min_center_dist = float(
            runtime_cfg.resolve_strategy_field("processor.min_center_dist", self, "min_center_dist", 0.1) or 0.1
        )
        min_box_size_px = int(
            runtime_cfg.resolve_strategy_field("processor.min_box_size_px", self, "min_box_size_px", 64) or 64
        )
        classification_budget_limit = int(
            runtime_cfg.resolve_strategy_field(
                "processor.max_classifications_per_frame",
                self,
                "max_classifications_per_frame",
                1,
            )
            or 1
        )
        track_conf = binary_track_ultralytics_conf_floor(min_confidence, runtime_cfg)
        results = _track_maybe_retry(
            self.binary_model,
            frame,
            persist=True,
            conf=track_conf,
            verbose=False,
            imgsz=imgsz,
            tracker=tracker_config,
        )

        if not results or len(results[0].boxes) == 0:
            return []

        boxes = results[0].boxes
        # Without stable ByteTrack IDs, per-frame indexes create fake tracks.
        if boxes.id is None:
            return []
        track_ids = boxes.id.int().cpu().tolist()
        class_indexes = boxes.cls.int().cpu().tolist()
        confidences = boxes.conf.cpu().tolist()
        xyxyn = boxes.xyxyn.cpu().numpy()  # normalized for output
        xyxy = boxes.xyxy.cpu().numpy()  # absolute for cropping

        h, w, _ = frame.shape

        valid_boxes = []
        for track_id, class_idx, conf, bbox_norm, bbox_abs in zip(track_ids, class_indexes, confidences, xyxyn, xyxy):
            detector_name = self.binary_model.names[class_idx]
            detector_label = self._normalize_detector_label(detector_name)
            eff_min = per_label_binary_conf_threshold(
                detector_label,
                min_confidence,
                runtime_cfg,
            )
            if not self.is_valid_detection(
                bbox_norm,
                conf,
                eff_min,
                min_center_dist=min_center_dist,
            ):
                continue
            if self.detector_scope and detector_label not in self.detector_scope:
                continue

            x1, y1, x2, y2 = map(int, bbox_abs)
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(w, x2), min(h, y2)

            if x2 <= x1 or y2 <= y1:
                continue
            box_w = x2 - x1
            box_h = y2 - y1
            if box_w < min_box_size_px or box_h < min_box_size_px:
                continue

            valid_boxes.append(
                {
                    "track_id": track_id,
                    "detector_label": detector_label,
                    "conf": conf,
                    "bbox_norm": bbox_norm,
                    "crop_coords": (x1, y1, x2, y2),
                    "box_area_norm": max(0.0, float(bbox_norm[2] - bbox_norm[0]))
                    * max(0.0, float(bbox_norm[3] - bbox_norm[1])),
                }
            )

        if not valid_boxes:
            return []
        classification_budget = min(
            len(valid_boxes),
            max(1, classification_budget_limit),
        )
        if self.classification_scheduler == "round_robin":
            valid_boxes.sort(key=lambda b: b["track_id"])
            start_idx = self._classification_index % len(valid_boxes)
            self._classification_index = (self._classification_index + classification_budget) % len(valid_boxes)
            scheduled_boxes = [valid_boxes[(start_idx + i) % len(valid_boxes)] for i in range(len(valid_boxes))]
        else:
            scheduled_boxes = sorted(
                valid_boxes,
                key=self._priority_score,
                reverse=True,
            )
        scan_limit = min(
            len(scheduled_boxes),
            max(1, int(getattr(self, "max_blur_checks", 1) or 1)),
        )
        classified_by_track = {}
        fallback_box = None
        for box in scheduled_boxes[:scan_limit]:
            if should_skip_bird_species_classifier(
                box["detector_label"],
                box["box_area_norm"],
                runtime_cfg,
            ):
                continue
            if fallback_box is None:
                fallback_box = box
            x1, y1, x2, y2 = box["crop_coords"]
            crop = frame[y1:y2, x1:x2]
            is_blur, variance = self.is_blurry(crop)
            if is_blur:
                continue
            classified_by_track[box["track_id"]] = {
                "crop": crop.copy(),
                "blur_variance": variance,
            }
            if len(classified_by_track) >= classification_budget:
                break
        if not classified_by_track and fallback_box is not None:
            x1, y1, x2, y2 = fallback_box["crop_coords"]
            crop = frame[y1:y2, x1:x2]
            _, variance = self.is_blurry(crop)
            classified_by_track[fallback_box["track_id"]] = {
                "crop": crop.copy(),
                "blur_variance": variance,
            }
        for box in valid_boxes:
            stats = self._track_stats.setdefault(
                box["track_id"],
                {"classified_count": 0, "last_classified_frame": -1},
            )
            if box["track_id"] in classified_by_track:
                stats["classified_count"] = int(stats.get("classified_count") or 0) + 1
                stats["last_classified_frame"] = self._frame_index
        detection_results = []
        for box in valid_boxes:
            species_name = None
            crop = None
            blur_variance = None
            combined_conf = box["conf"]  # Default to detector confidence
            classifier_conf = None

            classified = classified_by_track.get(box["track_id"])
            if classified and should_skip_bird_species_classifier(
                box["detector_label"],
                box["box_area_norm"],
                runtime_cfg,
            ):
                classified = None
            co: ClassifierOutput | None = None
            if classified:
                co = self._classify_crop(classified["crop"])
                species_name = co.species_name
                cls_conf = co.top1_confidence
                classifier_conf = cls_conf
                combined_conf = box["conf"] * cls_conf

                crop = classified["crop"]
                blur_variance = classified["blur_variance"]

            detection_results.append(
                DetectionResult(
                    track_id=box["track_id"],
                    detector_label=box["detector_label"],
                    class_name=species_name,
                    confidence=combined_conf,
                    detector_confidence=box["conf"],
                    classifier_confidence=classifier_conf,
                    classifier_entropy=(co.entropy if co else None),
                    classifier_top1_top2_margin=(co.top1_top2_margin if co else None),
                    bbox=box["bbox_norm"],
                    blur_variance=blur_variance,
                    crop=crop,
                )
            )

        return detection_results

    def reset(self):
        self._classification_index = 0
        self._frame_index = 0
        self._track_stats = {}
        if hasattr(self.binary_model.predictor, "trackers"):
            self.binary_model.predictor.trackers[0].reset()
