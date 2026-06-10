import os
import sys
import unittest
from unittest.mock import patch

current_dir = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.abspath(os.path.join(current_dir, "../src"))
sys.path.insert(0, src_path)

from recording_session import _camera_processor_overrides  # noqa: E402


class TestCameraTuningRole(unittest.TestCase):
    @patch("recording_session.get_valid_cameras")
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

    @patch("recording_session.get_valid_cameras")
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

    @patch("recording_session.get_valid_cameras")
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
