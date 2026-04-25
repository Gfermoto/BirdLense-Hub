"""Tests for no-detection finalize logging helpers."""

from __future__ import annotations

import os
import sys
import unittest
from unittest.mock import patch

current_dir = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.abspath(os.path.join(current_dir, "../src"))
sys.path.insert(0, src_path)

from recording_no_detection_log import log_no_detections_after_merge  # noqa: E402


class TestRecordingNoDetectionLog(unittest.TestCase):
    def test_warns_and_advances_next_warning_time(self):
        with (
            patch("recording_no_detection_log.logging.warning") as warn,
            patch("recording_no_detection_log.logging.debug") as debug,
        ):
            next_warn = log_no_detections_after_merge(
                track_count=3,
                mqtt_event_count=4,
                now_monotonic=10.0,
                next_warn_monotonic=5.0,
                warn_interval_seconds=120.0,
            )

        self.assertEqual(next_warn, 130.0)
        warn.assert_called_once()
        debug.assert_not_called()

    def test_debugs_inside_throttle_window(self):
        with (
            patch("recording_no_detection_log.logging.warning") as warn,
            patch("recording_no_detection_log.logging.debug") as debug,
        ):
            next_warn = log_no_detections_after_merge(
                track_count=3,
                mqtt_event_count=4,
                now_monotonic=10.0,
                next_warn_monotonic=50.0,
                warn_interval_seconds=120.0,
            )

        self.assertEqual(next_warn, 50.0)
        warn.assert_not_called()
        debug.assert_called_once()


if __name__ == "__main__":
    unittest.main()
