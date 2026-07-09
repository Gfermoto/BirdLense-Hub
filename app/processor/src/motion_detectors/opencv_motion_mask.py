"""Frigate-style normalized motion exclusion masks for OpenCV trigger."""

from __future__ import annotations

import re
from typing import Iterable

import cv2
import numpy as np


def parse_normalized_polygon(spec: str) -> np.ndarray | None:
    """
    Parse Frigate motion mask coordinates: ``x1,y1,x2,y2,...`` in 0..1 space.

    Returns Nx2 float32 polygon or None if invalid.
    """
    text = str(spec or "").strip()
    if not text:
        return None
    parts = [p.strip() for p in re.split(r"[\s,;]+", text) if p.strip()]
    if len(parts) < 6 or len(parts) % 2 != 0:
        return None
    try:
        nums = [float(p) for p in parts]
    except ValueError:
        return None
    pts = np.array(list(zip(nums[0::2], nums[1::2])), dtype=np.float32)
    if pts.shape[0] < 3:
        return None
    return pts


def build_exclusion_mask(
    shape_hw: tuple[int, int],
    polygons: Iterable[str],
) -> np.ndarray | None:
    """
    Build uint8 mask (255 = ignore motion) for frame shape (H, W).

    Polygons use normalized coordinates like Frigate ``motion.mask``.
    """
    h, w = int(shape_hw[0]), int(shape_hw[1])
    if h <= 0 or w <= 0:
        return None
    specs = [str(p).strip() for p in polygons if str(p).strip()]
    if not specs:
        return None
    mask = np.zeros((h, w), dtype=np.uint8)
    for spec in specs:
        poly_norm = parse_normalized_polygon(spec)
        if poly_norm is None:
            continue
        poly_px = np.zeros_like(poly_norm)
        poly_px[:, 0] = np.clip(poly_norm[:, 0], 0.0, 1.0) * float(w)
        poly_px[:, 1] = np.clip(poly_norm[:, 1], 0.0, 1.0) * float(h)
        cv2.fillPoly(mask, [poly_px.astype(np.int32)], 255)
    if not int(cv2.countNonZero(mask)):
        return None
    return mask


def apply_exclusion_mask(
    binary_mask: np.ndarray,
    exclusion_mask: np.ndarray | None,
) -> np.ndarray:
    """Zero motion inside excluded regions (Frigate motion mask semantics)."""
    if exclusion_mask is None:
        return binary_mask
    if binary_mask.shape != exclusion_mask.shape:
        return binary_mask
    out = binary_mask.copy()
    out[exclusion_mask > 0] = 0
    return out
