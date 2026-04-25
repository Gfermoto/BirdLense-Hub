"""Tests for recording MQTT event window helpers."""

from __future__ import annotations

import os
import sys
import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock

current_dir = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.abspath(os.path.join(current_dir, "../src"))
sys.path.insert(0, src_path)

from recording_mqtt_window import get_recording_mqtt_events  # noqa: E402


class TestRecordingMqttWindow(unittest.TestCase):
    """Test MQTT event lookup window selection."""

    def test_returns_empty_without_aggregator(self):
        """No aggregator means no MQTT events."""
        events = get_recording_mqtt_events(
            None,
            MagicMock(),
            start_time=datetime(2026, 1, 1, tzinfo=timezone.utc),
            end_time=datetime(2026, 1, 1, 0, 0, 5, tzinfo=timezone.utc),
            merge_window=5,
            yolo_tracks_count=0,
        )

        self.assertEqual(events, [])

    def test_extends_lookback_for_frigate_trigger_without_yolo_tracks(self):
        """Frigate-triggered zero-YOLO sessions use extended lookback."""
        aggregator = MagicMock()
        aggregator.get_events_in_window.return_value = [{"source": "frigate"}]
        motion_detector = MagicMock()
        motion_detector.get_triggered_camera.return_value = "front"
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        end = datetime(2026, 1, 1, 0, 0, 5, tzinfo=timezone.utc)

        events = get_recording_mqtt_events(
            aggregator,
            motion_detector,
            start_time=start,
            end_time=end,
            merge_window=5,
            yolo_tracks_count=0,
        )

        self.assertEqual(events, [{"source": "frigate"}])
        aggregator.get_events_in_window.assert_called_once_with(
            start,
            end,
            5,
            lookback_seconds=60,
        )

    def test_uses_merge_window_when_yolo_tracks_exist(self):
        """YOLO sessions use normal merge-window lookback."""
        aggregator = MagicMock()
        motion_detector = MagicMock()
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        end = datetime(2026, 1, 1, 0, 0, 5, tzinfo=timezone.utc)

        get_recording_mqtt_events(
            aggregator,
            motion_detector,
            start_time=start,
            end_time=end,
            merge_window=5,
            yolo_tracks_count=1,
        )

        aggregator.get_events_in_window.assert_called_once_with(
            start,
            end,
            5,
            lookback_seconds=5,
        )


if __name__ == "__main__":
    unittest.main()
