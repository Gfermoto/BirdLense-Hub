import os
import sys
import unittest
from unittest.mock import patch

import yaml

current_dir = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.abspath(os.path.join(current_dir, "../src"))
project_root = os.path.abspath(os.path.join(current_dir, "../../.."))
sys.path.insert(0, src_path)

from recording_session import _camera_processor_overrides  # noqa: E402


def _default_feeder_far_role() -> dict:
    path = os.path.join(project_root, "app", "app_config", "default_config.yaml")
    with open(path, encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)
    return (cfg.get("processor") or {}).get("camera_tuning_by_role", {}).get("feeder_far") or {}


def _default_feeder_close_role() -> dict:
    path = os.path.join(project_root, "app", "app_config", "default_config.yaml")
    with open(path, encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)
    return (cfg.get("processor") or {}).get("camera_tuning_by_role", {}).get("feeder_close") or {}


class TestCameraTuningRole(unittest.TestCase):
    @patch("app_config.cameras.get_valid_cameras")
    @patch("recording_session.app_config")
    def test_role_preset_merged_before_per_camera(self, mock_cfg, mock_cameras):
        mock_cameras.return_value = [
            {"id": "Forest", "tuning_role": "feeder_far"},
        ]
        mock_cfg.get.side_effect = lambda key, default=None: {
            "processor.camera_tuning_by_role.feeder_far": {
                "track_static_reject_min_frames": 3,
            },
            "processor.camera_overrides.Forest": {
                "track_static_reject_min_frames": 5,
            },
        }.get(key, default)

        out = _camera_processor_overrides("Forest")
        self.assertEqual(out["track_static_reject_min_frames"], 5)

    @patch("app_config.cameras.get_valid_cameras")
    @patch("recording_session.app_config")
    def test_role_only_when_no_per_camera(self, mock_cfg, mock_cameras):
        mock_cameras.return_value = [
            {"id": "BirdBox", "tuning_role": "feeder_close"},
        ]
        mock_cfg.get.side_effect = lambda key, default=None: {
            "processor.camera_tuning_by_role.feeder_close": {
                "min_confidence_binary": 0.12,
            },
        }.get(key, default)

        out = _camera_processor_overrides("BirdBox")
        self.assertEqual(out["min_confidence_binary"], 0.12)

    def test_feeder_far_defaults_support_weak_distant_detections(self):
        role = _default_feeder_far_role()
        self.assertLessEqual(float(role.get("min_confidence_binary_bird") or 1.0), 0.08)
        self.assertLessEqual(float(role.get("openvino_min_confidence_binary_bird") or 1.0), 0.08)
        self.assertLessEqual(int(role.get("min_box_size_px") or 999), 10)
        self.assertTrue(bool(role.get("track_to_predict_fallback_enabled")))

    def test_feeder_close_defaults_allow_edge_perches_and_static_birds(self):
        role = _default_feeder_close_role()
        self.assertLessEqual(float(role.get("min_center_dist") or 1.0), 0.02)
        self.assertLessEqual(float(role.get("scoring_moving_roi_min_motion_score") or 1.0), 0.22)
        self.assertLessEqual(float(role.get("min_confidence_binary_bird") or 1.0), 0.03)

    @patch("app_config.cameras.get_valid_cameras")
    @patch("recording_session.app_config")
    def test_legacy_detection_overrides_merged_before_processor(self, mock_cfg, mock_cameras):
        mock_cameras.return_value = [{"id": "BirdBox"}]
        mock_cfg.get.side_effect = lambda key, default=None: {
            "detection.camera_overrides.BirdBox": {
                "min_confidence_binary": 0.12,
                "min_track_duration": 0.5,
            },
            "processor.camera_overrides.BirdBox": {
                "min_confidence_binary": 0.08,
            },
        }.get(key, default)

        out = _camera_processor_overrides("BirdBox")
        self.assertEqual(out["min_confidence_binary"], 0.08)
        self.assertEqual(out["min_track_duration"], 0.5)


if __name__ == "__main__":
    unittest.main()
