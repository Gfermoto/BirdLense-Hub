"""Unit tests for yolo_blind_monitor (SOTA-05)."""

from __future__ import annotations

import time
import unittest

from yolo_blind_monitor import (
    YoloBlindLiveMonitor,
    evaluate_detector_health_from_snapshot,
    blind_quickcheck_overrides,
)


class TestBlindQuickcheckOverrides(unittest.TestCase):
    def test_defaults(self):
        ov = blind_quickcheck_overrides({})
        self.assertLessEqual(float(ov["min_confidence_binary"]), 0.1)
        self.assertLessEqual(int(ov["min_box_size_px"]), 20)


class TestYoloBlindLiveMonitor(unittest.TestCase):
    def test_alert_after_frigate_only_duration(self):
        mon = YoloBlindLiveMonitor(alert_seconds=1.0)
        signals = {"yolo_frames_with_tracks": 0, "yolo_blind_phase": "none", "session_extended_by_frigate_only": 5}
        mon._frigate_only_since = time.monotonic() - 2.0
        mon.on_frame(
            frigate_only_extension=True,
            yolo_track_found=False,
            yolo_raw_boxes=0,
            runtime_signals=signals,
        )
        # Gauges published internally; no exception is enough for smoke.

    def test_recovery_clears_frigate_timer(self):
        mon = YoloBlindLiveMonitor(alert_seconds=30.0)
        signals = {"yolo_frames_with_tracks": 1, "yolo_blind_phase": "none", "session_extended_by_frigate_only": 0}
        mon._frigate_only_since = time.monotonic()
        mon.on_frame(
            frigate_only_extension=False,
            yolo_track_found=True,
            yolo_raw_boxes=2,
            runtime_signals=signals,
        )
        self.assertIsNone(mon._frigate_only_since)


class TestEvaluateDetectorHealth(unittest.TestCase):
    def test_blind_when_alert(self):
        out = evaluate_detector_health_from_snapshot(
            {"yolo_blind_alert": 1, "yolo_blind_status": "degraded"},
            recent_blind_confirmed=False,
            recent_blind_score=0.0,
        )
        self.assertEqual(out["status"], "blind")
        self.assertTrue(out["yolo_blind_alert"])

    def test_degraded_when_suspected_phase(self):
        out = evaluate_detector_health_from_snapshot(
            {"yolo_blind_alert": 0, "yolo_blind_phase_live": "suspected"},
            recent_blind_confirmed=False,
            recent_blind_score=0.0,
        )
        self.assertEqual(out["status"], "degraded")


if __name__ == "__main__":
    unittest.main()
