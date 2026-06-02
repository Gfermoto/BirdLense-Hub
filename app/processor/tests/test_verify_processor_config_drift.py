"""Tests for scripts/verify_processor_config_drift.py."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]


def _load_mod():
    path = _REPO_ROOT / "scripts" / "verify_processor_config_drift.py"
    spec = importlib.util.spec_from_file_location("verify_processor_config_drift", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["verify_processor_config_drift"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_no_drift_when_user_matches_default():
    mod = _load_mod()
    default = {
        "processor": {
            "min_confidence_binary": 0.12,
            "track_static_reject_min_frames": 4,
            "track_static_reject_min_duration_sec": 2.0,
            "track_static_reject_max_center_dispersion_norm": 0.085,
            "track_static_reject_max_relative_center_dispersion": 0.16,
            "track_static_reject_max_bbox_iou_first_last_min": 0.74,
        }
    }
    report = mod.evaluate_processor_config_drift(default=default, user={})
    assert report["ok"] is True
    assert report["drift_count"] == 0


def test_detects_stricter_track_static_and_camera_conf():
    mod = _load_mod()
    default = {
        "processor": {
            "min_confidence_binary": 0.12,
            "track_static_reject_min_frames": 4,
            "track_static_reject_min_duration_sec": 2.0,
            "track_static_reject_max_center_dispersion_norm": 0.085,
            "track_static_reject_max_relative_center_dispersion": 0.16,
            "track_static_reject_max_bbox_iou_first_last_min": 0.74,
            "camera_overrides": {},
        }
    }
    user = {
        "processor": {
            "track_static_reject_min_frames": 18,
            "camera_overrides": {
                "BirdBox": {"min_confidence_binary": 0.26},
            },
        }
    }
    report = mod.evaluate_processor_config_drift(default=default, user=user)
    assert report["ok"] is False
    paths = {item["path"] for item in report["drifts"]}
    assert "processor.track_static_reject_min_frames" in paths
    assert "processor.camera_overrides.BirdBox.min_confidence_binary" in paths
