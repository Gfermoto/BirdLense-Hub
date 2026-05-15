"""Tests for motion detector factory fallback behavior."""

import os
import sys
import unittest


current_dir = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.abspath(os.path.join(current_dir, '../src'))
sys.path.append(src_path)


from motion_detectors.factory import build_motion_detector
from motion_detectors.opencv_motion import OpenCVMotionDetector
from motion_detectors.or_motion import OrMotionDetector
from processor_runtime_stats import reset_runtime_stats_for_tests, runtime_stats_snapshot


class TestMotionDetectorFactory(unittest.TestCase):
    def test_frigate_source_keeps_opencv_fallback(self):
        media_source = type(
            'FakeMediaSource',
            (),
            {'capture': lambda self: None},
        )()
        primary = object()

        detector = build_motion_detector(
            motion_source='frigate',
            media_source=media_source,
            primary=primary,
            mqtt_broker='mqtt.local',
            mqtt_topic='',
            mqtt_port=1883,
            mqtt_username=None,
            mqtt_password=None,
            check_every_n_frames=2,
        )

        self.assertIsInstance(detector, OrMotionDetector)
        self.assertIs(detector._primary, primary)
        self.assertIsInstance(detector._additional, OpenCVMotionDetector)

    def test_frigate_without_primary_is_opencv_only(self):
        media_source = type(
            'FakeMediaSource',
            (),
            {'capture': lambda self: None},
        )()

        detector = build_motion_detector(
            motion_source='frigate',
            media_source=media_source,
            primary=None,
            mqtt_broker='',
            mqtt_topic='',
            check_every_n_frames=2,
        )

        self.assertIsInstance(detector, OpenCVMotionDetector)

    def test_opencv_with_primary_uses_or(self):
        media_source = type(
            'FakeMediaSource',
            (),
            {'capture': lambda self: None},
        )()
        primary = object()

        detector = build_motion_detector(
            motion_source='opencv',
            media_source=media_source,
            primary=primary,
            check_every_n_frames=2,
        )

        self.assertIsInstance(detector, OrMotionDetector)
        self.assertIs(detector._primary, primary)
        self.assertIsInstance(detector._additional, OpenCVMotionDetector)

    def test_grouped_frigate_unavailable_falls_back_to_opencv_and_increments_counter(self):
        reset_runtime_stats_for_tests()
        media_source = type(
            'FakeMediaSource',
            (),
            {'capture': lambda self: None},
        )()
        trigger_config = {
            "opencv": {
                "enabled": False,
                "check_every_n_frames": 1,
                "diff_threshold": 18,
                "min_contour_area": 320,
            },
            "frigate": {"enabled": True, "topic": "frigate/events"},
            "motion_sensor": {
                "enabled": False,
                "source": "mqtt",
                "mqtt_topic": "",
                "esphome_url": "",
                "esphome_sensor_id": "",
            },
            "scales": {"enabled": False},
        }
        detector = build_motion_detector(
            trigger_config=trigger_config,
            media_source=media_source,
            frigate_detector=None,
            mqtt_broker="mqtt.local",
        )
        self.assertIsInstance(detector, OpenCVMotionDetector)
        snap = runtime_stats_snapshot()
        self.assertEqual(
            snap["counters"].get("trigger_motion_factory_frigate_fallback_opencv_total"),
            1,
        )


if __name__ == '__main__':
    unittest.main()
