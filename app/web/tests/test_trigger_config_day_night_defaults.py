"""Day/night OpenCV defaults must inherit raw diff_threshold before clamping."""

from __future__ import annotations

from app_config.trigger_config import build_opencv_trigger_runtime_config


def test_day_night_inherit_raw_diff_threshold_before_clamp():
    """diff_threshold=3 clamps to 5; unset day/night still inherit raw 3 -> 5 each."""
    cfg = {"triggers": {"opencv": {"diff_threshold": 3}}}
    out = build_opencv_trigger_runtime_config(cfg)
    assert out["diff_threshold"] == 5
    assert out["day_diff_threshold"] == 5
    assert out["night_diff_threshold"] == 5


def test_empty_config_uses_default_yaml_fallbacks():
    """Partial/empty config must not use stale 18/320 Python literals."""
    out = build_opencv_trigger_runtime_config({})
    assert out["diff_threshold"] == 20
    assert out["min_contour_area"] == 360
    assert out["day_diff_threshold"] == 20
    assert out["night_diff_threshold"] == 16
    assert out["day_min_contour_area"] == 320
    assert out["night_min_contour_area"] == 220


def test_explicit_day_diff_not_replaced_by_clamped_parent():
    cfg = {"triggers": {"opencv": {"diff_threshold": 90, "day_diff_threshold": 12}}}
    out = build_opencv_trigger_runtime_config(cfg)
    assert out["diff_threshold"] == 80
    assert out["day_diff_threshold"] == 12
    assert out["night_diff_threshold"] == 80
