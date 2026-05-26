"""MOG2 / static-filter calibration previews for SOTA-08 (shared web + processor tests)."""

from __future__ import annotations

import base64
from dataclasses import asdict
from typing import Any, Mapping

import cv2
import numpy as np

from scene_adaptive import SceneAdaptiveAnalyzer, SceneAdaptiveConfig


def _clamp_float(value: Any, default: float, lo: float, hi: float) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    return max(lo, min(hi, out))


def _clamp_int(value: Any, default: int, lo: int, hi: int) -> int:
    try:
        out = int(value)
    except (TypeError, ValueError):
        return default
    return max(lo, min(hi, out))


def render_mog2_foreground_mask(
    gray: np.ndarray,
    *,
    history: int = 300,
    var_threshold: float = 24.0,
    detect_shadows: bool = False,
    warmup_frames: int = 5,
) -> np.ndarray:
    """Single-stream MOG2 mask (uint8 0/255) after morphology."""
    h, w = gray.shape[:2]
    mog = cv2.createBackgroundSubtractorMOG2(
        history=max(30, int(history)),
        varThreshold=max(4.0, float(var_threshold)),
        detectShadows=bool(detect_shadows),
    )
    fg = np.zeros((h, w), dtype=np.uint8)
    for _ in range(max(1, int(warmup_frames))):
        raw = mog.apply(gray)
        if detect_shadows:
            raw = np.where(raw == 127, 0, raw).astype(np.uint8)
        fg = raw
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    fg = cv2.morphologyEx(fg, cv2.MORPH_OPEN, kernel, iterations=1)
    fg = cv2.dilate(fg, None, iterations=2)
    return fg


def overlay_mask_on_bgr(
    frame_bgr: np.ndarray,
    mask: np.ndarray,
    *,
    color_bgr: tuple[int, int, int] = (0, 0, 255),
    alpha: float = 0.45,
) -> np.ndarray:
    """Blend colored mask onto BGR frame."""
    if frame_bgr is None or mask is None:
        return frame_bgr
    if mask.shape[:2] != frame_bgr.shape[:2]:
        mask = cv2.resize(mask, (frame_bgr.shape[1], frame_bgr.shape[0]), interpolation=cv2.INTER_NEAREST)
    overlay = frame_bgr.copy()
    tint = np.zeros_like(frame_bgr)
    tint[:, :] = color_bgr
    active = mask > 0
    if not np.any(active):
        return overlay
    blended = cv2.addWeighted(frame_bgr, 1.0 - alpha, tint, alpha, 0)
    overlay[active] = blended[active]
    return overlay


def jpeg_base64_from_bgr(frame_bgr: np.ndarray, *, quality: int = 82) -> str:
    ok, buf = cv2.imencode(".jpg", frame_bgr, [int(cv2.IMWRITE_JPEG_QUALITY), int(quality)])
    if not ok:
        raise ValueError("jpeg_encode_failed")
    return base64.b64encode(buf.tobytes()).decode("ascii")


def build_detection_mog2_preview(
    frame_bgr: np.ndarray,
    scene_cfg: SceneAdaptiveConfig | Mapping[str, Any] | None = None,
    *,
    warmup_frames: int | None = None,
) -> dict[str, Any]:
    """Processor.background_subtraction_* preview (YOLO static-bg rejection path)."""
    cfg = (
        scene_cfg
        if isinstance(scene_cfg, SceneAdaptiveConfig)
        else SceneAdaptiveConfig.from_runtime_cfg(scene_cfg or {})
    )
    gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
    analyzer = SceneAdaptiveAnalyzer(cfg)
    warm = warmup_frames if warmup_frames is not None else max(10, int(cfg.bg_warmup_frames))
    for _ in range(max(1, int(warm))):
        analyzer.update(frame_bgr)
    mask = analyzer._last_fg
    if mask is None:
        mask = render_mog2_foreground_mask(
            gray,
            history=cfg.bg_history,
            var_threshold=cfg.bg_var_threshold,
            detect_shadows=cfg.bg_detect_shadows,
            warmup_frames=warm,
        )
    fg_ratio = float(np.mean(mask > 0)) if mask is not None else 0.0
    composite = overlay_mask_on_bgr(frame_bgr, mask if mask is not None else np.zeros_like(gray))
    return {
        "mode": "detection_mog2",
        "foreground_pixel_fraction": round(fg_ratio, 6),
        "frame_brightness": round(float(analyzer.last_state.frame_brightness), 2),
        "warmed_up": bool(analyzer.last_state.warmed_up),
        "config": asdict(cfg),
        "image_jpeg_base64": jpeg_base64_from_bgr(composite),
        "mask_jpeg_base64": jpeg_base64_from_bgr(
            cv2.cvtColor(mask if mask is not None else np.zeros_like(gray), cv2.COLOR_GRAY2BGR)
        ),
    }


