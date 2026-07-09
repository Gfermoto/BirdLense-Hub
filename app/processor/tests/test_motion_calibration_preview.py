"""SOTA-08: motion calibration preview helpers."""

from __future__ import annotations

import numpy as np
import pytest

from motion_calibration_preview import (
    build_detection_mog2_preview,
    build_trigger_mog2_preview,
    calibration_warnings,
    render_mog2_foreground_mask,
)


@pytest.fixture
def synthetic_frame():
    frame = np.zeros((120, 160, 3), dtype=np.uint8)
    frame[40:80, 50:110] = (180, 180, 180)
    return frame


def test_render_mog2_foreground_mask_non_empty(synthetic_frame):
    gray = synthetic_frame[:, :, 0]
    mask = render_mog2_foreground_mask(gray, warmup_frames=3)
    assert mask.shape == gray.shape
    assert mask.dtype == np.uint8


def test_build_detection_mog2_preview_returns_images(synthetic_frame):
    out = build_detection_mog2_preview(
        synthetic_frame,
        {
            "processor.background_subtraction_enabled": True,
            "processor.background_subtraction_history": 50,
            "processor.background_subtraction_var_threshold": 16.0,
            "processor.background_subtraction_min_fg_ratio": 0.07,
            "processor.background_subtraction_warmup_frames": 5,
            "processor.background_subtraction_detect_shadows": False,
        },
    )
    assert out["mode"] == "detection_mog2"
    assert out.get("image_jpeg_base64")
    assert out.get("mask_jpeg_base64")


def test_build_trigger_mog2_preview(synthetic_frame):
    out = build_trigger_mog2_preview(
        synthetic_frame,
        {
            "mog2_history": 80,
            "mog2_var_threshold": 20.0,
            "mog2_detect_shadows": False,
            "mog2_min_contour_area": 100,
            "suppress_warmup_frames": 5,
        },
    )
    assert out["mode"] == "trigger_mog2"
    assert "foreground_pixel_fraction" in out


def test_calibration_warnings_fn_risk():
    warns = calibration_warnings(
        mode="detection_mog2",
        foreground_pixel_fraction=0.01,
        processor_cfg={"background_subtraction_min_fg_ratio": 0.2},
    )
    codes = {w["code"] for w in warns}
    assert "fn_risk_high_min_fg" in codes
