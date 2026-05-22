"""Подготовка BGR под YOLO без stretch (letterbox pad=114 как у Ultralytics/YOLOv8).

Не использует ``LetterBox`` из ultralytics: в тестах ``cv2.resize`` патчится на 2-arg
lambda без ``interpolation=``.
"""

from __future__ import annotations

import numpy as np


def _resolve_resize_interpolation() -> int:
    """Map config/env interpolation mode to cv2 constant."""
    import os
    from app_config.app_config import app_config
    import cv2

    raw = (os.environ.get("BIRDLENSE_RESIZE_INTERPOLATION") or "").strip().lower()
    if not raw:
        raw = str(app_config.get("processor.letterbox_resize_interpolation", "linear") or "linear").strip().lower()
    mapping = {
        "nearest": cv2.INTER_NEAREST,
        "linear": cv2.INTER_LINEAR,
        "cubic": cv2.INTER_CUBIC,
        "area": cv2.INTER_AREA,
        "lanczos": cv2.INTER_LANCZOS4,
    }
    return mapping.get(raw, cv2.INTER_LINEAR)


def _maybe_enhance_low_res_frame(frame: np.ndarray) -> np.ndarray:
    """Apply lightweight low-res enhancement before letterbox resize."""
    import cv2
    from app_config.app_config import app_config

    if not bool(app_config.get("processor.lowres_enhance_enabled", True)):
        return frame
    ih, iw = frame.shape[:2]
    max_side = int(max(iw, ih))
    max_input_px = int(app_config.get("processor.lowres_enhance_max_input_px", 800) or 800)
    if max_side > max_input_px:
        return frame
    amount = float(app_config.get("processor.lowres_sharpen_amount", 0.32) or 0.32)
    amount = max(0.0, min(1.0, amount))
    if amount <= 0.0:
        return frame
    blur = cv2.GaussianBlur(frame, (0, 0), sigmaX=1.0, sigmaY=1.0)
    enhanced = cv2.addWeighted(frame, 1.0 + amount, blur, -amount, 0)
    return enhanced


def frame_matches_target_wh(
    frame: np.ndarray,
    out_wh: tuple[int, int],
    *,
    tolerance_px: int = 2,
) -> bool:
    """True when frame already matches target WxH (skip redundant resize)."""
    tw, th = int(out_wh[0]), int(out_wh[1])
    ih, iw = frame.shape[:2]
    tol = max(0, int(tolerance_px))
    return abs(iw - tw) <= tol and abs(ih - th) <= tol


def prepare_detector_frame(
    frame: np.ndarray,
    out_wh: tuple[int, int],
    *,
    skip_letterbox_when_size_matches: bool = True,
) -> np.ndarray:
    """Letterbox to ``out_wh`` unless frame is already native detect size."""
    if skip_letterbox_when_size_matches and frame_matches_target_wh(frame, out_wh):
        out = _maybe_enhance_low_res_frame(frame)
        return np.ascontiguousarray(out)
    return letterbox_bgr_to_wh(frame, out_wh)


def letterbox_bgr_to_wh(frame: np.ndarray, out_wh: tuple[int, int]) -> np.ndarray:
    """Letterbox до ``out_wh=(width,height)``. Сохраняет соотношение сторон, pad 114 BGR."""
    import cv2

    tw, th = int(out_wh[0]), int(out_wh[1])
    if tw <= 0 or th <= 0:
        raise ValueError("letterbox_bgr_to_wh: out_wh must be positive WxH")

    ih, iw = frame.shape[:2]
    frame = _maybe_enhance_low_res_frame(frame)
    r = min(tw / iw, th / ih)
    nw, nh = max(1, int(round(iw * r))), max(1, int(round(ih * r)))
    # Prefer explicit interpolation, but keep fallback for tests that monkeypatch cv2.resize with 2-arg lambda.
    interp = _resolve_resize_interpolation()
    try:
        resized = cv2.resize(frame, (nw, nh), None, 0.0, 0.0, interp)
    except TypeError:
        resized = cv2.resize(frame, (nw, nh))
    pad_x, pad_y = tw - nw, th - nh
    top, bottom = pad_y // 2, pad_y - pad_y // 2
    left, right = pad_x // 2, pad_x - pad_x // 2
    out = cv2.copyMakeBorder(
        resized,
        top,
        bottom,
        left,
        right,
        cv2.BORDER_CONSTANT,
        value=(114, 114, 114),
    )
    return np.ascontiguousarray(out)
