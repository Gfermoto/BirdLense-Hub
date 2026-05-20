"""Universal static / phantom box suppression (feeder, branches, background)."""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Mapping

import cv2
import numpy as np

logger = logging.getLogger(__name__)


def _parse_float(cfg: Mapping[str, Any], key: str, default: float) -> float:
    raw = cfg.get(key)
    if raw is None:
        return default
    try:
        return float(raw)
    except (TypeError, ValueError):
        return default


def _parse_int(cfg: Mapping[str, Any], key: str, default: int) -> int:
    raw = cfg.get(key)
    if raw is None:
        return default
    try:
        return int(raw)
    except (TypeError, ValueError):
        return default


def _parse_bool(cfg: Mapping[str, Any], key: str, default: bool) -> bool:
    raw = cfg.get(key)
    if raw is None:
        return default
    if isinstance(raw, bool):
        return raw
    return str(raw).strip().lower() in ("1", "true", "yes", "on")


@dataclass
class StaticObjectFilterConfig:
    enabled: bool = True
    static_box_aspect_ratio_min: float = 0.8
    static_box_aspect_ratio_max: float = 1.2
    static_box_conf_threshold: float = 0.45
    static_scene_bird_min_confidence: float = 0.5
    static_scene_bird_like_min_confidence: float = 0.4
    static_scene_bird_like_max_aspect: float = 0.7
    static_scene_bird_like_min_aspect: float = 1.4
    static_temporal_enabled: bool = True
    static_temporal_min_frames: int = 4
    static_temporal_max_jitter_px: float = 5.0
    static_temporal_max_area_px: float = 120_000.0
    static_temporal_hist_change_max: float = 0.04
    static_giant_box_area_frac: float = 0.5
    log_sample_limit: int = 5

    @classmethod
    def from_runtime_cfg(cls, runtime_cfg: Mapping[str, Any]) -> StaticObjectFilterConfig:
        return cls(
            enabled=_parse_bool(runtime_cfg, "processor.static_object_suppression_enabled", True),
            static_box_aspect_ratio_min=_parse_float(
                runtime_cfg, "processor.static_box_aspect_ratio_min", 0.8
            ),
            static_box_aspect_ratio_max=_parse_float(
                runtime_cfg, "processor.static_box_aspect_ratio_max", 1.2
            ),
            static_box_conf_threshold=_parse_float(
                runtime_cfg, "processor.static_box_conf_threshold", 0.45
            ),
            static_scene_bird_min_confidence=_parse_float(
                runtime_cfg, "processor.static_scene_bird_min_confidence", 0.5
            ),
            static_scene_bird_like_min_confidence=_parse_float(
                runtime_cfg, "processor.static_scene_bird_like_min_confidence", 0.4
            ),
            static_scene_bird_like_max_aspect=_parse_float(
                runtime_cfg, "processor.static_scene_bird_like_max_aspect", 0.7
            ),
            static_scene_bird_like_min_aspect=_parse_float(
                runtime_cfg, "processor.static_scene_bird_like_min_aspect", 1.4
            ),
            static_temporal_enabled=_parse_bool(runtime_cfg, "processor.static_temporal_enabled", True),
            static_temporal_min_frames=_parse_int(runtime_cfg, "processor.static_temporal_min_frames", 4),
            static_temporal_max_jitter_px=_parse_float(
                runtime_cfg, "processor.static_temporal_max_jitter_px", 5.0
            ),
            static_temporal_max_area_px=_parse_float(
                runtime_cfg, "processor.static_temporal_max_area_px", 120_000.0
            ),
            static_temporal_hist_change_max=_parse_float(
                runtime_cfg, "processor.static_temporal_hist_change_max", 0.04
            ),
            static_giant_box_area_frac=_parse_float(
                runtime_cfg, "processor.static_giant_box_area_frac", 0.5
            ),
        )


def _box_aspect(box: dict[str, Any]) -> float:
    x1, y1, x2, y2 = box["crop_coords"]
    w = max(1.0, float(x2 - x1))
    h = max(1.0, float(y2 - y1))
    return w / h


def _box_center(box: dict[str, Any]) -> tuple[float, float]:
    x1, y1, x2, y2 = box["crop_coords"]
    return (float(x1 + x2) / 2.0, float(y1 + y2) / 2.0)


def _box_area_px(box: dict[str, Any]) -> float:
    x1, y1, x2, y2 = box["crop_coords"]
    return max(0.0, float(x2 - x1)) * max(0.0, float(y2 - y1))


def _is_squareish(ar: float, cfg: StaticObjectFilterConfig) -> bool:
    return cfg.static_box_aspect_ratio_min <= ar <= cfg.static_box_aspect_ratio_max


def _is_bird_like_shape(ar: float, cfg: StaticObjectFilterConfig) -> bool:
    return ar <= cfg.static_scene_bird_like_max_aspect or ar >= cfg.static_scene_bird_like_min_aspect


def _crop_hist_signature(frame_bgr: np.ndarray, box: dict[str, Any]) -> np.ndarray | None:
    x1, y1, x2, y2 = [int(v) for v in box["crop_coords"]]
    h, w = frame_bgr.shape[:2]
    x1, y1 = max(0, x1), max(0, y1)
    x2, y2 = min(w, x2), min(h, y2)
    if x2 - x1 < 8 or y2 - y1 < 8:
        return None
    crop = frame_bgr[y1:y2, x1:x2]
    hist = cv2.calcHist([crop], [0], None, [16], [0, 256]).flatten()
    s = float(hist.sum())
    if s <= 0:
        return None
    return hist / s


