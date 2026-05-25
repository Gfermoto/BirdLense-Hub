"""Resolve live/regen letterbox target size from processor config."""

from __future__ import annotations

from typing import Any, Mapping, Tuple

LoResSize = Tuple[int, int]


def _clamp_side(px: int, *, lo: int = 320, hi: int = 1280) -> int:
    return max(lo, min(hi, int(px)))


def parse_inference_lores_wh(raw: Any) -> LoResSize | None:
    """``[width, height]`` or ``{w,h}`` / ``{width,height}``."""
    if raw is None:
        return None
    if isinstance(raw, Mapping):
        w = raw.get("w", raw.get("width"))
        h = raw.get("h", raw.get("height"))
        if w is None or h is None:
            return None
        return (_clamp_side(w), _clamp_side(h))
    if isinstance(raw, (list, tuple)) and len(raw) >= 2:
        try:
            return (_clamp_side(raw[0]), _clamp_side(raw[1]))
        except (TypeError, ValueError):
            return None
    return None


def resolve_inference_lores_size(app_config: Mapping[str, Any]) -> LoResSize | None:
    """
    Target WxH for detect-stream frames before YOLO.

    ``processor.detect_use_native_resolution: true`` → None (letterbox only inside detector).
    ``processor.inference_lores_wh`` — explicit detect substream size from UI/config.
    Fallback: square ``processor.inference_lores_px`` (legacy, default 640).
    """
    try:
        from pipeline_config import detect_use_native_resolution

        if detect_use_native_resolution(app_config):
            return None
    except ImportError:
        pass
    try:
        from pipeline_config import _cfg_get
    except ImportError:
        _cfg_get = lambda c, k, d=None: c.get(k, d) if hasattr(c, "get") else d  # type: ignore

    wh = parse_inference_lores_wh(_cfg_get(app_config, "processor.inference_lores_wh"))
    if wh is not None:
        return wh
    try:
        lpx = int(_cfg_get(app_config, "processor.inference_lores_px") or 640)
    except (TypeError, ValueError):
        lpx = 640
    side = _clamp_side(lpx)
    return (side, side)


def resolve_track_regen_lores_size(app_config: Mapping[str, Any]) -> LoResSize:
    """Regen lores: ``track_regen_lores_wh`` > ``track_regen_lores_px`` > live inference size."""
    wh = parse_inference_lores_wh(app_config.get("processor.track_regen_lores_wh"))
    if wh is not None:
        return wh
    try:
        lpx = int(app_config.get("processor.track_regen_lores_px") or 0)
    except (TypeError, ValueError):
        lpx = 0
    if lpx > 0:
        side = _clamp_side(lpx)
        return (side, side)
    return resolve_inference_lores_size(app_config)
