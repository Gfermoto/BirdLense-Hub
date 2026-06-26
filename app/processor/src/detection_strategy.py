from abc import ABC, abstractmethod
from collections import deque
import logging
import math
import threading
import time
from pathlib import Path
from typing import Any, List, Mapping, Optional, Sequence, Tuple
from dataclasses import dataclass
import numpy as np
import cv2
from detector_labels import (
    detector_native_class_labels_enabled,
    normalize_detector_label,
    resolve_detector_scope_set,
)
from ultralytics import YOLO
from inference.weight_contract import validate_detector_weight_contract
from processor_runtime_profile import RuntimeProfileConfigOverlay
from roi_super_resolution import build_roi_super_resolution
from detection_quality import DetectionQualityConfig, DetectionQualityPipeline
from processor_backpressure import (
    record_classification_queue_drop,
    record_classification_queue_state,
)
from roi_crop import RoiCropRef, crop_for_classifier, roi_crop_ref_from_norm_bbox

logger = logging.getLogger(__name__)


def coerce_bgr_frame(
    frame: Any,
    *,
    log_label: str = "classification_frame",
) -> np.ndarray | None:
    """Validate/coerce a BGR uint8 frame for classifier crops; None → caller uses detector frame."""
    if frame is None:
        return None
    try:
        arr = frame if isinstance(frame, np.ndarray) else np.asarray(frame)
    except Exception:
        logger.warning("%s: cannot convert to ndarray", log_label)
        return None
    if arr.size == 0:
        logger.warning("%s: empty frame array", log_label)
        return None
    try:
        if arr.ndim == 2:
            arr = cv2.cvtColor(arr, cv2.COLOR_GRAY2BGR)
        elif arr.ndim == 3:
            channels = int(arr.shape[2])
            if channels == 4:
                arr = cv2.cvtColor(arr, cv2.COLOR_BGRA2BGR)
            elif channels == 1:
                arr = cv2.cvtColor(arr.reshape(arr.shape[0], arr.shape[1]), cv2.COLOR_GRAY2BGR)
            elif channels != 3:
                logger.warning(
                    "%s: expected 1/3/4 channels, got %s (shape=%s)",
                    log_label,
                    channels,
                    arr.shape,
                )
                return None
        else:
            logger.warning("%s: invalid ndim=%s shape=%s", log_label, arr.ndim, arr.shape)
            return None
        if arr.dtype != np.uint8:
            if np.issubdtype(arr.dtype, np.floating):
                scale = 255.0 if float(np.nanmax(arr)) <= 1.0 else 1.0
                arr = np.clip(arr * scale, 0, 255).astype(np.uint8)
            else:
                arr = np.clip(arr, 0, 255).astype(np.uint8)
        h, w = int(arr.shape[0]), int(arr.shape[1])
        if h < 8 or w < 8:
            logger.warning("%s: frame too small (%dx%d)", log_label, w, h)
            return None
        return np.ascontiguousarray(arr)
    except Exception:
        logger.warning("%s: frame validation failed", log_label, exc_info=True)
        return None


def resolve_classifier_crop_frame(
    detect_frame: np.ndarray,
    classification_frame: Any,
    *,
    profile_overrides: Mapping[str, Any] | None = None,
) -> np.ndarray:
    """Pick classifier crop source; on sync mismatch fall back to detect frame + metric."""
    mismatch = bool((profile_overrides or {}).get("_classifier_crop_source_mismatch"))
    if mismatch:
        try:
            from processor_runtime_stats import inc_counter

            inc_counter("classifier_crop_source_mismatch_total", 1)
        except Exception:
            logger.debug("classifier_crop_source_mismatch counter failed", exc_info=True)
        return detect_frame
    coerced = coerce_bgr_frame(classification_frame, log_label="classification_frame")
    return detect_frame if coerced is None else coerced


def _rodent_binary_threshold_raw(config: Mapping[str, Any]) -> Any:
    """Порог для белки/грызунов (legacy Rodent + Trapper ``Eurasian Red Squirrel``)."""
    raw = config.get("processor.min_confidence_binary_rodent")
    if raw is not None:
        return raw
    return config.get("processor.min_confidence_binary_squirrel")


def _is_squirrel_detector_label(detector_label: str) -> bool:
    """Trapper native: ``Eurasian Red Squirrel``; legacy: Rodent / Squirrel."""
    d = " ".join(str(detector_label or "").strip().lower().split())
    if d in ("rodent", "squirrel"):
        return True
    return "squirrel" in d


def _parse_optional_processor_float(config: Mapping[str, Any], key: str) -> float | None:
    raw = config.get(key)
    if raw is None:
        return None
    if isinstance(raw, str) and raw.strip().lower() in ("", "null", "none"):
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None




def build_binary_track_ultralytics_extras(runtime_cfg: Mapping[str, Any]) -> dict[str, float | int]:
    """Доп. аргументы для ``YOLO.track()`` / NMS: ``iou``, ``max_det``.

    Пустые/null в конфиге — ключ не передаём (поведение Ultralytics по умолчанию).
    """
    extras: dict[str, float | int] = {}
    raw_iou = runtime_cfg.get("processor.binary_track_iou")
    if raw_iou is not None and raw_iou != "":
        try:
            v = float(raw_iou)
            if 0.05 <= v <= 0.95:
                extras["iou"] = v
        except (TypeError, ValueError):
            pass
    raw_md = runtime_cfg.get("processor.binary_track_max_det")
    if raw_md is not None and raw_md != "":
        try:
            v = int(raw_md)
            if 1 <= v <= 1000:
                extras["max_det"] = v
        except (TypeError, ValueError):
            pass
    return extras


def binary_track_ultralytics_conf_floor(
    base_min: float,
    config: Mapping[str, Any],
    *,
    inference_backend: str | None = None,
) -> float:
    """
    Минимальный ``conf`` для YOLO ``track()``, чтобы кандидаты не отсекались до per-label фильтра.

    Если заданы отдельные пороги Bird/Rodent, берётся min(...) с базовым — иначе жёсткий
    порог на птицу отбросил бы грызунов на этапе движка.

    ``config`` — ``app_config`` или ``RuntimeProfileConfigOverlay`` (ночные overrides для ``processor.*``).
    """
    try:
        base = float(base_min)
    except (TypeError, ValueError):
        base = 0.22
    b_raw = config.get("processor.min_confidence_binary_bird")
    s_raw = _rodent_binary_threshold_raw(config)
    bird_m = float(b_raw) if b_raw is not None else base
    rod_m = float(s_raw) if s_raw is not None else base
    stock = min(base, bird_m, rod_m)
    return stock


def per_label_binary_conf_threshold(
    detector_label: str,
    base_min: float,
    config: Mapping[str, Any],
    *,
    inference_backend: str | None = None,
) -> float:
    """Порог confidence бинарника после нормализации метки (Bird / Rodent)."""
    try:
        base = float(base_min)
    except (TypeError, ValueError):
        base = 0.22
    b_raw = config.get("processor.min_confidence_binary_bird")
    s_raw = _rodent_binary_threshold_raw(config)
    bird_m = float(b_raw) if b_raw is not None else base
    rod_m = float(s_raw) if s_raw is not None else base
    if detector_label == "Bird":
        return bird_m
    if _is_squirrel_detector_label(detector_label):
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


def _track_maybe_retry(
    model,
    frame: np.ndarray,
    **kwargs,
):
    """ByteTrack иногда возвращает ``boxes.id is None`` — повтор."""
    results = model.track(frame, **kwargs)
    if not results or len(results[0].boxes) == 0:
        return results
    if results[0].boxes.id is not None:
        return results
    results = model.track(frame, **kwargs)
    return results


def _bbox_iou_xyxy(a: np.ndarray, b: np.ndarray) -> float:
    """IoU двух bbox в координатах xyxy (абсолютные или нормализованные — размерность одна и та же)."""
    ax1, ay1, ax2, ay2 = (float(v) for v in np.asarray(a).reshape(4))
    bx1, by1, bx2, by2 = (float(v) for v in np.asarray(b).reshape(4))
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
    inter = iw * ih
    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    union = area_a + area_b - inter
    return float(inter / union) if union > 0 else 0.0


