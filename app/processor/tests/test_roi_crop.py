"""RoiCropRef zero-copy path (#511)."""

from __future__ import annotations

import numpy as np

from roi_crop import RoiCropRef, crop_for_classifier, roi_crop_ref_from_norm_bbox


def test_roi_crop_ref_view_shares_buffer():
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    ref = roi_crop_ref_from_norm_bbox(frame, x1=10, y1=20, x2=40, y2=50)
    assert ref is not None
    view = ref.view()
    assert view.base is frame or np.shares_memory(view, frame)
    out, _copied = crop_for_classifier(ref)
    assert out.shape == (30, 30, 3)


def test_roi_crop_ref_full_row_slice_avoids_copy_when_contiguous():
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    ref = RoiCropRef(frame=frame, y1=20, y2=50, x1=0, x2=100)
    out, copied = crop_for_classifier(ref)
    assert copied is False
    assert out.flags["C_CONTIGUOUS"]


def test_crop_for_classifier_non_contiguous_copies():
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    sliced = frame[20:50:2, 10:40:2]
    out, copied = crop_for_classifier(sliced)
    assert copied is True
    assert out.flags["C_CONTIGUOUS"]
