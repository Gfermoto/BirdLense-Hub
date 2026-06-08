"""Tests for dual-stream timeline offset."""

from __future__ import annotations

import os
import sys
import unittest

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(current_dir, "../src"))

from dual_stream_timeline import (  # noqa: E402
    apply_record_time_offset,
    resolve_detect_record_time_offset_sec,
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


if __name__ == "__main__":
    unittest.main()
