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
import recording_mqtt_window as rmw  # noqa: E402


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
            lookback_seconds=15,
        )

    def test_uses_merge_window_when_yolo_tracks_exist(self):
        """OpenCV-triggered YOLO sessions use normal merge-window lookback."""
        aggregator = MagicMock()
        motion_detector = MagicMock()
        motion_detector.get_triggered_camera.return_value = "front"
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        end = datetime(2026, 1, 1, 0, 0, 5, tzinfo=timezone.utc)

        get_recording_mqtt_events(
            aggregator,
            motion_detector,
            start_time=start,
            end_time=end,
            merge_window=5,
            yolo_tracks_count=1,
            trigger_source="opencv",
        )

        aggregator.get_events_in_window.assert_called_once_with(
            start,
            end,
            5,
            lookback_seconds=5,
        )

    def test_extends_lookback_for_frigate_trigger_with_yolo_tracks(self):
        """Frigate-triggered sessions keep extended lookback so MQTT can merge into YOLO tracks."""
        aggregator = MagicMock()
        motion_detector = MagicMock()
        motion_detector.get_triggered_camera.return_value = "BirdBox"
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        end = datetime(2026, 1, 1, 0, 0, 5, tzinfo=timezone.utc)

        get_recording_mqtt_events(
            aggregator,
            motion_detector,
            start_time=start,
            end_time=end,
            merge_window=6,
            yolo_tracks_count=3,
            trigger_source="frigate",
            lookback_camera_id="BirdBox",
        )

        aggregator.get_events_in_window.assert_called_once_with(
            start,
            end,
            6,
            lookback_seconds=15,
        )

    def test_scope_camera_id_filters_frigate_only(self):
        """Explicit scope camera keeps only matching Frigate events."""
        aggregator = MagicMock()
        aggregator.get_events_in_window.return_value = [
            {"source": "frigate", "camera": "front"},
            {"source": "frigate", "camera": "side"},
            {"source": "birdnet"},
        ]
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
            scope_camera_id="side",
        )

        self.assertEqual(
            events,
            [
                {"source": "frigate", "camera": "side"},
                {"source": "birdnet"},
            ],
        )

    def test_without_scope_camera_does_not_filter_frigate_events(self):
        """Detector camera is used for lookback only, not for filtering."""
        aggregator = MagicMock()
        aggregator.get_events_in_window.return_value = [
            {'source': 'frigate', 'camera': 'front'},
            {'source': 'frigate', 'camera': 'side'},
        ]
        motion_detector = MagicMock()
        motion_detector.get_triggered_camera.return_value = 'front'
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        end = datetime(2026, 1, 1, 0, 0, 5, tzinfo=timezone.utc)

        events = get_recording_mqtt_events(
            aggregator,
            motion_detector,
            start_time=start,
            end_time=end,
            merge_window=5,
            yolo_tracks_count=0,
            scope_camera_id=None,
        )

        self.assertEqual(
            events,
            [
                {'source': 'frigate', 'camera': 'front'},
                {'source': 'frigate', 'camera': 'side'},
            ],
        )

    def test_lookback_uses_explicit_camera_id(self):
        """Lookback extension uses session camera, not mutable detector state."""
        aggregator = MagicMock()
        aggregator.get_events_in_window.return_value = []
        motion_detector = MagicMock()
        motion_detector.get_triggered_camera.return_value = None
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        end = datetime(2026, 1, 1, 0, 0, 5, tzinfo=timezone.utc)

        get_recording_mqtt_events(
            aggregator,
            motion_detector,
            start_time=start,
            end_time=end,
            merge_window=5,
            yolo_tracks_count=0,
            scope_camera_id=None,
            lookback_camera_id='session-cam',
        )

        aggregator.get_events_in_window.assert_called_once_with(
            start,
            end,
            5,
            lookback_seconds=15,
        )

    def test_scope_drop_increments_runtime_counter(self):
        aggregator = MagicMock()
        aggregator.get_events_in_window.return_value = [
            {"source": "frigate", "camera": "front"},
            {"source": "frigate", "camera": "side"},
        ]
        motion_detector = MagicMock()
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        end = datetime(2026, 1, 1, 0, 0, 5, tzinfo=timezone.utc)
        calls = []
        old_inc = rmw.inc_counter
        rmw.inc_counter = lambda name, delta=1: calls.append((name, int(delta)))
        try:
            events = get_recording_mqtt_events(
                aggregator,
                motion_detector,
                start_time=start,
                end_time=end,
                merge_window=5,
                yolo_tracks_count=0,
                scope_camera_id="side",
            )
        finally:
            rmw.inc_counter = old_inc
        self.assertEqual(events, [{"source": "frigate", "camera": "side"}])
        self.assertIn(("mqtt_scope_drop_total", 1), calls)

    def test_injects_trigger_fallback_when_frigate_window_empty(self):
        aggregator = MagicMock()
        aggregator.get_events_in_window.return_value = []
        motion_detector = MagicMock()
        motion_detector.get_triggered_camera.return_value = "front"
        motion_detector.get_last_frigate_event.return_value = {
            "source": "frigate",
            "camera": "front",
            "species": "bird",
            "label": "bird",
            "confidence": 0.71,
            "timestamp": "2026-01-01T00:00:01+00:00",
            "_frigate_has_geometry": False,
        }
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        end = datetime(2026, 1, 1, 0, 0, 5, tzinfo=timezone.utc)

        events = get_recording_mqtt_events(
            aggregator,
            motion_detector,
            start_time=start,
            end_time=end,
            merge_window=5,
            yolo_tracks_count=0,
            scope_camera_id="front",
            trigger_source="frigate",
        )

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["source"], "frigate")
        self.assertTrue(events[0].get("_synthetic_trigger_fallback"))

    def test_skips_wrong_camera_last_event_fallback(self):
        """Forest session must not salvage BirdBox global last Frigate event."""
        aggregator = MagicMock()
        aggregator.get_events_in_window.return_value = []
        motion_detector = MagicMock()
        motion_detector.get_last_frigate_event.return_value = {
            "source": "frigate",
            "camera": "BirdBox",
            "species": "bird",
            "label": "bird",
            "confidence": 0.79,
            "timestamp": "2026-01-01T00:00:01+00:00",
        }
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        end = datetime(2026, 1, 1, 0, 0, 5, tzinfo=timezone.utc)

        events = get_recording_mqtt_events(
            aggregator,
            motion_detector,
            start_time=start,
            end_time=end,
            merge_window=5,
            yolo_tracks_count=0,
            scope_camera_id="Forest",
            lookback_camera_id="Forest",
            trigger_source="frigate",
        )

        self.assertEqual(events, [])

    def test_prefers_session_frigate_trigger_snapshot_over_global_last(self):
        aggregator = MagicMock()
        aggregator.get_events_in_window.return_value = []
        motion_detector = MagicMock()
        motion_detector.get_last_frigate_event.return_value = {
            "source": "frigate",
            "camera": "BirdBox",
            "species": "bird",
            "label": "bird",
            "confidence": 0.79,
            "timestamp": "2026-01-01T00:00:01+00:00",
        }
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        end = datetime(2026, 1, 1, 0, 0, 5, tzinfo=timezone.utc)

        events = get_recording_mqtt_events(
            aggregator,
            motion_detector,
            start_time=start,
            end_time=end,
            merge_window=5,
            yolo_tracks_count=0,
            scope_camera_id="Forest",
            lookback_camera_id="Forest",
            trigger_source="frigate",
            frigate_trigger_event={
                "source": "frigate",
                "camera": "Forest",
                "species": "Hooded Crow",
                "label": "bird",
                "sub_label": "Hooded Crow",
                "confidence": 0.66,
                "timestamp": "2026-01-01T00:00:01+00:00",
                "_session_trigger_snapshot": True,
                "_frigate_has_geometry": False,
            },
        )

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["camera"], "Forest")
        self.assertEqual(events[0]["sub_label"], "Hooded Crow")
        self.assertTrue(events[0].get("_session_trigger_snapshot"))

    def test_no_trigger_fallback_for_non_frigate_source(self):
        aggregator = MagicMock()
        aggregator.get_events_in_window.return_value = []
        motion_detector = MagicMock()
        motion_detector.get_triggered_camera.return_value = "front"
        motion_detector.get_last_frigate_event.return_value = {
            "source": "frigate",
            "camera": "front",
            "species": "bird",
            "label": "bird",
            "confidence": 0.71,
            "timestamp": "2026-01-01T00:00:01+00:00",
        }
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        end = datetime(2026, 1, 1, 0, 0, 5, tzinfo=timezone.utc)

        events = get_recording_mqtt_events(
            aggregator,
            motion_detector,
            start_time=start,
            end_time=end,
            merge_window=5,
            yolo_tracks_count=0,
            scope_camera_id="front",
            trigger_source="opencv",
        )
        self.assertEqual(events, [])


if __name__ == "__main__":
    unittest.main()