def _greedy_match_iou_track_ids(
    prev: np.ndarray,
    prev_ids: Sequence[int],
    curr: np.ndarray,
    *,
    iou_thr: float = 0.25,
    next_id: int,
) -> tuple[list[int], int]:
    """
    Сопоставить текущие боксы с предыдущим кадром по greedy IoU; при низком пересечении выдать новые id.

    Используется только в офлайне track-regen (#201), когда ByteTrack временно отдаёт ``boxes.id is None``.
    """
    prev = np.asarray(prev, dtype=np.float64).reshape(-1, 4)
    curr_arr = np.asarray(curr, dtype=np.float64).reshape(-1, 4)
    pids = [int(x) for x in prev_ids]
    nid = int(next_id)
    thr = float(iou_thr)
    if prev.shape[0] == 0 or len(pids) != prev.shape[0]:
        out = list(range(nid, nid + curr_arr.shape[0]))
        return out, nid + curr_arr.shape[0]
    out_ids: list[int] = []
    used_prev = set()
    for ci in range(curr_arr.shape[0]):
        best_j: int | None = None
        best_iou = -1.0
        for j in range(prev.shape[0]):
            if j in used_prev:
                continue
            iou_val = _bbox_iou_xyxy(prev[j], curr_arr[ci])
            if iou_val >= thr and iou_val > best_iou:
                best_j, best_iou = j, iou_val
        if best_j is not None:
            used_prev.add(best_j)
            out_ids.append(pids[best_j])
        else:
            out_ids.append(nid)
            nid += 1
    return out_ids, nid


def _crop_coords_from_letterboxed_bbox_norm(
    *,
    bbox_norm: Sequence[float],
    detector_frame_shape: Sequence[int],
    overlay_frame_shape: Sequence[int],
    classification_frame_shape: Sequence[int],
    playback_frame_shape: Sequence[int] | None = None,
) -> tuple[int, int, int, int] | None:
    """Map normalized bbox from detector letterbox space to classification frame space."""
    from frame_geometry import remap_norm_bbox_for_crop

    mapped = remap_norm_bbox_for_crop(
        bbox_norm,
        detector_shape_hw=detector_frame_shape[:2],
        overlay_shape_hw=overlay_frame_shape[:2],
        crop_shape_hw=classification_frame_shape[:2],
        playback_shape_hw=playback_frame_shape[:2] if playback_frame_shape is not None else None,
    )
    if mapped is None:
        return None
    try:
        cls_h, cls_w = int(classification_frame_shape[0]), int(classification_frame_shape[1])
    except Exception:
        return None
    if cls_h <= 0 or cls_w <= 0:
        return None
    x1 = int(max(0, min(cls_w, round(float(mapped[0]) * cls_w))))
    y1 = int(max(0, min(cls_h, round(float(mapped[1]) * cls_h))))
    x2 = int(max(0, min(cls_w, round(float(mapped[2]) * cls_w))))
    y2 = int(max(0, min(cls_h, round(float(mapped[3]) * cls_h))))
    if x2 <= x1 or y2 <= y1:
        return None
    return x1, y1, x2, y2


def _storage_bbox_norm_for_overlay(
    bbox_norm: Sequence[float],
    *,
    detector_frame_shape: Sequence[int],
    overlay_frame_shape: Sequence[int],
    playback_frame_shape: Sequence[int] | None = None,
) -> list[float]:
    """Bbox для UI/БД: xyxy norm на кадре записи (main stream), не detect/letterbox."""
    from yolo_geometry import (
        map_norm_bbox_xyxy_between_frame_shapes,
        unmap_letterbox_norm_xyxy_to_source_norm_xyxy,
    )

    capture_norm: list[float]
    if (
        len(detector_frame_shape) >= 2
        and len(overlay_frame_shape) >= 2
        and (
            int(detector_frame_shape[0]) != int(overlay_frame_shape[0])
            or int(detector_frame_shape[1]) != int(overlay_frame_shape[1])
        )
    ):
        mapped = unmap_letterbox_norm_xyxy_to_source_norm_xyxy(
            bbox_norm,
            source_shape=overlay_frame_shape[:2],
            letterbox_shape=detector_frame_shape[:2],
        )
        capture_norm = (
            [round(float(v), 6) for v in mapped] if mapped is not None else [round(float(b), 6) for b in bbox_norm]
        )
    else:
        capture_norm = [round(float(b), 6) for b in bbox_norm]

    if (
        playback_frame_shape
        and len(playback_frame_shape) >= 2
        and len(overlay_frame_shape) >= 2
        and (
            int(playback_frame_shape[0]) != int(overlay_frame_shape[0])
            or int(playback_frame_shape[1]) != int(overlay_frame_shape[1])
        )
    ):
        remapped = map_norm_bbox_xyxy_between_frame_shapes(
            capture_norm,
            from_shape_hw=overlay_frame_shape[:2],
            to_shape_hw=playback_frame_shape[:2],
        )
        if remapped is not None:
            return [round(float(v), 6) for v in remapped]
    return capture_norm


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
    scoring_review_only: bool = False


