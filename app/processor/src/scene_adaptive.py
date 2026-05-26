"""Universal scene analysis: MOG2 background model + adaptive confidence (no fixed masks)."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Mapping

import cv2
import numpy as np

logger = logging.getLogger(__name__)


def _parse_bool(cfg: Mapping[str, Any], key: str, default: bool) -> bool:
    try:
        raw = cfg.get(key)
    except (AttributeError, TypeError):
        return default
    if raw is None or not isinstance(raw, (bool, str, int, float)):
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
class SceneAdaptiveConfig:
    bg_enabled: bool = True
    bg_history: int = 400
    bg_var_threshold: float = 16.0
    bg_detect_shadows: bool = True
    bg_min_foreground_ratio: float = 0.07
    bg_warmup_frames: int = 45
    bg_learning_rate: float = -1.0
    adaptive_conf_enabled: bool = True
    adaptive_static_global_diff_max: float = 2.0
    adaptive_static_boost: float = 0.10
    adaptive_low_fg_ratio_max: float = 0.012
    adaptive_low_fg_boost: float = 0.06
    adaptive_night_brightness_max: float = 48.0
    adaptive_night_boost: float = 0.10
    adaptive_conf_cap: float = 0.50

    @classmethod
    def from_runtime_cfg(cls, runtime_cfg: Mapping[str, Any]) -> SceneAdaptiveConfig:
        return cls(
            bg_enabled=_parse_bool(runtime_cfg, "processor.background_subtraction_enabled", True),
            bg_history=max(50, _parse_int(runtime_cfg, "processor.background_subtraction_history", 400)),
            bg_var_threshold=_parse_float(
                runtime_cfg, "processor.background_subtraction_var_threshold", 16.0
            ),
            bg_detect_shadows=_parse_bool(
                runtime_cfg, "processor.background_subtraction_detect_shadows", True
            ),
            bg_min_foreground_ratio=_parse_float(
                runtime_cfg, "processor.background_subtraction_min_fg_ratio", 0.07
            ),
            bg_warmup_frames=max(
                10, _parse_int(runtime_cfg, "processor.background_subtraction_warmup_frames", 45)
            ),
            bg_learning_rate=_parse_float(
                runtime_cfg, "processor.background_subtraction_learning_rate", -1.0
            ),
            adaptive_conf_enabled=_parse_bool(
                runtime_cfg, "processor.scene_adaptive_conf_enabled", True
            ),
            adaptive_static_global_diff_max=_parse_float(
                runtime_cfg, "processor.scene_adaptive_static_global_diff_max", 2.0
            ),
            adaptive_static_boost=_parse_float(
                runtime_cfg, "processor.scene_adaptive_static_boost", 0.10
            ),
            adaptive_low_fg_ratio_max=_parse_float(
                runtime_cfg, "processor.scene_adaptive_low_fg_ratio_max", 0.012
            ),
            adaptive_low_fg_boost=_parse_float(
                runtime_cfg, "processor.scene_adaptive_low_fg_boost", 0.06
            ),
            adaptive_night_brightness_max=_parse_float(
                runtime_cfg, "processor.scene_adaptive_night_brightness_max", 48.0
            ),
            adaptive_night_boost=_parse_float(
                runtime_cfg, "processor.scene_adaptive_night_boost", 0.10
            ),
            adaptive_conf_cap=_parse_float(runtime_cfg, "processor.scene_adaptive_conf_cap", 0.50),
        )


@dataclass
class SceneFrameState:
    frame_index: int = 0
    global_mean_absdiff: float = 0.0
    frame_brightness: float = 0.0
    frame_foreground_ratio: float = 0.0
    bird_confidence_boost: float = 0.0
    warmed_up: bool = False


class SceneAdaptiveAnalyzer:
    """Per-stream MOG2 + scene metrics for adaptive thresholds (location-agnostic)."""

    def __init__(self, cfg: SceneAdaptiveConfig | None = None) -> None:
        self.cfg = cfg or SceneAdaptiveConfig()
        self._mog = (
            cv2.createBackgroundSubtractorMOG2(
                history=int(self.cfg.bg_history),
                varThreshold=float(self.cfg.bg_var_threshold),
                detectShadows=bool(self.cfg.bg_detect_shadows),
            )
            if self.cfg.bg_enabled
            else None
        )
        self._prev_gray: np.ndarray | None = None
        self._frame_index = 0
        self._last_fg: np.ndarray | None = None
        self.last_state = SceneFrameState()

    def reset(self) -> None:
        self._prev_gray = None
        self._frame_index = 0
        self._last_fg = None
        self.last_state = SceneFrameState()
        if self.cfg.bg_enabled:
            self._mog = cv2.createBackgroundSubtractorMOG2(
                history=int(self.cfg.bg_history),
                varThreshold=float(self.cfg.bg_var_threshold),
                detectShadows=bool(self.cfg.bg_detect_shadows),
            )
        else:
            self._mog = None

    def reconfigure(self, cfg: SceneAdaptiveConfig) -> None:
        """Apply new MOG2/adaptive settings and reset background state."""
        self.cfg = cfg
        self.reset()

    def update(self, frame_bgr: np.ndarray) -> SceneFrameState:
        self._frame_index += 1
        gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        global_diff = 0.0
        if self._prev_gray is not None and self._prev_gray.shape == gray.shape:
            global_diff = float(np.mean(cv2.absdiff(gray, self._prev_gray)))
        self._prev_gray = gray
        brightness = float(np.mean(gray))
        frame_fg = 0.0
        warmed = self._frame_index >= int(self.cfg.bg_warmup_frames)
        if self._mog is not None:
            fg = self._mog.apply(gray, learningRate=float(self.cfg.bg_learning_rate))
            if self.cfg.bg_detect_shadows:
                fg = np.where(fg == 127, 0, fg).astype(np.uint8)
            self._last_fg = fg
            frame_fg = float(np.mean(fg > 0))
        boost = 0.0
        if self.cfg.adaptive_conf_enabled:
            if global_diff < self.cfg.adaptive_static_global_diff_max:
                boost += self.cfg.adaptive_static_boost
            if frame_fg < self.cfg.adaptive_low_fg_ratio_max:
                boost += self.cfg.adaptive_low_fg_boost
            if brightness < self.cfg.adaptive_night_brightness_max:
                boost += self.cfg.adaptive_night_boost
            boost = min(boost, max(0.0, self.cfg.adaptive_conf_cap - 0.20))
        self.last_state = SceneFrameState(
            frame_index=self._frame_index,
            global_mean_absdiff=global_diff,
            frame_brightness=brightness,
            frame_foreground_ratio=frame_fg,
            bird_confidence_boost=boost,
            warmed_up=warmed,
        )
        return self.last_state

    def box_foreground_ratio(self, box: dict[str, Any], frame_shape: tuple[int, int, int]) -> float | None:
        if self._last_fg is None:
            return None
        x1, y1, x2, y2 = [int(v) for v in box["crop_coords"]]
        h, w = frame_shape[:2]
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(w, x2), min(h, y2)
        if x2 - x1 < 4 or y2 - y1 < 4:
            return None
        roi = self._last_fg[y1:y2, x1:x2]
        return float(np.mean(roi > 0))

    def background_reject_reason(
        self, box: dict[str, Any], *, frame_shape: tuple[int, int, int]
    ) -> str | None:
        if not self.cfg.bg_enabled or self._mog is None:
            return None
        if not self.last_state.warmed_up:
            return None
        ratio = self.box_foreground_ratio(box, frame_shape)
        if ratio is None:
            return None
        if ratio < self.cfg.bg_min_foreground_ratio:
            return f"bg_sub_no_foreground(fg_ratio={ratio:.3f})"
        return None

    def bird_confidence_floor(self, base_bird_min: float) -> float:
        """Adaptive floor = base + scene boost (capped). Works in any locale without masks."""
        if not self.cfg.adaptive_conf_enabled:
            return float(base_bird_min)
        return min(
            float(self.cfg.adaptive_conf_cap),
            float(base_bird_min) + float(self.last_state.bird_confidence_boost),
        )
