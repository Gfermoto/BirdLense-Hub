from __future__ import annotations

import numpy as np
import pytest

pytest.importorskip("cv2")
from roi_super_resolution import build_roi_super_resolution


def test_sr_disabled_passthrough():
    sr = build_roi_super_resolution({"experimental.sr_enabled": False})
    crop = np.zeros((24, 24, 3), dtype=np.uint8)
    out, meta = sr.enhance(crop)
    assert out.shape == crop.shape
    assert meta.enabled is False


def test_sr_enabled_upscales_small_crop():
    sr = build_roi_super_resolution(
        {
            "experimental.sr_enabled": True,
            "experimental.sr_model": "fsrcnn_x2",
            "experimental.sr_scale": 2,
            "experimental.sr_min_crop_px": 8,
            "experimental.sr_max_crop_px": 64,
        }
    )
    crop = np.zeros((20, 20, 3), dtype=np.uint8)
    assert sr.should_enhance(crop, min_box_size_px=32) is True
    out, meta = sr.enhance(crop)
    assert out.shape[0] >= 40
    assert out.shape[1] >= 40
    assert meta.enabled is True