def _hist_l1_delta(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.abs(a - b).sum())


class StaticObjectFilter:
    """Post-NMS filter: drop phantom static boxes; keep sitting/moving birds."""

    def __init__(self, cfg: StaticObjectFilterConfig | None = None) -> None:
        self.cfg = cfg or StaticObjectFilterConfig()
        self._track_history: dict[int, list[tuple[int, float, float, np.ndarray | None]]] = defaultdict(list)
        self._log_samples = 0
        self.last_stats: dict[str, int] = {
            "rejected_static_objects": 0,
            "rejected_phantom_boxes": 0,
        }

    def reset(self) -> None:
        self._track_history.clear()
        self._log_samples = 0
        self.last_stats = {"rejected_static_objects": 0, "rejected_phantom_boxes": 0}

    def _scene_context(self, boxes: list[dict[str, Any]]) -> tuple[bool, bool]:
        cfg = self.cfg
        has_anchor = False
        has_bird_like = False
        for b in boxes:
            if str(b.get("detector_label") or "") != "Bird":
                continue
            conf = float(b.get("conf") or 0.0)
            ar = _box_aspect(b)
            if conf >= cfg.static_scene_bird_min_confidence:
                has_anchor = True
            if conf >= cfg.static_scene_bird_like_min_confidence and _is_bird_like_shape(ar, cfg):
                has_bird_like = True
        return has_anchor, has_bird_like

    def _reject_reason(
        self,
        box: dict[str, Any],
        *,
        frame_bgr: np.ndarray | None,
        frame_index: int,
        has_anchor: bool,
        has_bird_like: bool,
    ) -> str | None:
        cfg = self.cfg
        if not cfg.enabled or str(box.get("detector_label") or "") != "Bird":
            return None

        conf = float(box.get("conf") or 0.0)
        ar = _box_aspect(box)
        area_norm = float(box.get("box_area_norm") or 0.0)
        area_px = _box_area_px(box)

        if area_norm > cfg.static_giant_box_area_frac:
            return f"phantom_box_giant_area(area_norm={area_norm:.3f})"

        if conf >= cfg.static_scene_bird_min_confidence:
            return None
        if _is_bird_like_shape(ar, cfg) and conf >= cfg.static_scene_bird_like_min_confidence:
            return None

        square = _is_squareish(ar, cfg)

        if square and conf < cfg.static_box_conf_threshold:
            if not has_anchor and not has_bird_like:
                return (
                    f"static_object_detected(ar={ar:.2f},conf={conf:.2f},"
                    f"no_birds_in_frame,raised_thr={cfg.static_box_conf_threshold:.2f})"
                )
            if not has_anchor:
                return (
                    f"static_object_detected(ar={ar:.2f},conf={conf:.2f},"
                    f"square_low_conf_no_anchor)"
                )

        if not cfg.static_temporal_enabled or frame_bgr is None:
            return None

        track_id = int(box.get("track_id") or 0)
        cx, cy = _box_center(box)
        sig = _crop_hist_signature(frame_bgr, box)
        hist = self._track_history[track_id]
        hist.append((frame_index, cx, cy, sig))
        if len(hist) > cfg.static_temporal_min_frames + 2:
            del hist[: -cfg.static_temporal_min_frames - 1]

        if len(hist) < cfg.static_temporal_min_frames or area_px > cfg.static_temporal_max_area_px:
            return None
        if not square or conf >= cfg.static_box_conf_threshold:
            return None

        recent = hist[-cfg.static_temporal_min_frames :]
        c0x, c0y = recent[0][1], recent[0][2]
        if any(
            abs(p[1] - c0x) > cfg.static_temporal_max_jitter_px
            or abs(p[2] - c0y) > cfg.static_temporal_max_jitter_px
            for p in recent[1:]
        ):
            return None

        if recent[0][3] is not None and recent[-1][3] is not None:
            delta = _hist_l1_delta(recent[0][3], recent[-1][3])
            if delta > cfg.static_temporal_hist_change_max:
                return None

        if has_anchor or has_bird_like:
            return None

        return (
            f"static_object_temporal(ar={ar:.2f},conf={conf:.2f},"
            f"frames={cfg.static_temporal_min_frames},jitter<{cfg.static_temporal_max_jitter_px:.0f}px)"
        )

    def filter_boxes(
        self,
        boxes: list[dict[str, Any]],
        *,
        frame_bgr: np.ndarray | None,
        frame_index: int,
    ) -> list[dict[str, Any]]:
        self.last_stats = {"rejected_static_objects": 0, "rejected_phantom_boxes": 0}
        if not self.cfg.enabled or not boxes:
            return boxes

        has_anchor, has_bird_like = self._scene_context(boxes)
        kept: list[dict[str, Any]] = []
        for box in boxes:
            reason = self._reject_reason(
                box,
                frame_bgr=frame_bgr,
                frame_index=frame_index,
                has_anchor=has_anchor,
                has_bird_like=has_bird_like,
            )
            if reason:
                if reason.startswith("phantom_box"):
                    self.last_stats["rejected_phantom_boxes"] += 1
                else:
                    self.last_stats["rejected_static_objects"] += 1
                if self._log_samples < self.cfg.log_sample_limit:
                    self._log_samples += 1
                    logger.info(
                        "StaticObjectFilter reject track=%s reason=%s",
                        box.get("track_id"),
                        reason,
                    )
                continue
            kept.append(box)
        return kept
