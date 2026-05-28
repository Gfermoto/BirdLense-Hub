"""ROI views for classifier path — avoid redundant frame copies (#511)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Union

import numpy as np

RoiCropLike = Union["RoiCropRef", np.ndarray]


@dataclass(slots=True)
class RoiCropRef:
    """View into a shared BGR frame buffer (zero-copy until classifier needs contiguous)."""

    frame: np.ndarray
    y1: int
    y2: int
    x1: int
    x2: int
    copied: bool = False

    def view(self) -> np.ndarray:
        return self.frame[self.y1 : self.y2, self.x1 : self.x2]

    def materialize_for_classifier(self) -> np.ndarray:
        crop = self.view()
        if crop.size == 0:
            return crop
        if crop.flags["C_CONTIGUOUS"]:
            return crop
        self.copied = True
        return np.ascontiguousarray(crop)


def crop_for_classifier(crop: RoiCropLike) -> tuple[np.ndarray, bool]:
    """Return BGR crop and whether a memcpy was required."""
    if isinstance(crop, RoiCropRef):
        before = crop.copied
        out = crop.materialize_for_classifier()
        return out, bool(crop.copied and not before)
    if isinstance(crop, np.ndarray):
        if crop.size == 0:
            return crop, False
        if crop.flags["C_CONTIGUOUS"]:
            return crop, False
        return np.ascontiguousarray(crop), True
    raise TypeError(f"unsupported crop type: {type(crop)!r}")


def roi_crop_ref_from_norm_bbox(
    frame: np.ndarray,
    *,
    x1: int,
    y1: int,
    x2: int,
    y2: int,
) -> RoiCropRef | None:
    h, w = frame.shape[:2]
    x1c = max(0, min(w, int(x1)))
    x2c = max(0, min(w, int(x2)))
    y1c = max(0, min(h, int(y1)))
    y2c = max(0, min(h, int(y2)))
    if x2c <= x1c or y2c <= y1c:
        return None
    return RoiCropRef(frame=frame, y1=y1c, y2=y2c, x1=x1c, x2=x2c)
