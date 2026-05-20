"""NVR-grade detection quality pipeline: masks, motion, static, texture, hard negatives."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

import cv2
import numpy as np

from detection_masks import DetectionMaskConfig, DetectionMaskFilter
from static_object_filter import StaticObjectFilter, StaticObjectFilterConfig

logger = logging.getLogger(__name__)


def _parse_bool(cfg: Mapping[str, Any], key: str, default: bool) -> bool:
    try:
        raw = cfg.get(key)
    except (AttributeError, TypeError):
        return default
    if raw is None:
        return default
    if not isinstance(raw, (bool, str, int, float)):
        return default
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, (int, float)):
        return bool(raw)
    return str(raw).strip().lower() in ("1", "true", "yes", "on")


def _parse_float(cfg: Mapping[str, Any], key: str, default: float) -> float:
    try:
        raw = cfg.get(key)
    except (AttributeError, TypeError):
        return default
    if raw is None or not isinstance(raw, (str, int, float)):
        return default
    try:
        return float(raw)
    except (TypeError, ValueError):
        return default


def _parse_int(cfg: Mapping[str, Any], key: str, default: int) -> int:
    try:
        raw = cfg.get(key)
    except (AttributeError, TypeError):
        return default
    if raw is None or not isinstance(raw, (str, int, float)):
        return default
    try:
        return int(raw)
    except (TypeError, ValueError):
        return default


@dataclass
class DetectionQualityConfig:
    mask: DetectionMaskConfig = field(default_factory=lambda: DetectionMaskConfig([], [], False))
    static: StaticObjectFilterConfig = field(default_factory=StaticObjectFilterConfig)
    motion_verified_enabled: bool = True
    motion_min_mean_absdiff: float = 6.0
    motion_global_static_reject: bool = True
    motion_global_max_mean_absdiff: float = 1.5
    texture_enabled: bool = True
    texture_min_laplacian_var: float = 20.0
    hard_negatives_enabled: bool = True
    hard_negatives_max_per_frame: int = 8
    hard_negatives_dir: str = "data/hard_negatives"
    assumed_fps: float = 7.0
    static_temporal_min_seconds: float = 8.0

    @classmethod
    def from_runtime_cfg(cls, runtime_cfg: Mapping[str, Any]) -> DetectionQualityConfig:
        static = StaticObjectFilterConfig.from_runtime_cfg(runtime_cfg)
        min_frames_override = _parse_int(runtime_cfg, "processor.static_temporal_min_frames", 0)
        if min_frames_override <= 0:
            fps = max(1.0, _parse_float(runtime_cfg, "processor.detection_quality_assumed_fps", 7.0))
            sec = _parse_float(runtime_cfg, "processor.static_temporal_min_seconds", 8.0)
            static.static_temporal_min_frames = max(4, int(sec * fps))
        else:
            static.static_temporal_min_frames = min_frames_override
        static.static_temporal_max_jitter_px = _parse_float(
            runtime_cfg, "processor.static_temporal_max_jitter_px", 2.0
        )
        return cls(
            mask=DetectionMaskConfig.from_runtime_cfg(runtime_cfg),
            static=static,
            motion_verified_enabled=_parse_bool(
                runtime_cfg, "processor.motion_verified_detection_enabled", True
            ),
            motion_min_mean_absdiff=_parse_float(
                runtime_cfg, "processor.motion_verified_min_pixel_change", 6.0
            ),
            motion_global_static_reject=_parse_bool(
                runtime_cfg, "processor.motion_global_static_reject_enabled", True
            ),
            motion_global_max_mean_absdiff=_parse_float(
                runtime_cfg, "processor.motion_global_max_mean_absdiff", 1.5
            ),
            texture_enabled=_parse_bool(runtime_cfg, "processor.detection_texture_filter_enabled", True),
            texture_min_laplacian_var=_parse_float(
                runtime_cfg, "processor.detection_texture_min_laplacian_var", 20.0
            ),
            hard_negatives_enabled=_parse_bool(runtime_cfg, "processor.hard_negatives_enabled", True),
            hard_negatives_max_per_frame=_parse_int(
                runtime_cfg, "processor.hard_negatives_max_per_frame", 8
            ),
            hard_negatives_dir=str(
                runtime_cfg.get("processor.hard_negatives_dir") or "data/hard_negatives"
            ),
            assumed_fps=_parse_float(runtime_cfg, "processor.detection_quality_assumed_fps", 7.0),
            static_temporal_min_seconds=_parse_float(
                runtime_cfg, "processor.static_temporal_min_seconds", 8.0
            ),
        )


class DetectionQualityPipeline:
    """Post-NMS quality gate (Frigate/Blue Iris patterns)."""

    def __init__(self, cfg: DetectionQualityConfig | None = None) -> None:
        self.cfg = cfg or DetectionQualityConfig()
        self._mask = DetectionMaskFilter(self.cfg.mask)
        self._static = StaticObjectFilter(self.cfg.static)
        self._prev_gray: np.ndarray | None = None
        self._log_samples = 0
        self.last_stats: dict[str, int] = {
            "rejected_ignore_mask": 0,
            "rejected_interest_zone": 0,
            "rejected_motion_verified": 0,
            "rejected_global_static": 0,
            "rejected_texture": 0,
            "rejected_static_objects": 0,
            "rejected_phantom_boxes": 0,
            "hard_negatives_saved": 0,
        }

    def reset(self) -> None:
        self._prev_gray = None
        self._static.reset()
        self._log_samples = 0
        for k in self.last_stats:
            self.last_stats[k] = 0

    def _texture_reject(self, frame_bgr: np.ndarray, box: dict[str, Any]) -> bool:
        if not self.cfg.texture_enabled:
            return False
        x1, y1, x2, y2 = [int(v) for v in box["crop_coords"]]
        h, w = frame_bgr.shape[:2]
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(w, x2), min(h, y2)
        if x2 - x1 < 8 or y2 - y1 < 8:
            return False
        crop = frame_bgr[y1:y2, x1:x2]
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        var = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        return var < self.cfg.texture_min_laplacian_var

    def _roi_motion_reject(
        self, gray: np.ndarray, prev_gray: np.ndarray, box: dict[str, Any]
    ) -> str | None:
        x1, y1, x2, y2 = [int(v) for v in box["crop_coords"]]
        roi_prev = prev_gray[y1:y2, x1:x2]
        roi_curr = gray[y1:y2, x1:x2]
        if roi_prev.size < 64 or roi_curr.size < 64:
            return None
        local = float(np.mean(cv2.absdiff(roi_curr, roi_prev)))
        if local < self.cfg.motion_min_mean_absdiff:
            return f"roi_no_motion(mean_absdiff={local:.2f})"
        return None

    def _save_hard_negative(
        self,
        frame_bgr: np.ndarray,
        box: dict[str, Any],
        reason: str,
        *,
        processor_cwd: str | None,
    ) -> None:
        if not self.cfg.hard_negatives_enabled:
            return
        saved = int(self.last_stats.get("hard_negatives_saved") or 0)
        if saved >= self.cfg.hard_negatives_max_per_frame:
            return
        x1, y1, x2, y2 = [int(v) for v in box["crop_coords"]]
        h, w = frame_bgr.shape[:2]
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(w, x2), min(h, y2)
        if x2 - x1 < 4 or y2 - y1 < 4:
            return
        crop = frame_bgr[y1:y2, x1:x2]
        root = Path(processor_cwd or Path(__file__).resolve().parents[1])
        out_dir = (root / self.cfg.hard_negatives_dir).resolve()
        out_dir.mkdir(parents=True, exist_ok=True)
        tag = reason.split("(")[0].replace(" ", "_")[:40]
        fname = out_dir / f"hn_{tag}_{saved:04d}.jpg"
        try:
            cv2.imwrite(str(fname), crop)
            self.last_stats["hard_negatives_saved"] += 1
        except OSError:
            logger.debug("hard_negative write failed: %s", fname, exc_info=True)

    def _log_reject(self, box: dict[str, Any], reason: str) -> None:
        if self._log_samples >= 8:
            return
        self._log_samples += 1
        logger.info(
            "DetectionQuality reject track=%s conf=%.3f reason=%s",
            box.get("track_id"),
            float(box.get("conf") or 0.0),
            reason,
        )

    def filter_boxes(
        self,
        boxes: list[dict[str, Any]],
        *,
        frame_bgr: np.ndarray,
        frame_index: int,
        processor_cwd: str | None = None,
    ) -> list[dict[str, Any]]:
        self.last_stats = {k: 0 for k in self.last_stats}
        gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        prev_gray = self._prev_gray
        global_static = False
        global_diff = 0.0
        if (
            self.cfg.motion_verified_enabled
            and prev_gray is not None
            and prev_gray.shape == gray.shape
        ):
            global_diff = float(np.mean(cv2.absdiff(gray, prev_gray)))
            global_static = (
                self.cfg.motion_global_static_reject
                and global_diff < self.cfg.motion_global_max_mean_absdiff
            )
        self._prev_gray = gray

        if not boxes:
            return boxes

        kept: list[dict[str, Any]] = []
        for box in boxes:
            if str(box.get("detector_label") or "") != "Bird":
                kept.append(box)
                continue
            if bool(box.get("relaxed_small_object")):
                kept.append(box)
                continue
            reason = self._mask.reject_reason(box, frame_shape=frame_bgr.shape)
            if reason:
                if "ignore_mask" in reason:
                    self.last_stats["rejected_ignore_mask"] += 1
                else:
                    self.last_stats["rejected_interest_zone"] += 1
                self._save_hard_negative(frame_bgr, box, reason, processor_cwd=processor_cwd)
                self._log_reject(box, reason)
                continue

            conf = float(box.get("conf") or 0.0)
            mreason = None
            if self.cfg.motion_verified_enabled and global_static and conf < 0.42:
                mreason = f"global_frame_static(mean_absdiff={global_diff:.2f})"
            elif (
                self.cfg.motion_verified_enabled
                and conf < 0.5
                and prev_gray is not None
                and prev_gray.shape == gray.shape
            ):
                mreason = self._roi_motion_reject(gray, prev_gray, box)
            if mreason:
                if mreason.startswith("global"):
                    self.last_stats["rejected_global_static"] += 1
                else:
                    self.last_stats["rejected_motion_verified"] += 1
                self._save_hard_negative(frame_bgr, box, mreason, processor_cwd=processor_cwd)
                self._log_reject(box, mreason)
                continue

            if conf < 0.5 and self._texture_reject(frame_bgr, box):
                reason = "texture_low_edge_energy"
                self.last_stats["rejected_texture"] += 1
                self._save_hard_negative(frame_bgr, box, reason, processor_cwd=processor_cwd)
                self._log_reject(box, reason)
                continue

            kept.append(box)

        pre_static = len(kept)
        kept = self._static.filter_boxes(kept, frame_bgr=frame_bgr, frame_index=frame_index)
        self.last_stats["rejected_static_objects"] += int(
            self._static.last_stats.get("rejected_static_objects") or 0
        )
        self.last_stats["rejected_phantom_boxes"] += int(
            self._static.last_stats.get("rejected_phantom_boxes") or 0
        )
        if pre_static > len(kept):
            self._save_hard_negative(
                frame_bgr,
                {"crop_coords": (0, 0, 1, 1), "conf": 0.0, "track_id": -1},
                "static_object_suppressed",
                processor_cwd=processor_cwd,
            )
        return kept
