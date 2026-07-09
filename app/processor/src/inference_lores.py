"""Resolve live/regen letterbox target size from processor config."""

from __future__ import annotations

from typing import Any, Mapping, Tuple

from shared.frame_shape import parse_config_wh

LoResSize = Tuple[int, int]


def _clamp_side(px: int, *, lo: int = 320, hi: int = 1280) -> int:
    return max(lo, min(hi, int(px)))


def parse_inference_lores_wh(raw: Any) -> LoResSize | None:
    """``[width, height]`` or ``{w,h}`` / ``{width,height}``."""
    wh = parse_config_wh(raw)
    if wh is None:
        return None
    return (_clamp_side(wh[0]), _clamp_side(wh[1]))


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

        def _cfg_get(c, k, d=None):  # type: ignore[no-untyped-def]
            return c.get(k, d) if hasattr(c, "get") else d

    wh = parse_inference_lores_wh(_cfg_get(app_config, "processor.inference_lores_wh"))
    if wh is not None:
        return wh
    try:
        lpx = int(_cfg_get(app_config, "processor.inference_lores_px") or 0)
    except (TypeError, ValueError):
        lpx = 0
    if lpx > 0:
        side = _clamp_side(lpx)
        return (side, side)
    return None


def resolve_track_regen_lores_size(app_config: Mapping[str, Any]) -> LoResSize | None:
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
