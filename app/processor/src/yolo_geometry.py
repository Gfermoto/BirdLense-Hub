"""Подготовка BGR под YOLO без stretch (letterbox pad=114 как у Ultralytics/YOLOv8).

Не использует ``LetterBox`` из ultralytics: в тестах ``cv2.resize`` патчится на 2-arg
lambda без ``interpolation=``.
"""

from __future__ import annotations

import numpy as np


def letterbox_bgr_to_wh(frame: np.ndarray, out_wh: tuple[int, int]) -> np.ndarray:
    """Letterbox до ``out_wh=(width,height)``. Сохраняет соотношение сторон, pad 114 BGR."""
    import cv2

    tw, th = int(out_wh[0]), int(out_wh[1])
    if tw <= 0 or th <= 0:
        raise ValueError("letterbox_bgr_to_wh: out_wh must be positive WxH")

    ih, iw = frame.shape[:2]
    r = min(tw / iw, th / ih)
    nw, nh = max(1, int(round(iw * r))), max(1, int(round(ih * r)))
    # Только позиционные аргументы — совместимо с патчами тестов (без kwargs).
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