@dataclass
class ClassificationTask:
    track_id: int
    detector_label: str
    box_area_norm: float
    crop: "np.ndarray | RoiCropRef"
    blur_variance: float | None


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
        self._playback_frame_shape_hw: tuple[int, int] | None = None

    def set_playback_frame_shape(self, shape_hw: tuple[int, int] | None) -> None:
        """Recorded MP4 dimensions (H, W) for bbox storage when detect ≠ record stream."""
        if shape_hw is None:
            self._playback_frame_shape_hw = None
            return
        try:
            h, w = int(shape_hw[0]), int(shape_hw[1])
        except (TypeError, ValueError, IndexError):
            self._playback_frame_shape_hw = None
            return
        if h > 0 and w > 0:
            self._playback_frame_shape_hw = (h, w)
        else:
            self._playback_frame_shape_hw = None

    def _playback_shape_for_storage(self) -> tuple[int, int] | None:
        return getattr(self, "_playback_frame_shape_hw", None)

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
        classification_frame: np.ndarray | None = None,
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
        max_box_area_norm: float | None = None,
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

        if max_box_area_norm is not None:
            try:
                area = max(0.0, float(x2) - float(x1)) * max(0.0, float(y2) - float(y1))
                if area > float(max_box_area_norm):
                    return False
            except (TypeError, ValueError):
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
        binary_inference_device: str | None = None,
        classifier_inference_device: str | None = None,
        classifier_engine: str = "birder_eu",
    ):
        super().__init__(min_center_dist, min_box_size_px, blur_threshold, max_blur_checks)
        self.logger = logging.getLogger(self.__class__.__name__)
        self.inference_backend = (inference_backend or "torch").strip().lower()
        self.classifier_inference_backend = (classifier_inference_backend or "torch").strip().lower()
        _dev = (binary_inference_device or "").strip()
        self._binary_track_device: str | None = _dev or None
        _cls_dev = (classifier_inference_device or "").strip()
        self._classifier_predict_device: str | None = _cls_dev or None
        self.weight_contract_mode = (weight_contract_mode or "warn").strip().lower()
        self.regional_species = regional_species
        self.max_classifications_per_frame = max(1, int(max_classifications_per_frame or 1))
        self.classification_scheduler = str(classification_scheduler or "priority").strip().lower()
        self.binary_imgsz = max(320, int(binary_imgsz or 320))
        self._binary_model_path = str(binary_model_path or "").strip() or None
        from app_config.app_config import app_config

        self._roi_sr = build_roi_super_resolution(app_config)
        self._detector_native_labels = detector_native_class_labels_enabled(app_config)
        self.detector_scope = resolve_detector_scope_set(detector_scope, app_config)
        scope_log = "ALL" if self.detector_scope is None else sorted(self.detector_scope)

        self._classifier_engine = (classifier_engine or "birder_eu").strip().lower()
        self.logger.info(
            "TwoStageStrategy: detector_backend=%s classifier_engine=%s classifier_backend=%s "
            "detector_weight_contract=%s detector_scope=%s native_class_labels=%s",
            self.inference_backend,
            self._classifier_engine,
            self.classifier_inference_backend,
            self.weight_contract_mode,
            scope_log,
            self._detector_native_labels,
        )

        if self.inference_backend not in ("torch", "tensorrt"):
            raise NotImplementedError(
                f"Detector backend {self.inference_backend!r} is not implemented (#371).",
            )

        self.binary_model = YOLO(
            binary_model_path,
        )

        _cls_backends = ("torch", "onnxruntime")
        if self.classifier_inference_backend not in _cls_backends:
            raise NotImplementedError(
                f"Classifier backend {self.classifier_inference_backend!r} is not implemented (#371).",
            )

        self._classifier_is_efficientnet = False
        self._classifier_is_birder_eu = False
        if self._classifier_engine == "birder_eu":
            from inference.birder_eu_classifier import load_birder_eu_classifier

            self._classifier_is_birder_eu = True
            self.classifier_model = load_birder_eu_classifier(
                classifier_model_path,
                backend=self.classifier_inference_backend,
                device=_cls_dev or None,
                regional_species=self.regional_species,
                app_config=app_config,
            )
        elif self._classifier_engine == "efficientnet_b2":
            from inference.efficientnet_b2_classifier import load_efficientnet_b2_classifier

            self._classifier_is_efficientnet = True
            self.classifier_model = load_efficientnet_b2_classifier(
                classifier_model_path,
                backend=self.classifier_inference_backend,
                device=_cls_dev or None,
                regional_species=self.regional_species,
                app_config=app_config,
            )
        else:
            self.classifier_model = YOLO(
                classifier_model_path,
                task="classify",
            )

        validate_detector_weight_contract(
            getattr(self.binary_model, "names", None),
            self.detector_scope,
            self.weight_contract_mode,
            self.logger,
        )
        from processor_support import mark_yolo_inference_ready

        mark_yolo_inference_ready(self.inference_backend)

        # Round-robin index for classification scheduling
        self._classification_index = 0
        self._frame_index = 0
        self._track_stats = {}
        try:
            self._classification_task_queue_maxsize = int(
                app_config.get("processor.classifier_task_queue_maxsize") or 8
            )
        except (TypeError, ValueError):
            self._classification_task_queue_maxsize = 8
        self._classification_task_queue_maxsize = max(1, self._classification_task_queue_maxsize)
        self._classification_task_queue: deque[ClassificationTask] = deque()
        self._classification_task_drops_total = 0
        self._latest_cls_by_track: dict[int, ClassifierOutput] = {}
        self._classifier_async_enabled = False
        self._classifier_async_lock = threading.Lock()
        self._classifier_worker_stop = threading.Event()
        self._classifier_worker: threading.Thread | None = None
        if self._classifier_async_enabled:
            self._classifier_worker = threading.Thread(
                target=self._classifier_async_worker_loop,
                name="birdlense-classifier-async",
                daemon=True,
            )
            self._classifier_worker.start()
            self.logger.info("Classifier async worker started (detect path decoupled from classify).")

        # Pre-calculate allowed class IDs for regional species (YOLO-cls path only).
        self.classes = None
        if self.regional_species and not getattr(self, "_classifier_is_efficientnet", False):
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
        elif self.regional_species and (
            getattr(self, "_classifier_is_efficientnet", False) or getattr(self, "_classifier_is_birder_eu", False)
        ):
            self.logger.info(
                "Regional species filter delegated to neural classifier (%s entries).",
                len(self.regional_species),
            )

        # Warmup
        _warm: dict = {"tracker": "bytetrack.yaml", "persist": True, "verbose": False}
        if self._binary_track_device:
            _warm["device"] = self._binary_track_device
        self.binary_model.track(np.zeros((320, 320, 3), dtype=np.uint8), **_warm)
        if getattr(self, "_classifier_is_efficientnet", False) or getattr(self, "_classifier_is_birder_eu", False):
            self.classifier_model.warmup()
        else:
            _cls_warm: dict = {"verbose": False}
            if self._classifier_predict_device:
                _cls_warm["device"] = self._classifier_predict_device
            self.classifier_model(np.zeros((224, 224, 3), dtype=np.uint8), **_cls_warm)

    def _classifier_async_worker_loop(self) -> None:
        """Drain classification queue off the hot detect+track path."""
        while not self._classifier_worker_stop.is_set():
            if bool(getattr(self, "_for_track_regen", False)):
                time.sleep(0.05)
                continue
            task: ClassificationTask | None = None
            with self._classifier_async_lock:
                if self._classification_task_queue:
                    task = self._classification_task_queue.popleft()
            if task is None:
                time.sleep(0.015)
                continue
            try:
                co = self._classify_crop(task.crop)
            except Exception:
                logger.debug("Async classifier failed for track %s", task.track_id, exc_info=True)
                continue
            with self._classifier_async_lock:
                self._latest_cls_by_track[int(task.track_id)] = co
                stats = self._track_stats.setdefault(
                    int(task.track_id),
                    {"classified_count": 0, "last_classified_frame": -1},
                )
                stats["classified_count"] = int(stats.get("classified_count") or 0) + 1
                stats["last_classified_frame"] = int(getattr(self, "_frame_index", 0) or 0)

    def _normalize_class_name(self, name: str) -> str:
        """Blue_Jay → Blue Jay, Winter_OR_juvenile → Winter/juvenile."""
        return name.replace("_OR_", "/").replace("_", " ")

    def _normalize_detector_label(self, name: str) -> str:
        return normalize_detector_label(name, native=bool(getattr(self, "_detector_native_labels", False)))

    def _update_best_raw_bird_candidate(
        self,
        *,
        track_ids: Sequence[Any],
        class_indexes: Sequence[int],
        confidences: Sequence[float],
        xyxyn: np.ndarray,
    ) -> None:
        """Keep strongest bird bbox for detect-first raw-hits anchor salvage."""
        from track_first_contract import is_valid_norm_bbox

        best_conf = -1.0
        best: dict[str, Any] | None = None
        for track_id, class_idx, conf, bbox_norm in zip(track_ids, class_indexes, confidences, xyxyn):
            detector_label = self._normalize_detector_label(self.binary_model.names[class_idx])
            if detector_label != "Bird":
                continue
            try:
                bbox = [float(v) for v in bbox_norm[:4]]
            except (TypeError, ValueError, IndexError):
                continue
            if not is_valid_norm_bbox(bbox):
                continue
            cf = float(conf or 0.0)
            if cf <= best_conf:
                continue
            try:
                tid = int(track_id)
            except (TypeError, ValueError):
                tid = 1
            best_conf = cf
            best = {
                "track_id": tid if tid > 0 else 1,
                "bbox": bbox,
                "confidence": cf,
                "detector_label": "Bird",
            }
        if best is None:
            return
        prev = getattr(self, "_best_raw_bird_candidate", None)
        if not isinstance(prev, dict) or float(best["confidence"]) >= float(prev.get("confidence") or 0.0):
            self._best_raw_bird_candidate = best

    def get_best_raw_bird_candidate(self) -> dict[str, Any] | None:
        candidate = getattr(self, "_best_raw_bird_candidate", None)
        return dict(candidate) if isinstance(candidate, dict) else None

    def _binary_class_allowlist(self, runtime_cfg: Mapping[str, Any]) -> set[int] | None:
        """Классы бинарного детектора, которые разрешено передавать в predict/track (пустой конфиг → без фильтра)."""
        raw = runtime_cfg.get("processor.binary_predict_class_allowlist")
        if raw is None or (isinstance(raw, (list, tuple, set)) and len(raw) == 0):
            return None
        if not isinstance(raw, (list, tuple, set)):
            return None
        out: set[int] = set()
        for item in raw:
            try:
                out.add(int(item))
            except (TypeError, ValueError):
                continue
        return out if out else None

    def _extract_valid_box_crop(
        self,
        box: dict[str, Any],
        *,
        frame: np.ndarray,
        cls_frame: np.ndarray,
        min_box_size_px: int,
    ) -> tuple[np.ndarray | RoiCropRef | None, float | None]:
        """ROI crop for a valid box (no classifier call)."""
        det_shape = getattr(self, "_detector_frame_shape", frame.shape[:2])
        overlay_shape = getattr(self, "_overlay_frame_shape", frame.shape[:2])
        playback_shape = self._playback_shape_for_storage()
        mapped = _crop_coords_from_letterboxed_bbox_norm(
            bbox_norm=box["bbox_norm"],
            detector_frame_shape=det_shape,
            overlay_frame_shape=overlay_shape,
            classification_frame_shape=cls_frame.shape,
            playback_frame_shape=playback_shape,
        )
        if mapped is None:
            return None, None
        x1, y1, x2, y2 = mapped
        crop_ref = roi_crop_ref_from_norm_bbox(cls_frame, x1=x1, y1=y1, x2=x2, y2=y2)
        if crop_ref is None:
            return None, None
        crop_view = crop_ref.view()
        is_blur, variance = self.is_blurry(crop_view)
        if is_blur:
            return None, variance
        crop_sr, _, _ = self._apply_roi_sr_to_crop(crop_view, min_box_size_px=min_box_size_px)
        crop_payload: np.ndarray | RoiCropRef = crop_ref
        if crop_sr is not crop_view:
            crop_payload = crop_sr
        return crop_payload, variance

    def _classify_valid_box_crop(
        self,
        box: dict[str, Any],
        *,
        frame: np.ndarray,
        cls_frame: np.ndarray,
        min_box_size_px: int,
    ) -> tuple[ClassifierOutput | None, np.ndarray | RoiCropRef | None, float | None]:
        """Классификатор по боксу (если не попал в очередь кадра)."""
        crop_payload, variance = self._extract_valid_box_crop(
            box,
            frame=frame,
            cls_frame=cls_frame,
            min_box_size_px=min_box_size_px,
        )
        if crop_payload is None:
            return None, None, variance
        return self._classify_crop(crop_payload), crop_payload, variance

    def _classify_crop(self, crop: np.ndarray | RoiCropRef) -> ClassifierOutput:
        """Классификация кропа: вид, top1 conf, энтропия и top1−top2 margin по полному вектору probs."""
        crop_bgr, _copied = crop_for_classifier(crop)
        if crop_bgr.size == 0:
            return ClassifierOutput(None, 0.0, 0.0, 0.0)
        if getattr(self, "_classifier_is_efficientnet", False) or getattr(self, "_classifier_is_birder_eu", False):
            out = self.classifier_model.classify_crop_bgr(crop_bgr)
            return ClassifierOutput(
                out.species_name,
                float(out.top1_confidence),
                float(out.entropy),
                float(out.top1_top2_margin),
            )

        _cls_kwargs: dict = {"verbose": False}
        _cls_dev = getattr(self, "_classifier_predict_device", None)
        if _cls_dev:
            _cls_kwargs["device"] = _cls_dev
        result_cls = self.classifier_model(crop_bgr, **_cls_kwargs)

        if not result_cls or result_cls[0].probs is None:
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

    def _apply_roi_sr_to_crop(
        self,
        crop: np.ndarray,
        *,
        min_box_size_px: int,
    ) -> tuple[np.ndarray, int, float]:
        """ROI super-resolution when configured; no-op if builder returned None."""
        roi_sr = getattr(self, "_roi_sr", None)
        if roi_sr is None:
            return crop, 0, 0.0
        if not roi_sr.should_enhance(crop, min_box_size_px=min_box_size_px):
            return crop, 0, 0.0
        crop_sr, sr_meta = roi_sr.enhance(crop)
        applied = 1 if sr_meta.enabled else 0
        latency = float(sr_meta.latency_ms) if sr_meta.enabled else 0.0
        return crop_sr, applied, latency

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
        classification_frame: np.ndarray | None = None,
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
        if not hasattr(self, "_classification_task_queue_maxsize"):
            self._classification_task_queue_maxsize = 8
        if not hasattr(self, "_classification_task_queue"):
            self._classification_task_queue = deque()
        if not hasattr(self, "_classification_task_drops_total"):
            self._classification_task_drops_total = 0
        if not hasattr(self, "_latest_cls_by_track"):
            self._latest_cls_by_track = {}
        self._frame_index += 1
        inference_backend = str(getattr(self, "inference_backend", "torch") or "torch").strip().lower()
        from frame_geometry import prepare_yolo_detector_frame, resolve_binary_track_imgsz

        _pol = getattr(self, "_tracking_policy", None)
        if _pol is not None:
            _geom_mode = _pol.geometry_mode_for_frame()
        else:
            _geom_mode = "regen" if bool(getattr(self, "_for_track_regen", False)) else "live"
        overlay_bgr = np.ascontiguousarray(frame)
        det_frame, det_shape_hw, overlay_shape_hw = prepare_yolo_detector_frame(
            overlay_bgr,
            runtime_cfg,
            mode=_geom_mode,
        )
        self._detector_frame_shape = det_shape_hw
        self._overlay_frame_shape = overlay_shape_hw
        from frame_geometry import DetectorGeometry

        detect_geometry = DetectorGeometry(
            detector_shape_hw=tuple(det_shape_hw),
            overlay_shape_hw=tuple(overlay_shape_hw),
        )
        self._detect_geometry = detect_geometry
        frame = det_frame

        imgsz = resolve_binary_track_imgsz(
            frame,
            runtime_cfg,
            inference_backend=inference_backend,
            default_square=int(
                runtime_cfg.resolve_strategy_field("processor.binary_imgsz", self, "binary_imgsz", 320) or 320
            ),
        )
        min_center_dist = float(
            runtime_cfg.resolve_strategy_field("processor.min_center_dist", self, "min_center_dist", 0.1) or 0.1
        )
        max_box_area_norm = float(
            runtime_cfg.resolve_strategy_field("processor.max_box_area_norm", self, "max_box_area_norm", 1.0) or 1.0
        )
        min_box_size_px = int(
            runtime_cfg.resolve_strategy_field("processor.min_box_size_px", self, "min_box_size_px", 64) or 64
        )
        auto_small_object_relax_enabled = bool(runtime_cfg.get("processor.auto_small_object_relax_enabled", True))
        try:
            auto_small_object_relax_min_box_size_px = int(
                runtime_cfg.get("processor.auto_small_object_relax_min_box_size_px") or min_box_size_px
            )
        except (TypeError, ValueError):
            auto_small_object_relax_min_box_size_px = int(min_box_size_px)
        auto_small_object_relax_min_box_size_px = max(1, auto_small_object_relax_min_box_size_px)
        try:
            auto_small_object_relax_min_center_dist = float(
                runtime_cfg.get("processor.auto_small_object_relax_min_center_dist")
                if runtime_cfg.get("processor.auto_small_object_relax_min_center_dist") is not None
                else min_center_dist
            )
        except (TypeError, ValueError):
            auto_small_object_relax_min_center_dist = float(min_center_dist)
        auto_small_object_relax_min_center_dist = max(0.0, min(0.45, auto_small_object_relax_min_center_dist))
        try:
            auto_small_object_relax_conf_delta = float(
                runtime_cfg.get("processor.auto_small_object_relax_conf_delta") or 0.0
            )
        except (TypeError, ValueError):
            auto_small_object_relax_conf_delta = 0.0
        auto_small_object_relax_conf_delta = max(0.0, min(0.25, auto_small_object_relax_conf_delta))
        try:
            auto_small_object_relax_max_candidates = int(
                runtime_cfg.get("processor.auto_small_object_relax_max_candidates") or 2
            )
        except (TypeError, ValueError):
            auto_small_object_relax_max_candidates = 2
        auto_small_object_relax_max_candidates = max(1, min(8, auto_small_object_relax_max_candidates))
        classification_budget_limit = int(
            runtime_cfg.resolve_strategy_field(
                "processor.max_classifications_per_frame",
                self,
                "max_classifications_per_frame",
                1,
            )
            or 1
        )
        track_conf = binary_track_ultralytics_conf_floor(
            min_confidence,
            runtime_cfg,
            inference_backend=inference_backend,
        )
        try:
            from bytetrack_contract import log_bytetrack_conf_contract_once

            _assumed_fps = float(runtime_cfg.get("processor.detection_quality_assumed_fps") or 7.0)
            log_bytetrack_conf_contract_once(
                tracker_config,
                float(track_conf),
                stream_fps=_assumed_fps,
            )
        except ImportError:
            pass
        # Post-track filters must not discard boxes that track() already admitted at track_conf.
        accept_min_confidence = min(float(min_confidence), float(track_conf))
        boxes_from_predict_fallback = False
        track_regen_ctx = bool(getattr(self, "_for_track_regen", False))
        if _pol is not None:
            track_regen_ctx = bool(_pol.for_track_regen)
            iou_fb = bool(_pol.use_regen_direct_track_call)
        else:
            iou_fb = bool(runtime_cfg.get("processor.track_regen_iou_id_fallback", False))
        _tkw: dict = {
            "persist": True,
            "conf": track_conf,
            "verbose": False,
            "imgsz": imgsz,
            "tracker": tracker_config,
        }
        _tkw.update(build_binary_track_ultralytics_extras(runtime_cfg))
        _allow = self._binary_class_allowlist(runtime_cfg)
        if _allow is not None:
            _tkw["classes"] = sorted(_allow)
        _bdev = getattr(self, "_binary_track_device", None)
        if _bdev:
            _tkw["device"] = _bdev
        results = (
            self.binary_model.track(frame, **_tkw)
            if track_regen_ctx and iou_fb
            else _track_maybe_retry(
                self.binary_model,
                frame,
                **_tkw,
            )
        )

        _quality_reject_stats: dict[str, int] = {}
        frame_copy_count = 0

        def _record_detect_metrics(
            *,
            raw_boxes: int,
            boxes_with_track_id: int,
            accepted: int,
            predict_fallback: bool = False,
            sr_applied: int = 0,
            sr_latency_ms: float = 0.0,
            quality_reject: Mapping[str, int] | None = None,
        ) -> None:
            qr = dict(quality_reject or _quality_reject_stats)
            self.last_detect_metrics = {
                "raw_boxes": int(raw_boxes),
                "boxes_with_track_id": int(boxes_with_track_id),
                "accepted": int(accepted),
                "predict_fallback": bool(predict_fallback),
                "sr_applied": int(sr_applied),
                "sr_latency_ms": round(float(sr_latency_ms), 3),
                "rejected_static_objects": int(qr.get("rejected_static_objects") or 0),
                "rejected_phantom_boxes": int(qr.get("rejected_phantom_boxes") or 0),
                "rejected_ignore_mask": int(qr.get("rejected_ignore_mask") or 0),
                "rejected_interest_zone": int(qr.get("rejected_interest_zone") or 0),
                "rejected_motion_verified": int(qr.get("rejected_motion_verified") or 0),
                "rejected_global_static": int(qr.get("rejected_global_static") or 0),
                "rejected_texture": int(qr.get("rejected_texture") or 0),
                "rejected_background_subtraction": int(qr.get("rejected_background_subtraction") or 0),
                "hard_negatives_saved": int(qr.get("hard_negatives_saved") or 0),
                "scoring_accepted": int(qr.get("scoring_accepted") or 0),
                "scoring_review": int(qr.get("scoring_review") or 0),
                "scoring_rejected": int(qr.get("scoring_rejected") or 0),
                "frame_copy_count_per_frame": int(frame_copy_count),
                "classification_queue_depth": int(len(self._classification_task_queue)),
                "classification_queue_drops_total": int(self._classification_task_drops_total),
            }
            record_classification_queue_state(
                depth=len(self._classification_task_queue),
                maxsize=self._classification_task_queue_maxsize,
                drops_total=self._classification_task_drops_total,
            )

        boxes = None
        if results and len(results[0].boxes) > 0:
            boxes = results[0].boxes
        else:
            fallback_enabled = bool(
                runtime_cfg.get(
                    "processor.track_to_predict_fallback_enabled",
                    False,
                )
            )
            if not fallback_enabled:
                _record_detect_metrics(raw_boxes=0, boxes_with_track_id=0, accepted=0)
                return []
            try:
                fallback_conf = float(runtime_cfg.get("processor.track_to_predict_fallback_confidence") or 0.005)
            except (TypeError, ValueError):
                fallback_conf = 0.005
            _pkw: dict[str, Any] = {
                "verbose": False,
                "imgsz": imgsz,
                "conf": max(0.001, min(0.20, fallback_conf)),
            }
            if _allow is not None:
                _pkw["classes"] = sorted(_allow)
            if _bdev:
                _pkw["device"] = _bdev
            pred = self.binary_model.predict(frame, **_pkw)
            if not pred or len(pred[0].boxes) == 0:
                _record_detect_metrics(raw_boxes=0, boxes_with_track_id=0, accepted=0)
                return []
            boxes = pred[0].boxes
            boxes_from_predict_fallback = True
            accept_min_confidence = min(
                float(min_confidence),
                max(float(fallback_conf) * 4.0, 0.04),
            )
            self._track_predict_fallback_hits = int(getattr(self, "_track_predict_fallback_hits", 0)) + 1
            if self._track_predict_fallback_hits <= 3 or self._track_predict_fallback_hits % 60 == 0:
                logger.warning(
                    "Track->predict fallback recovered %s box(es) without ByteTrack ids. hits=%s",
                    len(boxes),
                    self._track_predict_fallback_hits,
                )

        if boxes.id is None and len(boxes) > 0 and not (track_regen_ctx and iou_fb):
            logger.warning(
                "ByteTrack: %s box(es) but no track ids after retry (live). "
                "Usually tracker track_high_thresh/new_track_thresh in %r exceed YOLO track(conf=%.3f). "
                "Keep high/new ~0.02 below that conf; raise min_confidence_binary floors if you tighten YAML.",
                len(boxes),
                tracker_config,
                float(track_conf),
            )

        def _tensor_to_numpy(tensor_like):
            """Ultralytics torch tensor или unittest fake с ``.numpy()``."""
            prox = tensor_like.cpu() if hasattr(tensor_like, "cpu") else tensor_like
            if hasattr(prox, "numpy"):
                return np.asarray(prox.numpy(), dtype=np.float64)
            return np.asarray(prox, dtype=np.float64)

        # Without stable ByteTrack IDs, per-frame indexes create fake tracks.
        # В live-камере и тестах без track-regen — пустой кадр; в офлайне — IoU-синтез id (#201).
        if boxes.id is None:
            if _pol is not None:
                live_iou_fb = bool(_pol.iou_id_fallback)
                iou_thr = float(_pol.iou_match_threshold)
            else:
                live_iou_fb = bool(runtime_cfg.get("processor.iou_id_fallback_live_enabled", True))
                iou_thr_raw = (
                    runtime_cfg.get("processor.track_regen_iou_match_threshold")
                    if track_regen_ctx
                    else runtime_cfg.get("processor.iou_id_fallback_live_match_threshold")
                )
                try:
                    iou_thr = float(iou_thr_raw) if iou_thr_raw is not None else (0.22 if track_regen_ctx else 0.20)
                except (TypeError, ValueError):
                    iou_thr = 0.22 if track_regen_ctx else 0.20
            if not (track_regen_ctx and iou_fb) and not live_iou_fb:
                _record_detect_metrics(
                    raw_boxes=len(boxes),
                    boxes_with_track_id=0,
                    accepted=0,
                    predict_fallback=boxes_from_predict_fallback,
                )
                return []
            try:
                curr_xyxy = np.reshape(_tensor_to_numpy(boxes.xyxy), (-1, 4))
            except Exception:
                _record_detect_metrics(
                    raw_boxes=len(boxes),
                    boxes_with_track_id=0,
                    accepted=0,
                    predict_fallback=boxes_from_predict_fallback,
                )
                return []
            if track_regen_ctx:
                prev_boxes = getattr(self, "_regen_iou_prev_boxes", None)
                prev_ids = getattr(self, "_regen_iou_prev_ids", None)
                nid_seed = int(getattr(self, "_regen_iou_next_id", 1))
            else:
                prev_boxes = getattr(self, "_live_iou_prev_boxes", None)
                prev_ids = getattr(self, "_live_iou_prev_ids", None)
                nid_seed = int(getattr(self, "_live_iou_next_id", 1))
            if prev_boxes is None or prev_ids is None:
                synth = list(range(nid_seed, nid_seed + len(curr_xyxy)))
                nid_next = nid_seed + len(curr_xyxy)
            else:
                synth, nid_next = _greedy_match_iou_track_ids(
                    prev_boxes,
                    prev_ids,
                    curr_xyxy,
                    iou_thr=iou_thr,
                    next_id=nid_seed,
                )
            if track_regen_ctx:
                self._regen_iou_prev_boxes = curr_xyxy.copy()
                frame_copy_count += 1
                self._regen_iou_prev_ids = list(synth)
                self._regen_iou_next_id = int(nid_next)
            else:
                self._live_iou_prev_boxes = curr_xyxy.copy()
                frame_copy_count += 1
                self._live_iou_prev_ids = list(synth)
                self._live_iou_next_id = int(nid_next)
            track_ids = synth
        else:
            track_ids = boxes.id.int().cpu().tolist()

        class_indexes = boxes.cls.int().cpu().tolist()
        confidences = boxes.conf.cpu().tolist()
        xyxyn = _tensor_to_numpy(boxes.xyxyn)
        xyxy = np.reshape(_tensor_to_numpy(boxes.xyxy), (-1, 4))
        overlay_hw = tuple(getattr(self, "_overlay_frame_shape", frame.shape[:2]))
        det_hw = tuple(getattr(self, "_detector_frame_shape", frame.shape[:2]))
        if len(xyxy) > 0:
            from bbox_iou_gate import apply_bbox_geometry_iou_gate

            xyxy, self._bbox_iou_gate_stats, keep_idx = apply_bbox_geometry_iou_gate(
                xyxy,
                detector_shape_hw=det_hw,
                overlay_shape_hw=overlay_hw,
                runtime_cfg=runtime_cfg,
            )
            if len(xyxy) == 0:
                _record_detect_metrics(
                    raw_boxes=len(boxes),
                    boxes_with_track_id=0,
                    accepted=0,
                    predict_fallback=boxes_from_predict_fallback,
                    quality_reject={"rejected_geometry_iou": len(boxes)},
                )
                return []
            if len(keep_idx) != len(track_ids):
                track_ids = [track_ids[i] for i in keep_idx]
                class_indexes = [class_indexes[i] for i in keep_idx]
                confidences = [confidences[i] for i in keep_idx]
                xyxyn = xyxyn[keep_idx]

        self._update_best_raw_bird_candidate(
            track_ids=track_ids,
            class_indexes=class_indexes,
            confidences=confidences,
            xyxyn=xyxyn,
        )

        h, w, _ = frame.shape
        cls_frame = resolve_classifier_crop_frame(
            frame,
            classification_frame,
            profile_overrides=profile_overrides,
        )
        from frame_geometry import bbox_norm_detector_to_overlay

        detect_geometry = getattr(self, "_detect_geometry", None)
        overlay_hw = tuple(getattr(self, "_overlay_frame_shape", frame.shape[:2]))
        det_hw = tuple(getattr(self, "_detector_frame_shape", frame.shape[:2]))

        def _overlay_norm_bbox(bbox_norm: Sequence[float]) -> tuple[float, float, float, float]:
            if detect_geometry is not None and detect_geometry.letterbox_active:
                mapped = bbox_norm_detector_to_overlay(bbox_norm, geometry=detect_geometry)
                if mapped is not None:
                    return mapped
            return (
                float(bbox_norm[0]),
                float(bbox_norm[1]),
                float(bbox_norm[2]),
                float(bbox_norm[3]),
            )

        if not hasattr(self, "_detection_quality") or self._detection_quality is None:
            self._detection_quality = DetectionQualityPipeline(
                DetectionQualityConfig.from_runtime_cfg(runtime_cfg),
                runtime_cfg=runtime_cfg,
            )
        else:
            self._detection_quality.sync_from_runtime_cfg(runtime_cfg)
        self._detection_quality.scene_analyzer.update(overlay_bgr)
        try:
            base_bird_min = float(
                runtime_cfg.get("processor.min_confidence_binary_bird")
                or runtime_cfg.get("processor.min_confidence_binary")
                or min_confidence
            )
        except (TypeError, ValueError):
            base_bird_min = float(min_confidence)
        scene_bird_floor = self._detection_quality.scene_analyzer.bird_confidence_floor(base_bird_min)

        def _collect_valid_boxes(
            *,
            min_box_px: int,
            min_center: float,
            conf_delta: float = 0.0,
            relaxed_small_object: bool = False,
        ) -> list[dict]:
            out: list[dict] = []
            for track_id, class_idx, conf, bbox_norm, bbox_abs in zip(
                track_ids, class_indexes, confidences, xyxyn, xyxy
            ):
                detector_name = self.binary_model.names[class_idx]
                detector_label = self._normalize_detector_label(detector_name)
                eff_min = per_label_binary_conf_threshold(
                    detector_label,
                    accept_min_confidence,
                    runtime_cfg,
                    inference_backend=inference_backend,
                )
                eff_min = max(0.0, float(eff_min) - float(conf_delta))
                if detector_label == "Bird":
                    eff_min = max(float(eff_min), float(scene_bird_floor))
                cmp_conf = float(conf)
                if not self.is_valid_detection(
                    list(_overlay_norm_bbox(bbox_norm)),
                    cmp_conf,
                    eff_min,
                    min_center_dist=min_center,
                    max_box_area_norm=max_box_area_norm,
                ):
                    continue
                if self.detector_scope is not None and detector_label not in self.detector_scope:
                    continue

                x1, y1, x2, y2 = map(int, bbox_abs)
                x1, y1 = max(0, x1), max(0, y1)
                x2, y2 = min(w, x2), min(h, y2)

                if x2 <= x1 or y2 <= y1:
                    continue
                box_w = x2 - x1
                box_h = y2 - y1
                if box_w < min_box_px or box_h < min_box_px:
                    continue

                out.append(
                    {
                        "track_id": track_id,
                        "detector_label": detector_label,
                        "conf": conf,
                        "bbox_norm": bbox_norm,
                        "crop_coords": (x1, y1, x2, y2),
                        "box_area_norm": max(0.0, float(bbox_norm[2] - bbox_norm[0]))
                        * max(0.0, float(bbox_norm[3] - bbox_norm[1])),
                        "relaxed_small_object": bool(relaxed_small_object),
                    }
                )
            return out

        valid_boxes = _collect_valid_boxes(
            min_box_px=min_box_size_px,
            min_center=min_center_dist,
            conf_delta=0.0,
            relaxed_small_object=False,
        )
        if not valid_boxes and auto_small_object_relax_enabled:
            valid_boxes = _collect_valid_boxes(
                min_box_px=auto_small_object_relax_min_box_size_px,
                min_center=auto_small_object_relax_min_center_dist,
                conf_delta=auto_small_object_relax_conf_delta,
                relaxed_small_object=True,
            )
            if valid_boxes:
                valid_boxes.sort(
                    key=lambda box: (
                        float(box.get("conf") or 0.0),
                        float(box.get("box_area_norm") or 0.0),
                    ),
                    reverse=True,
                )
                valid_boxes = valid_boxes[:auto_small_object_relax_max_candidates]
                logger.info(
                    "Small-object auto-relax accepted %s box(es): min_box %s->%s, min_center_dist %.3f->%.3f, "
                    "conf_delta=%.3f",
                    len(valid_boxes),
                    min_box_size_px,
                    auto_small_object_relax_min_box_size_px,
                    min_center_dist,
                    auto_small_object_relax_min_center_dist,
                    auto_small_object_relax_conf_delta,
                )
        if not valid_boxes and bool(runtime_cfg.get("processor.ultra_weak_box_salvage_enabled", False)):
            try:
                ultra_min_conf = float(runtime_cfg.get("processor.ultra_weak_box_salvage_min_confidence") or 0.005)
            except (TypeError, ValueError):
                ultra_min_conf = 0.005
            try:
                ultra_max_candidates = int(runtime_cfg.get("processor.ultra_weak_box_salvage_max_candidates") or 1)
            except (TypeError, ValueError):
                ultra_max_candidates = 1
            ultra_max_candidates = max(1, min(4, ultra_max_candidates))
            weak_candidates: list[dict] = []
            for track_id, class_idx, conf, bbox_norm, bbox_abs in zip(
                track_ids, class_indexes, confidences, xyxyn, xyxy
            ):
                detector_name = self.binary_model.names[class_idx]
                detector_label = self._normalize_detector_label(detector_name)
                if detector_label != "Bird":
                    continue
                if self.detector_scope is not None and detector_label not in self.detector_scope:
                    continue
                conf_f = float(conf or 0.0)
                if conf_f < ultra_min_conf:
                    continue
                x1, y1, x2, y2 = map(int, bbox_abs)
                x1, y1 = max(0, x1), max(0, y1)
                x2, y2 = min(w, x2), min(h, y2)
                if x2 <= x1 or y2 <= y1:
                    continue
                area_norm = max(0.0, float(bbox_norm[2] - bbox_norm[0])) * max(0.0, float(bbox_norm[3] - bbox_norm[1]))
                if area_norm > max_box_area_norm:
                    continue
                weak_candidates.append(
                    {
                        "track_id": track_id,
                        "detector_label": detector_label,
                        "conf": conf_f,
                        "bbox_norm": bbox_norm,
                        "crop_coords": (x1, y1, x2, y2),
                        "box_area_norm": area_norm,
                        "relaxed_small_object": True,
                    }
                )
            if weak_candidates:
                weak_candidates.sort(
                    key=lambda box: (
                        float(box.get("conf") or 0.0),
                        float(box.get("box_area_norm") or 0.0),
                    ),
                    reverse=True,
                )
                valid_boxes = weak_candidates[:ultra_max_candidates]
                self._ultra_weak_salvage_hits = int(getattr(self, "_ultra_weak_salvage_hits", 0)) + 1
                if self._ultra_weak_salvage_hits <= 3 or self._ultra_weak_salvage_hits % 60 == 0:
                    logger.warning(
                        "Ultra-weak salvage accepted %s bird box(es) at conf >= %.3f. hits=%s",
                        len(valid_boxes),
                        ultra_min_conf,
                        self._ultra_weak_salvage_hits,
                    )

        pre_quality_n = len(valid_boxes)
        proc_cwd = str(Path(__file__).resolve().parents[1])
        _po = profile_overrides if isinstance(profile_overrides, dict) else {}
        frigate_prior = bool(_po.get("_scoring_frigate_prior_active", False))
        valid_boxes = self._detection_quality.filter_boxes(
            valid_boxes,
            frame_bgr=overlay_bgr,
            frame_index=int(self._frame_index),
            processor_cwd=proc_cwd,
            bird_trust_floor=float(scene_bird_floor),
            frigate_prior_active=frigate_prior,
            geometry=detect_geometry,
        )
        _quality_reject_stats.update(self._detection_quality.last_stats)
        if pre_quality_n > len(valid_boxes):
            logger.debug(
                "DetectionQuality: %s -> %s boxes stats=%s",
                pre_quality_n,
                len(valid_boxes),
                {k: v for k, v in _quality_reject_stats.items() if v},
            )

        if not valid_boxes:
            _raw_n = len(boxes) if boxes is not None else 0
            _tid_n = len(track_ids) if track_ids else 0
            _record_detect_metrics(
                raw_boxes=_raw_n,
                boxes_with_track_id=_tid_n,
                accepted=0,
                predict_fallback=boxes_from_predict_fallback,
                quality_reject=_quality_reject_stats,
            )
            return []
        # Overlay regen: только Trapper bbox+track (как тест OV), без NABirds — иначе Bird→сорока и «херня в бою».
        overlay_shape = getattr(self, "_overlay_frame_shape", None) or cls_frame.shape[:2]
        detector_shape = getattr(self, "_detector_frame_shape", None) or frame.shape[:2]
        _binary_only = (
            bool(_pol.binary_only)
            if _pol is not None
            else bool(
                getattr(self, "_for_track_regen", False)
                and bool(runtime_cfg.get("processor.track_regen_binary_only", False))
            )
        )
        try:
            from finalize_classification import defer_classifier_to_finalize

            _defer_classifier = defer_classifier_to_finalize(runtime_cfg)
        except ImportError:
            _defer_classifier = False
        if _binary_only or _defer_classifier:
            detection_results = []
            for box in valid_boxes:
                label = str(box.get("detector_label") or "Bird").strip() or "Bird"
                storage_bbox = _storage_bbox_norm_for_overlay(
                    box["bbox_norm"],
                    detector_frame_shape=detector_shape,
                    overlay_frame_shape=overlay_shape,
                    playback_frame_shape=self._playback_shape_for_storage(),
                )
                crop = None
                blur_variance = None
                if str(label).strip().lower() == "bird":
                    crop, blur_variance = self._extract_valid_box_crop(
                        box,
                        frame=frame,
                        cls_frame=cls_frame,
                        min_box_size_px=min_box_size_px,
                    )
                detection_results.append(
                    DetectionResult(
                        track_id=box["track_id"],
                        detector_label=label,
                        class_name=label,
                        confidence=float(box["conf"]),
                        detector_confidence=box["conf"],
                        classifier_confidence=None,
                        bbox=storage_bbox,
                        blur_variance=blur_variance,
                        crop=crop,
                        scoring_review_only=bool(box.get("scoring_review_only")),
                    )
                )
            _raw_n = len(boxes) if boxes is not None else 0
            _tid_n = len(track_ids) if track_ids else 0
            _record_detect_metrics(
                raw_boxes=_raw_n,
                boxes_with_track_id=_tid_n,
                accepted=len(detection_results),
                predict_fallback=boxes_from_predict_fallback,
                quality_reject=_quality_reject_stats,
            )
            return detection_results
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
        classified_by_track: dict[int, ClassificationTask] = {}
        scheduled_for_classifier: set[int] = set()
        sr_applied = 0
        sr_latency_total_ms = 0.0
        fallback_box = None
        for box in scheduled_boxes[:scan_limit]:
            if should_skip_bird_species_classifier(
                box["detector_label"],
                box["box_area_norm"],
                runtime_cfg,
            ):
                continue
            scheduled_for_classifier.add(int(box["track_id"]))
            if fallback_box is None:
                fallback_box = box
            mapped = _crop_coords_from_letterboxed_bbox_norm(
                bbox_norm=box["bbox_norm"],
                detector_frame_shape=detector_shape,
                overlay_frame_shape=overlay_shape,
                classification_frame_shape=cls_frame.shape,
                playback_frame_shape=self._playback_shape_for_storage(),
            )
            if mapped is None:
                continue
            x1, y1, x2, y2 = mapped
            roi_ref = roi_crop_ref_from_norm_bbox(cls_frame, x1=x1, y1=y1, x2=x2, y2=y2)
            if roi_ref is None:
                continue
            crop_view = roi_ref.view()
            is_blur, variance = self.is_blurry(crop_view)
            if is_blur:
                continue
            crop_sr, sr_n, sr_ms = self._apply_roi_sr_to_crop(crop_view, min_box_size_px=min_box_size_px)
            sr_applied += sr_n
            sr_latency_total_ms += sr_ms
            crop_payload: np.ndarray | RoiCropRef = roi_ref
            if crop_sr is not crop_view:
                crop_payload = crop_sr
            else:
                _, copied = crop_for_classifier(roi_ref)
                if copied:
                    frame_copy_count += 1
            if len(self._classification_task_queue) >= self._classification_task_queue_maxsize:
                if getattr(self, "_classifier_async_enabled", False) and not track_regen_ctx:
                    with self._classifier_async_lock:
                        if len(self._classification_task_queue) >= self._classification_task_queue_maxsize:
                            self._classification_task_queue.popleft()
                else:
                    self._classification_task_queue.popleft()
                self._classification_task_drops_total += 1
                record_classification_queue_drop(
                    depth=len(self._classification_task_queue),
                    maxsize=self._classification_task_queue_maxsize,
                    drops_total=self._classification_task_drops_total,
                )
            task = ClassificationTask(
                track_id=int(box["track_id"]),
                detector_label=str(box["detector_label"]),
                box_area_norm=float(box["box_area_norm"]),
                crop=crop_payload,
                blur_variance=variance,
            )
            if getattr(self, "_classifier_async_enabled", False) and not track_regen_ctx:
                with self._classifier_async_lock:
                    self._classification_task_queue.append(task)
            else:
                self._classification_task_queue.append(task)
        if not self._classification_task_queue and fallback_box is not None:
            mapped = _crop_coords_from_letterboxed_bbox_norm(
                bbox_norm=fallback_box["bbox_norm"],
                detector_frame_shape=detector_shape,
                overlay_frame_shape=overlay_shape,
                classification_frame_shape=cls_frame.shape,
                playback_frame_shape=self._playback_shape_for_storage(),
            )
            if mapped is not None:
                x1, y1, x2, y2 = mapped
                roi_ref = roi_crop_ref_from_norm_bbox(cls_frame, x1=x1, y1=y1, x2=x2, y2=y2)
                if roi_ref is not None:
                    crop_view = roi_ref.view()
                    crop_sr, sr_n, sr_ms = self._apply_roi_sr_to_crop(crop_view, min_box_size_px=min_box_size_px)
                    sr_applied += sr_n
                    sr_latency_total_ms += sr_ms
                    _, variance = self.is_blurry(crop_view)
                    crop_payload: np.ndarray | RoiCropRef = crop_sr if crop_sr is not crop_view else roi_ref
                    fb_task = ClassificationTask(
                        track_id=int(fallback_box["track_id"]),
                        detector_label=str(fallback_box["detector_label"]),
                        box_area_norm=float(fallback_box["box_area_norm"]),
                        crop=crop_payload,
                        blur_variance=variance,
                    )
                    if getattr(self, "_classifier_async_enabled", False) and not track_regen_ctx:
                        with self._classifier_async_lock:
                            self._classification_task_queue.append(fb_task)
                    else:
                        self._classification_task_queue.append(fb_task)
        use_async_classifier = bool(getattr(self, "_classifier_async_enabled", False) and not track_regen_ctx)
        if use_async_classifier:
            with self._classifier_async_lock:
                classified_by_track = {}
        else:
            while self._classification_task_queue and len(classified_by_track) < classification_budget:
                task = self._classification_task_queue.popleft()
                classified_by_track[int(task.track_id)] = task
        if not use_async_classifier:
            for box in valid_boxes:
                stats = self._track_stats.setdefault(
                    box["track_id"],
                    {"classified_count": 0, "last_classified_frame": -1},
                )
                if box["track_id"] in classified_by_track:
                    stats["classified_count"] = int(stats.get("classified_count") or 0) + 1
                    stats["last_classified_frame"] = self._frame_index
        elif valid_boxes:
            for box in valid_boxes:
                self._track_stats.setdefault(
                    box["track_id"],
                    {"classified_count": 0, "last_classified_frame": -1},
                )
        detection_results = []
        for box in valid_boxes:
            species_name = None
            crop = None
            blur_variance = None
            combined_conf = box["conf"]  # Default to detector confidence
            classifier_conf = None

            classified = classified_by_track.get(box["track_id"])
            if classified and should_skip_bird_species_classifier(
                classified.detector_label,
                classified.box_area_norm,
                runtime_cfg,
            ):
                classified = None
            co: ClassifierOutput | None = None
            storage_bbox = _storage_bbox_norm_for_overlay(
                box["bbox_norm"],
                detector_frame_shape=detector_shape,
                overlay_frame_shape=overlay_shape,
                playback_frame_shape=self._playback_shape_for_storage(),
            )
            if classified is not None:
                co = self._classify_crop(classified.crop)
                crop = classified.crop
                blur_variance = classified.blur_variance
            elif use_async_classifier:
                with self._classifier_async_lock:
                    co = self._latest_cls_by_track.get(int(box["track_id"]))
            elif (
                int(box["track_id"]) in scheduled_for_classifier
                and str(box.get("detector_label") or "").strip() != "Bird"
            ):
                # Не-Bird в scope (Trapper squirrel и т.д.): один проход классификатора даже при tight budget.
                co, crop, blur_variance = self._classify_valid_box_crop(
                    box,
                    frame=frame,
                    cls_frame=cls_frame,
                    min_box_size_px=min_box_size_px,
                )
            if co is not None:
                species_name = co.species_name
                classifier_conf = co.top1_confidence
                combined_conf = float(box["conf"]) * float(co.top1_confidence)
                self._latest_cls_by_track[int(box["track_id"])] = co

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
                    bbox=storage_bbox,
                    blur_variance=blur_variance,
                    crop=crop,
                    scoring_review_only=bool(box.get("scoring_review_only")),
                )
            )

        _raw_n = len(boxes) if boxes is not None else 0
        _tid_n = len(track_ids) if track_ids else 0
        _record_detect_metrics(
            raw_boxes=_raw_n,
            boxes_with_track_id=_tid_n,
            accepted=len(detection_results),
            predict_fallback=boxes_from_predict_fallback,
            sr_applied=sr_applied,
            sr_latency_ms=sr_latency_total_ms,
            quality_reject=_quality_reject_stats,
        )
        try:
            from bbox_parity_debug import maybe_save_parity_overlay
            from frame_geometry import unpad_boxes

            if cls_frame is not None and len(xyxyn) > 0:
                raw_overlay: list[tuple[float, float, float, float]] = []
                for bn in xyxyn:
                    mapped = unpad_boxes(
                        bn,
                        source_shape_hw=overlay_hw,
                        letterbox_shape_hw=det_hw,
                    )
                    if mapped is not None:
                        raw_overlay.append(mapped)
                accepted_overlay = [
                    (float(d.bbox[0]), float(d.bbox[1]), float(d.bbox[2]), float(d.bbox[3]))
                    for d in detection_results
                    if d.bbox and len(d.bbox) == 4
                ]
                maybe_save_parity_overlay(
                    cls_frame,
                    raw_boxes_overlay_norm=raw_overlay,
                    accepted_boxes_overlay_norm=accepted_overlay,
                    runtime_cfg=runtime_cfg,
                    session_id=str(getattr(self, "_parity_session_id", "") or "") or None,
                    frame_index=int(getattr(self, "_frame_index", 0)),
                    geometry_stats=getattr(self, "_bbox_iou_gate_stats", None),
                )
        except Exception:
            logger.debug("bbox parity overlay save failed", exc_info=True)
        return detection_results

    def reset(self):
        self._classification_index = 0
        self._frame_index = 0
        if hasattr(self, "_detection_quality") and self._detection_quality is not None:
            self._detection_quality.reset()
        self._track_stats = {}
        self._regen_iou_prev_boxes = None
        self._regen_iou_prev_ids = None
        self._regen_iou_next_id = 1
        self._live_iou_prev_boxes = None
        self._live_iou_prev_ids = None
        self._live_iou_next_id = 1
        self._track_predict_fallback_hits = 0
        self._ultra_weak_salvage_hits = 0
        self._classification_task_queue.clear()
        self._latest_cls_by_track.clear()
        self._detection_quality: DetectionQualityPipeline | None = None
        if hasattr(self.binary_model.predictor, "trackers"):
            self.binary_model.predictor.trackers[0].reset()

    def stop_classifier_worker(self) -> None:
        if getattr(self, "_classifier_worker_stop", None) is not None:
            self._classifier_worker_stop.set()
        worker = getattr(self, "_classifier_worker", None)
        if worker is not None and worker.is_alive():
            worker.join(timeout=0.5)
