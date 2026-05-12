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


def letterbox_bgr_to_wh(frame: np.ndarray, out_wh: tuple[int, int]) -> np.ndarray:
    """Letterbox до ``out_wh=(width,height)``. Сохраняет соотношение сторон, pad 114 BGR."""
    import cv2

    tw, th = int(out_wh[0]), int(out_wh[1])
    if tw <= 0 or th <= 0:
        raise ValueError("letterbox_bgr_to_wh: out_wh must be positive WxH")

    ih, iw = frame.shape[:2]
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
