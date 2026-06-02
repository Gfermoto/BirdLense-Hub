"""SOTA-10: adaptive ByteTrack YAML for low FPS."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

current_dir = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.abspath(os.path.join(current_dir, "../src"))
sys.path.insert(0, src_path)

from tracker_low_fps import (
    adaptive_match_thresh,
    clamp_bytetrack_track_thresholds,
    resolve_adaptive_tracker_path,
)


class TestTrackerLowFps(unittest.TestCase):
    def test_match_thresh_higher_at_low_fps(self):
        self.assertGreater(adaptive_match_thresh(7.0, 0.82, 10.0), 0.82)
        self.assertEqual(adaptive_match_thresh(15.0, 0.82, 10.0), 0.82)

    def test_clamp_bytetrack_thresholds_below_track_conf(self):
        doc = {
            "tracker_type": "bytetrack",
            "track_high_thresh": 0.18,
            "new_track_thresh": 0.18,
            "track_low_thresh": 0.10,
        }
        clamp_bytetrack_track_thresholds(doc, 0.14)
        self.assertLessEqual(doc["track_high_thresh"], 0.10)
        self.assertLessEqual(doc["new_track_thresh"], 0.10)

    def test_resolve_writes_cached_yaml(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "bytetrack_test.yaml"
            base.write_text(
                "tracker_type: bytetrack\ntrack_buffer: 32\nmatch_thresh: 0.82\n",
                encoding="utf-8",
            )
            cfg = {
                "processor.tracker_adaptive_low_fps_enabled": True,
                "processor.tracker_low_fps_threshold": 10.0,
                "processor.tracker_remember_seconds": 8.0,
                "processor.tracker_adaptive_min_buffer": 24,
                "processor.tracker_adaptive_max_buffer": 120,
            }
            out = resolve_adaptive_tracker_path(str(base), 7.0, runtime_cfg=cfg)
            self.assertNotEqual(out, str(base))
            self.assertTrue(Path(out).is_file())
            text = Path(out).read_text(encoding="utf-8")
            self.assertIn("track_buffer:", text)
            self.assertIn("56", text)


    def test_resolve_clamps_high_fps_tracker_when_track_conf_low(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "bytetrack_highfps.yaml"
            base.write_text(
                "tracker_type: bytetrack\n"
                "track_high_thresh: 0.12\n"
                "new_track_thresh: 0.12\n"
                "track_low_thresh: 0.06\n"
                "match_thresh: 0.86\n"
                "track_buffer: 30\n",
                encoding="utf-8",
            )
            cfg = {
                "processor.tracker_adaptive_low_fps_enabled": True,
                "processor.tracker_low_fps_threshold": 10.0,
                "processor.min_confidence_binary": 0.12,
                "processor.inference_backend": "openvino",
                "processor.openvino_binary_track_ultralytics_conf": 0.12,
            }
            out = resolve_adaptive_tracker_path(str(base), 25.0, runtime_cfg=cfg)
            self.assertNotEqual(out, str(base))
            doc = yaml.safe_load(Path(out).read_text(encoding="utf-8"))
            self.assertLessEqual(float(doc["track_high_thresh"]), 0.10)


if __name__ == "__main__":
    unittest.main()
