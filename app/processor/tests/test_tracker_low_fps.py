"""SOTA-10: adaptive ByteTrack YAML for low FPS."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tracker_low_fps import adaptive_match_thresh, resolve_adaptive_tracker_path


class TestTrackerLowFps(unittest.TestCase):
    def test_match_thresh_lower_at_low_fps(self):
        self.assertLess(adaptive_match_thresh(7.0, 0.82, 10.0), 0.82)
        self.assertEqual(adaptive_match_thresh(15.0, 0.82, 10.0), 0.82)

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


if __name__ == "__main__":
    unittest.main()
