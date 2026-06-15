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
    build_tracker_runtime_cfg,
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
        self.assertLessEqual(doc["track_high_thresh"], 0.12)
        self.assertLessEqual(doc["new_track_thresh"], 0.12)

    def test_clamp_bytetrack_thresholds_auto_unstick_track_conf(self):
        doc = {
            "tracker_type": "bytetrack",
            "track_high_thresh": 0.06,
            "new_track_thresh": 0.06,
            "track_low_thresh": 0.03,
        }
        clamp_bytetrack_track_thresholds(doc, 0.025)
        self.assertLessEqual(doc["track_high_thresh"], 0.01)
        self.assertLessEqual(doc["new_track_thresh"], 0.01)
        self.assertLess(doc["track_high_thresh"], 0.025)

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


    def test_resolve_clamps_with_feeder_far_runtime_overlay(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "bytetrack_lowfps.yaml"
            base.write_text(
                "tracker_type: bytetrack\n"
                "track_high_thresh: 0.06\n"
                "new_track_thresh: 0.06\n"
                "track_low_thresh: 0.03\n"
                "match_thresh: 0.86\n"
                "track_buffer: 12\n",
                encoding="utf-8",
            )

            class _AppCfg:
                def get(self, key, default=None):
                    data = {
                        "processor.min_confidence_binary": 0.06,
                        "processor.min_confidence_binary_bird": 0.05,
                        "processor.openvino_binary_track_ultralytics_conf": 0.06,
                        "processor.inference_backend": "openvino",
                        "processor.tracker_adaptive_low_fps_enabled": True,
                        "processor.tracker_low_fps_threshold": 10.0,
                    }
                    return data.get(key, default)

            profile_overrides = {
                "min_confidence_binary_bird": 0.025,
                "openvino_binary_track_ultralytics_conf": 0.025,
            }
            runtime_cfg = build_tracker_runtime_cfg(_AppCfg(), profile_overrides)
            out = resolve_adaptive_tracker_path(str(base), 7.0, runtime_cfg=runtime_cfg)
            self.assertNotEqual(out, str(base))
            doc = yaml.safe_load(Path(out).read_text(encoding="utf-8"))
            self.assertLess(float(doc["track_high_thresh"]), 0.025)
            self.assertLess(float(doc["new_track_thresh"]), 0.025)


if __name__ == "__main__":
    unittest.main()
