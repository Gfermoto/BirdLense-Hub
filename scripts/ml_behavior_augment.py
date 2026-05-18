"""Outdoor-camera augmentations for behavior tracklet mean RGB (#v2 retrain)."""

from __future__ import annotations

import random
from typing import Any

import numpy as np

try:
    import cv2
except ImportError as exc:  # pragma: no cover
    raise RuntimeError("opencv-python required") from exc


def augment_mean_rgb(
    rgb: np.ndarray,
    *,
    rng: random.Random | None = None,
) -> np.ndarray:
    """Return augmented uint8 RGB image (same shape as input)."""
    r = rng or random.Random()
    img = rgb.astype(np.float32).copy()
    # brightness / contrast (day-night)
    alpha = r.uniform(0.75, 1.25)
    beta = r.uniform(-25.0, 25.0)
    img = np.clip(img * alpha + beta, 0, 255)
    # HSV jitter
    bgr = cv2.cvtColor(img.astype(np.uint8), cv2.COLOR_RGB2BGR)
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV).astype(np.float32)
    hsv[:, :, 1] *= r.uniform(0.85, 1.15)
    hsv[:, :, 2] *= r.uniform(0.7, 1.3)
    hsv = np.clip(hsv, 0, 255).astype(np.uint8)
    out = cv2.cvtColor(hsv, cv2.COLOR_HSV2RGB)
    # noise / rain haze
    if r.random() < 0.35:
        noise = np.random.normal(0, r.uniform(2.0, 8.0), out.shape).astype(np.float32)
        out = np.clip(out.astype(np.float32) + noise, 0, 255).astype(np.uint8)
    if r.random() < 0.2:
        k = r.choice([3, 5])
        out = cv2.GaussianBlur(out, (k, k), r.uniform(0.3, 1.2))
    return out


def augment_tracklet_samples(
    tracklet: dict[str, Any],
    *,
    copies: int = 2,
    seed: int = 42,
) -> list[dict[str, Any]]:
    """Yield augmented tracklet dicts sharing label but new mean_rgb in-memory."""
    from shared.behavior_tracklet_crop import load_tracklet_mean_rgb

    rgb = load_tracklet_mean_rgb(tracklet)
    if rgb is None:
        return []
    rng = random.Random(int(seed) ^ hash(str(tracklet.get("tracklet_id"))))
    out: list[dict[str, Any]] = []
    for i in range(max(0, int(copies))):
        aug = augment_mean_rgb(rgb, rng=rng)
        row = dict(tracklet)
        row["augmented"] = True
        row["aug_index"] = i
        row["_mean_rgb_aug"] = aug  # consumed by trainer only
        out.append(row)
    return out
