"""Tests for dual-stream timeline offset."""

from __future__ import annotations

import os
import sys
import unittest

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(current_dir, "../src"))

from dual_stream_timeline import (  # noqa: E402
    apply_playback_timeline_offset_to_detections,
    apply_record_time_offset,
    resolve_detect_record_time_offset_sec,
    shift_detection_timeline_for_playback,
)


class TestDualStreamTimeline(unittest.TestCase):
    def test_global_offset(self):
        cfg = {"processor.detect_record_time_offset_sec": 0.25}
        self.assertAlmostEqual(resolve_detect_record_time_offset_sec(cfg), 0.25)

    def test_camera_role_offset(self):
        cfg = {
            "processor.detect_record_time_offset_sec": 0.0,
            "video.cameras": [{"id": "BirdBox", "tuning_role": "feeder_close"}],
            "processor.camera_tuning_by_role": {
                "feeder_close": {"detect_record_time_offset_sec": -0.15},
            },
        }
        self.assertAlmostEqual(
            resolve_detect_record_time_offset_sec(cfg, camera_id="BirdBox"),
            -0.15,
        )

    def test_apply_offset_clamps_zero(self):
        self.assertAlmostEqual(apply_record_time_offset(0.05, -0.2), 0.0)

    def test_camera_override_offset_wins(self):
        cfg = {
            "processor.detect_record_time_offset_sec": 0.0,
            "video.cameras": [{"id": "Forest", "tuning_role": "feeder_far"}],
            "processor": {
                "camera_tuning_by_role": {
                    "feeder_far": {"detect_record_time_offset_sec": 0.0},
                },
                "camera_overrides": {
                    "Forest": {"detect_record_time_offset_sec": -0.12},
                },
            },
        }
        self.assertAlmostEqual(
            resolve_detect_record_time_offset_sec(cfg, camera_id="Forest"),
            -0.12,
        )

    def test_shift_detection_timeline(self):
        det = {
            "start_time": 1.0,
            "end_time": 3.0,
            "frames": [{"t": 1.5, "bbox": [0.1, 0.2, 0.3, 0.4]}],
        }
        out = shift_detection_timeline_for_playback(det, -0.2)
        self.assertAlmostEqual(out["start_time"], 0.8)
        self.assertAlmostEqual(out["frames"][0]["t"], 1.3)
        self.assertTrue(out.get("playback_timeline_synced"))


if __name__ == "__main__":
    unittest.main()
