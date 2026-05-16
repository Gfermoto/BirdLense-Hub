import os
import sys
import unittest
from unittest.mock import MagicMock, patch

current_dir = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.abspath(os.path.join(current_dir, "../src"))
sys.path.insert(0, src_path)

from motion_recording_camera import resolve_motion_recording_camera_id  # noqa: E402


class TestMotionRecordingCamera(unittest.TestCase):
    def test_frigate_triggered_camera_is_explicit(self):
        motion = MagicMock()
        motion.get_triggered_camera.return_value = "Forest"
        motion.get_triggered_by.return_value = "frigate"
        self.assertEqual(
            resolve_motion_recording_camera_id(motion, default_camera_id="BirdBox"),
            "Forest",
        )

    def test_opencv_uses_recent_frigate_camera_hint(self):
        motion = MagicMock()
        motion.get_triggered_camera.return_value = None
        motion.get_triggered_by.return_value = "opencv"
        mqtt = MagicMock()
        mqtt.pick_recent_frigate_camera.return_value = "Forest"

        with patch(
            "motion_recording_camera.app_config.get",
            side_effect=lambda key, default=None: {
                "video.cameras": [{"id": "BirdBox"}, {"id": "Forest"}],
                "processor.frigate_activity_hold_seconds": 6.0,
            }.get(key, default),
        ), patch(
            "app_config.cameras.get_valid_cameras",
            side_effect=lambda cams: cams,
        ), patch(
            "app_config.cameras.cameras_for_processor",
            side_effect=lambda cams: cams,
        ):
            resolved = resolve_motion_recording_camera_id(
                motion,
                mqtt_aggregator=mqtt,
                default_camera_id="BirdBox",
            )

        self.assertEqual(resolved, "Forest")
        mqtt.pick_recent_frigate_camera.assert_called_once()

    def test_opencv_falls_back_to_default_camera(self):
        motion = MagicMock()
        motion.get_triggered_camera.return_value = None
        motion.get_triggered_by.return_value = "opencv"
        mqtt = MagicMock()
        mqtt.pick_recent_frigate_camera.return_value = None

        with patch(
            "motion_recording_camera.app_config.get",
            side_effect=lambda key, default=None: {
                "video.cameras": [{"id": "BirdBox"}, {"id": "Forest"}],
                "processor.frigate_activity_hold_seconds": 6.0,
            }.get(key, default),
        ), patch(
            "app_config.cameras.get_valid_cameras",
            side_effect=lambda cams: cams,
        ), patch(
            "app_config.cameras.cameras_for_processor",
            side_effect=lambda cams: cams,
        ):
            resolved = resolve_motion_recording_camera_id(
                motion,
                mqtt_aggregator=mqtt,
                default_camera_id="BirdBox",
            )

        self.assertEqual(resolved, "BirdBox")


if __name__ == "__main__":
    unittest.main()