def build_trigger_mog2_preview(
    frame_bgr: np.ndarray,
    opencv_cfg: Mapping[str, Any],
) -> dict[str, Any]:
    """triggers.opencv MOG2 motion-trigger preview."""
    gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
    history = _clamp_int(opencv_cfg.get("mog2_history"), 300, 30, 2000)
    var_threshold = _clamp_float(opencv_cfg.get("mog2_var_threshold"), 24.0, 4.0, 128.0)
    detect_shadows = bool(opencv_cfg.get("mog2_detect_shadows", False))
    warm = _clamp_int(opencv_cfg.get("suppress_warmup_frames"), 45, 1, 300)
    mask = render_mog2_foreground_mask(
        gray,
        history=history,
        var_threshold=var_threshold,
        detect_shadows=detect_shadows,
        warmup_frames=min(30, warm),
    )
    fg_ratio = float(np.mean(mask > 0))
    min_area = _clamp_int(
        opencv_cfg.get("mog2_min_contour_area") or opencv_cfg.get("min_contour_area"),
        220,
        20,
        50000,
    )
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    motion_contours = sum(1 for c in contours if cv2.contourArea(c) >= min_area)
    composite = overlay_mask_on_bgr(frame_bgr, mask, color_bgr=(0, 180, 255))
    return {
        "mode": "trigger_mog2",
        "foreground_pixel_fraction": round(fg_ratio, 6),
        "motion_contours_above_min_area": int(motion_contours),
        "min_contour_area": int(min_area),
        "config": {
            "mog2_history": history,
            "mog2_var_threshold": var_threshold,
            "mog2_detect_shadows": detect_shadows,
            "mog2_min_contour_area": min_area,
            "detection_method": str(opencv_cfg.get("detection_method") or "frame_diff"),
        },
        "image_jpeg_base64": jpeg_base64_from_bgr(composite),
        "mask_jpeg_base64": jpeg_base64_from_bgr(cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR)),
    }


def calibration_warnings(
    *,
    mode: str,
    foreground_pixel_fraction: float,
    processor_cfg: Mapping[str, Any] | None = None,
    opencv_cfg: Mapping[str, Any] | None = None,
) -> list[dict[str, str]]:
    """Heuristic FN/FP hints for UI."""
    warnings: list[dict[str, str]] = []
    fg = float(foreground_pixel_fraction)
    proc = processor_cfg or {}
    ocv = opencv_cfg or {}

    if mode == "detection_mog2":
        min_fg = _clamp_float(proc.get("background_subtraction_min_fg_ratio"), 0.07, 0.0, 1.0)
        if min_fg > 0.12:
            warnings.append(
                {
                    "level": "warning",
                    "code": "fn_risk_high_min_fg",
                    "message": "High min foreground ratio may reject real birds on static feeders (FN risk).",
                }
            )
        if min_fg < 0.03:
            warnings.append(
                {
                    "level": "warning",
                    "code": "fp_risk_low_min_fg",
                    "message": "Very low min foreground ratio keeps boxes on background (FP risk).",
                }
            )
        var_t = _clamp_float(proc.get("background_subtraction_var_threshold"), 16.0, 4.0, 128.0)
        if var_t < 8:
            warnings.append(
                {
                    "level": "info",
                    "code": "fp_risk_sensitive_mog2",
                    "message": "Low varThreshold marks more pixels as motion (more FP on branches/IR).",
                }
            )
    elif mode == "trigger_mog2":
        min_area = _clamp_int(ocv.get("mog2_min_contour_area") or ocv.get("min_contour_area"), 220, 20, 50000)
        if min_area > 500:
            warnings.append(
                {
                    "level": "warning",
                    "code": "fn_risk_large_contour",
                    "message": "Large min contour area may miss small/distant birds (FN risk).",
                }
            )
        if fg > 0.35:
            warnings.append(
                {
                    "level": "warning",
                    "code": "fp_risk_global_motion",
                    "message": "Foreground covers much of the frame — check wind/IR or lower sensitivity.",
                }
            )
    if proc.get("static_object_suppression_enabled") is True:
        jitter = _clamp_float(proc.get("static_temporal_max_jitter_px"), 2.0, 0.5, 32.0)
        if jitter < 1.5:
            warnings.append(
                {
                    "level": "warning",
                    "code": "fn_risk_tight_jitter",
                    "message": "Tight static jitter threshold may suppress slow-moving birds (FN risk).",
                }
            )
        bird_floor = _clamp_float(proc.get("static_scene_bird_min_confidence"), 0.25, 0.0, 1.0)
        if bird_floor > 0.4:
            warnings.append(
                {
                    "level": "warning",
                    "code": "fn_risk_high_static_conf",
                    "message": "High static scene bird floor rejects low-confidence real detections.",
                }
            )
    return warnings
