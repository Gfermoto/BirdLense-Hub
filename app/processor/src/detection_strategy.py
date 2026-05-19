from abc import ABC, abstractmethod
import logging
import math
from typing import Any, List, Mapping, Optional, Sequence, Tuple
from dataclasses import dataclass
import numpy as np
import cv2
from detector_labels import normalize_detector_label
from inference.torch_backend import load_yolo_classifier, load_yolo_detector
from inference.weight_contract import validate_detector_weight_contract
from processor_runtime_profile import RuntimeProfileConfigOverlay
from roi_super_resolution import build_roi_super_resolution

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


def _rodent_binary_threshold_raw(config: Mapping[str, Any]) -> Any:
    """Новый ключ ``min_confidence_binary_rodent``; ``min_confidence_binary_squirrel`` — только совместимость со старым YAML."""
    raw = config.get("processor.min_confidence_binary_rodent")
    if raw is not None:
        return raw
    return config.get("processor.min_confidence_binary_squirrel")


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


def _openvino_binary_bird_threshold_override(
    bird_m: float,
    config: Mapping[str, Any],
    *,
    inference_backend: str | None,
) -> float:
    """При ``openvino`` и непустом ``processor.openvino_min_confidence_binary_bird`` — заменить порог Bird."""
    if (inference_backend or "").strip().lower() != "openvino":
        return bird_m
    ov = _parse_optional_processor_float(config, "processor.openvino_min_confidence_binary_bird")
    if ov is None:
        return bird_m
    return max(0.001, min(0.99, float(ov)))


def openvino_binary_bird_score_scale(config: Mapping[str, Any], *, inference_backend: str | None) -> float:
    """Только Bird + OpenVINO: множитель к conf при сравнении с порогом (сырой conf в БД не меняется). 1.0 = выкл."""
    if (inference_backend or "").strip().lower() != "openvino":
        return 1.0
    s = _parse_optional_processor_float(config, "processor.openvino_binary_bird_score_scale")
    if s is None:
        return 1.0
    return max(1.0, min(25.0, float(s)))


