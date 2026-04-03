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


if __name__ == '__main__':
    unittest.main()
