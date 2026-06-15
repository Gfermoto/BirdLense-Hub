"""Unified frame dimension parsers (WxH config vs H×W metadata)."""

from __future__ import annotations

from typing import Any, Mapping

HW = tuple[int, int]  # (height, width) — OpenCV frame.shape, metadata lists
WH = tuple[int, int]  # (width, height) — config main_size, inference_lores_wh


def parse_metadata_hw(raw: Any) -> HW | None:
    """Parse JSON/list metadata stored as [height, width]."""
    if not isinstance(raw, (list, tuple)) or len(raw) < 2:
        return None
    try:
        h, w = int(raw[0]), int(raw[1])
    except (TypeError, ValueError):
        return None
    if h <= 0 or w <= 0:
        return None
    return (h, w)


def parse_config_wh(raw: Any) -> WH | None:
    """Parse processor config lists/maps as [width, height]."""
    if raw is None:
        return None
    if isinstance(raw, Mapping):
        w = raw.get("w", raw.get("width"))
        h = raw.get("h", raw.get("height"))
        if w is None or h is None:
            return None
        try:
            pw, ph = int(w), int(h)
        except (TypeError, ValueError):
            return None
        if pw <= 0 or ph <= 0:
            return None
        return (pw, ph)
    if isinstance(raw, (list, tuple)) and len(raw) >= 2:
        try:
            w, h = int(raw[0]), int(raw[1])
        except (TypeError, ValueError):
            return None
        if w <= 0 or h <= 0:
            return None
        return (w, h)
    return None


def numpy_hw(frame: Any) -> HW | None:
    """OpenCV/numpy BGR frame → (height, width)."""
    try:
        h, w = int(frame.shape[0]), int(frame.shape[1])
    except (AttributeError, IndexError, TypeError, ValueError):
        return None
    if h <= 0 or w <= 0:
        return None
    return (h, w)


def probe_wh(main_size: Any) -> WH | None:
    """Normalize ffprobe/main_size values to (width, height)."""
    if isinstance(main_size, Mapping):
        w = main_size.get("width", main_size.get("w"))
        h = main_size.get("height", main_size.get("h"))
        if w is None or h is None:
            return None
        try:
            pw, ph = int(w), int(h)
        except (TypeError, ValueError):
            return None
        if pw <= 0 or ph <= 0:
            return None
        return (pw, ph)
    wh = parse_config_wh(main_size)
    if wh is not None:
        return wh
    return None


def metadata_hw_list(shape_hw: HW) -> list[int]:
    """Serialize (H, W) for detection metadata JSON."""
    return [int(shape_hw[0]), int(shape_hw[1])]


def wh_to_hw(wh: WH) -> HW:
    return (int(wh[1]), int(wh[0]))


def hw_to_wh(hw: HW) -> WH:
    return (int(hw[1]), int(hw[0]))


def shapes_hw_equal(
    a: HW | list[int] | tuple[int, int] | None,
    b: HW | list[int] | tuple[int, int] | None,
) -> bool:
    ah = parse_metadata_hw(a)
    bh = parse_metadata_hw(b)
    if ah is None or bh is None:
        return False
    return ah == bh


def playback_hw_matches_main_size(playback_hw: HW, main_size_wh: WH) -> bool:
    """True when metadata [H,W] matches main_size (W,H)."""
    return playback_hw == wh_to_hw(main_size_wh)