def _openvino_binary_track_ultralytics_conf_cap(
    stock_floor: float,
    config: Mapping[str, Any],
    *,
    inference_backend: str | None,
) -> float:
    """При OV: ``min(stock_floor, openvino_binary_track_ultralytics_conf)`` — ослабить ``track(conf=…)`` без второго инференса."""
    if (inference_backend or "").strip().lower() != "openvino":
        return stock_floor
    cap = _parse_optional_processor_float(config, "processor.openvino_binary_track_ultralytics_conf")
    if cap is None:
        return stock_floor
    cap = max(0.01, min(0.25, float(cap)))
    return min(float(stock_floor), cap)


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
    bird_m = _openvino_binary_bird_threshold_override(bird_m, config, inference_backend=inference_backend)
    rod_m = float(s_raw) if s_raw is not None else base
    stock = min(base, bird_m, rod_m)
    return _openvino_binary_track_ultralytics_conf_cap(stock, config, inference_backend=inference_backend)


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
    bird_m = _openvino_binary_bird_threshold_override(bird_m, config, inference_backend=inference_backend)
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
    classification_frame_shape: Sequence[int],
) -> tuple[int, int, int, int] | None:
    """Map normalized bbox from detector letterbox space to classification frame space."""
    if len(bbox_norm) != 4:
        return None
    try:
        det_h, det_w = int(detector_frame_shape[0]), int(detector_frame_shape[1])
        cls_h, cls_w = int(classification_frame_shape[0]), int(classification_frame_shape[1])
    except Exception:
        return None
    if det_h <= 0 or det_w <= 0 or cls_h <= 0 or cls_w <= 0:
        return None

    x1d = float(bbox_norm[0]) * float(det_w)
    y1d = float(bbox_norm[1]) * float(det_h)
    x2d = float(bbox_norm[2]) * float(det_w)
    y2d = float(bbox_norm[3]) * float(det_h)

    if det_w == cls_w and det_h == cls_h:
        x1 = int(max(0, min(cls_w, round(x1d))))
        y1 = int(max(0, min(cls_h, round(y1d))))
        x2 = int(max(0, min(cls_w, round(x2d))))
        y2 = int(max(0, min(cls_h, round(y2d))))
        if x2 <= x1 or y2 <= y1:
            return None
        return x1, y1, x2, y2

    # Inverse of letterbox_bgr_to_wh(frame, (det_w, det_h))
    r = min(float(det_w) / float(cls_w), float(det_h) / float(cls_h))
    if r <= 0:
        return None
    nw = float(cls_w) * r
    nh = float(cls_h) * r
    pad_x = (float(det_w) - nw) / 2.0
    pad_y = (float(det_h) - nh) / 2.0
    x1 = int(max(0, min(cls_w, round((x1d - pad_x) / r))))
    y1 = int(max(0, min(cls_h, round((y1d - pad_y) / r))))
    x2 = int(max(0, min(cls_w, round((x2d - pad_x) / r))))
    y2 = int(max(0, min(cls_h, round((y2d - pad_y) / r))))
    if x2 <= x1 or y2 <= y1:
        return None
    return x1, y1, x2, y2


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
    ):
        super().__init__(min_center_dist, min_box_size_px, blur_threshold, max_blur_checks)
        self.logger = logging.getLogger(self.__class__.__name__)
        self.inference_backend = (inference_backend or "torch").strip().lower()
        self.classifier_inference_backend = (classifier_inference_backend or "torch").strip().lower()
        _dev = (binary_inference_device or "").strip()
        self._binary_track_device: str | None = _dev or None
        _cls_dev = (classifier_inference_device or "").strip()
        self._classifier_predict_device: str | None = (
            _cls_dev if self.classifier_inference_backend == "openvino" and _cls_dev else None
        )
        self.weight_contract_mode = (weight_contract_mode or "warn").strip().lower()
        self.regional_species = regional_species
        self.max_classifications_per_frame = max(1, int(max_classifications_per_frame or 1))
        self.classification_scheduler = str(classification_scheduler or "priority").strip().lower()
        self.binary_imgsz = max(320, int(binary_imgsz or 320))
        from app_config.app_config import app_config

        self._roi_sr = build_roi_super_resolution(app_config)
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
        _warm: dict = {"tracker": "bytetrack.yaml", "persist": True, "verbose": False}
        if self._binary_track_device:
            _warm["device"] = self._binary_track_device
        self.binary_model.track(np.zeros((320, 320, 3), dtype=np.uint8), **_warm)
        _cls_warm: dict = {"verbose": False}
        if self._classifier_predict_device:
            _cls_warm["device"] = self._classifier_predict_device
        self.classifier_model(np.zeros((224, 224, 3), dtype=np.uint8), **_cls_warm)

    def _normalize_class_name(self, name: str) -> str:
        """Blue_Jay → Blue Jay, Winter_OR_juvenile → Winter/juvenile."""
        return name.replace("_OR_", "/").replace("_", " ")

    def _normalize_detector_label(self, name: str) -> str:
        return normalize_detector_label(name)

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

    def _classify_crop(self, crop: np.ndarray) -> ClassifierOutput:
        """Классификация кропа: вид, top1 conf, энтропия и top1−top2 margin по полному вектору probs."""
        _cls_kwargs: dict = {"verbose": False}
        _cls_dev = getattr(self, "_classifier_predict_device", None)
        if _cls_dev:
            _cls_kwargs["device"] = _cls_dev
        result_cls = self.classifier_model(crop, **_cls_kwargs)

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
        self._frame_index += 1
        inference_backend = str(getattr(self, "inference_backend", "torch") or "torch").strip().lower()
        imgsz = int(runtime_cfg.resolve_strategy_field("processor.binary_imgsz", self, "binary_imgsz", 320) or 320)
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
        # Post-track filters must not discard boxes that track() already admitted at track_conf.
        accept_min_confidence = min(float(min_confidence), float(track_conf))
        boxes_from_predict_fallback = False
        track_regen_ctx = bool(getattr(self, "_for_track_regen", False))
        iou_fb = bool(runtime_cfg.get("processor.track_regen_iou_id_fallback", False))
        _tkw: dict = {
            "persist": True,
            "conf": track_conf,
            "verbose": False,
            "imgsz": imgsz,
            "tracker": tracker_config,
        }
        _tkw.update(build_binary_track_ultralytics_extras(runtime_cfg))
        _bdev = getattr(self, "_binary_track_device", None)
        if _bdev:
            _tkw["device"] = _bdev
        results = (
            self.binary_model.track(frame, **_tkw)
            if track_regen_ctx and iou_fb
            else _track_maybe_retry(self.binary_model, frame, **_tkw)
        )

        def _record_detect_metrics(
            *,
            raw_boxes: int,
            boxes_with_track_id: int,
            accepted: int,
            predict_fallback: bool = False,
            sr_applied: int = 0,
            sr_latency_ms: float = 0.0,
        ) -> None:
            self.last_detect_metrics = {
                "raw_boxes": int(raw_boxes),
                "boxes_with_track_id": int(boxes_with_track_id),
                "accepted": int(accepted),
                "predict_fallback": bool(predict_fallback),
                "sr_applied": int(sr_applied),
                "sr_latency_ms": round(float(sr_latency_ms), 3),
            }

        boxes = None
        if results and len(results[0].boxes) > 0:
            boxes = results[0].boxes
        else:
            fallback_enabled = bool(runtime_cfg.get("processor.track_to_predict_fallback_enabled", True))
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
            live_iou_fb = bool(runtime_cfg.get("processor.iou_id_fallback_live_enabled", True))
            if not (track_regen_ctx and iou_fb) and not live_iou_fb:
                _record_detect_metrics(
                    raw_boxes=len(boxes),
                    boxes_with_track_id=0,
                    accepted=0,
                    predict_fallback=boxes_from_predict_fallback,
                )
                return []
            iou_thr_raw = (
                runtime_cfg.get("processor.track_regen_iou_match_threshold")
                if track_regen_ctx
                else runtime_cfg.get("processor.iou_id_fallback_live_match_threshold")
            )
            try:
                iou_thr = float(iou_thr_raw) if iou_thr_raw is not None else (0.22 if track_regen_ctx else 0.20)
            except (TypeError, ValueError):
                iou_thr = 0.22 if track_regen_ctx else 0.20
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
                self._regen_iou_prev_ids = list(synth)
                self._regen_iou_next_id = int(nid_next)
            else:
                self._live_iou_prev_boxes = curr_xyxy.copy()
                self._live_iou_prev_ids = list(synth)
                self._live_iou_next_id = int(nid_next)
            track_ids = synth
        else:
            track_ids = boxes.id.int().cpu().tolist()

        class_indexes = boxes.cls.int().cpu().tolist()
        confidences = boxes.conf.cpu().tolist()
        xyxyn = _tensor_to_numpy(boxes.xyxyn)
        xyxy = _tensor_to_numpy(boxes.xyxy)

        h, w, _ = frame.shape
        cls_frame = coerce_bgr_frame(classification_frame, log_label="classification_frame") or frame

        _ov_bird_scale = openvino_binary_bird_score_scale(
            runtime_cfg,
            inference_backend=inference_backend,
        )

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
                cmp_conf = float(conf)
                if detector_label == "Bird" and _ov_bird_scale > 1.0:
                    cmp_conf *= _ov_bird_scale
                if not self.is_valid_detection(
                    bbox_norm,
                    cmp_conf,
                    eff_min,
                    min_center_dist=min_center,
                    max_box_area_norm=max_box_area_norm,
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
        if not valid_boxes and bool(runtime_cfg.get("processor.ultra_weak_box_salvage_enabled", True)):
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
                if self.detector_scope and detector_label not in self.detector_scope:
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

        if not valid_boxes:
            _raw_n = len(boxes) if boxes is not None else 0
            _tid_n = len(track_ids) if track_ids else 0
            _record_detect_metrics(
                raw_boxes=_raw_n,
                boxes_with_track_id=_tid_n,
                accepted=0,
                predict_fallback=boxes_from_predict_fallback,
            )
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
            if fallback_box is None:
                fallback_box = box
            mapped = _crop_coords_from_letterboxed_bbox_norm(
                bbox_norm=box["bbox_norm"],
                detector_frame_shape=frame.shape,
                classification_frame_shape=cls_frame.shape,
            )
            if mapped is None:
                continue
            x1, y1, x2, y2 = mapped
            crop = cls_frame[y1:y2, x1:x2]
            is_blur, variance = self.is_blurry(crop)
            if is_blur:
                continue
            if self._roi_sr.should_enhance(crop, min_box_size_px=min_box_size_px):
                crop_sr, sr_meta = self._roi_sr.enhance(crop)
                crop = crop_sr
                if sr_meta.enabled:
                    sr_applied += 1
                    sr_latency_total_ms += float(sr_meta.latency_ms)
            classified_by_track[box["track_id"]] = {
                "crop": crop.copy(),
                "blur_variance": variance,
            }
            if len(classified_by_track) >= classification_budget:
                break
        if not classified_by_track and fallback_box is not None:
            mapped = _crop_coords_from_letterboxed_bbox_norm(
                bbox_norm=fallback_box["bbox_norm"],
                detector_frame_shape=frame.shape,
                classification_frame_shape=cls_frame.shape,
            )
            if mapped is not None:
                x1, y1, x2, y2 = mapped
                crop = cls_frame[y1:y2, x1:x2]
                if self._roi_sr.should_enhance(crop, min_box_size_px=min_box_size_px):
                    crop_sr, sr_meta = self._roi_sr.enhance(crop)
                    crop = crop_sr
                    if sr_meta.enabled:
                        sr_applied += 1
                        sr_latency_total_ms += float(sr_meta.latency_ms)
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

        _raw_n = len(boxes) if boxes is not None else 0
        _tid_n = len(track_ids) if track_ids else 0
        _record_detect_metrics(
            raw_boxes=_raw_n,
            boxes_with_track_id=_tid_n,
            accepted=len(detection_results),
            predict_fallback=boxes_from_predict_fallback,
            sr_applied=sr_applied,
            sr_latency_ms=sr_latency_total_ms,
        )
        return detection_results

    def reset(self):
        self._classification_index = 0
        self._frame_index = 0
        self._track_stats = {}
        self._regen_iou_prev_boxes = None
        self._regen_iou_prev_ids = None
        self._regen_iou_next_id = 1
        self._live_iou_prev_boxes = None
        self._live_iou_prev_ids = None
        self._live_iou_next_id = 1
        self._track_predict_fallback_hits = 0
        self._ultra_weak_salvage_hits = 0
        if hasattr(self.binary_model.predictor, "trackers"):
            self.binary_model.predictor.trackers[0].reset()
