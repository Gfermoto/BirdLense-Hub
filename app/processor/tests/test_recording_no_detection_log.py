import os
import sys
import unittest
from unittest.mock import MagicMock, patch

current_dir = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.abspath(os.path.join(current_dir, "../src"))
sys.path.insert(0, src_path)

from recording_no_detection_log import (  # noqa: E402
    log_no_detection_activity,
    log_no_detections_after_merge,
)


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

    def test_logs_fusion_no_yolo_no_fallback_reason(self):
        api = MagicMock()
        log_no_detection_activity(
            api,
            track_count=0,
            mqtt_event_count=3,
            rejected_count=0,
            video_path_for_api="data/recordings/2026/05/16/120000/video.mp4",
            trigger_source="frigate",
            triggered_camera="Forest",
        )
        api.activity_log.assert_called_once()
        payload = api.activity_log.call_args.kwargs["data"]
        self.assertEqual(payload["reason"], "no_persisted_detections")
        self.assertEqual(payload["reason_code"], "FUSION_NO_YOLO_NO_FALLBACK")
        self.assertEqual(payload["mqtt_event_count"], 3)
        self.assertEqual(payload["triggered_camera"], "Forest")

    def test_logs_fusion_no_accepted_reason(self):
        api = MagicMock()
        log_no_detection_activity(
            api,
            track_count=2,
            mqtt_event_count=1,
            rejected_count=2,
            video_path_for_api="data/recordings/2026/05/16/120000/video.mp4",
        )
        api.activity_log.assert_called_once()
        payload = api.activity_log.call_args.kwargs["data"]
        self.assertEqual(payload["reason_code"], "FUSION_NO_ACCEPTED")
        self.assertEqual(payload["rejected_count"], 2)

    def test_skips_unknown_when_no_signals(self):
        api = MagicMock()
        log_no_detection_activity(
            api,
            track_count=0,
            mqtt_event_count=0,
            rejected_count=0,
            video_path_for_api="data/recordings/2026/05/16/120000/video.mp4",
        )
        api.activity_log.assert_not_called()


if __name__ == "__main__":
    unittest.main()
