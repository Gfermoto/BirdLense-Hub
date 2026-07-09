"""Tests for dense_track_persist (#613)."""

from __future__ import annotations

import os
import sys
import unittest

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(current_dir, "../src"))

from dense_track_persist import restore_dense_persist_frames  # noqa: E402


def _frames(n: int) -> list[dict]:
    return [{"t": float(i), "bbox": [0.40, 0.30, 0.48, 0.38]} for i in range(n)]


class TestDenseTrackPersist(unittest.TestCase):
    def test_restores_when_runtime_track_is_denser(self):
        tracks = {
            7: {
                "start_time": 0.0,
                "end_time": 5.0,
                "frames": _frames(12),
                "detector_events": [{"label": "Bird", "confidence": 0.5, "t": 0.0}],
            }
        }
        rows = [
            {
                "source": "video",
                "detection_provider": "yolo",
                "track_id": 7,
                "frames": _frames(2),
            }
        ]
        out, restored = restore_dense_persist_frames(rows, tracks, min_runtime_frames=4, min_persist_frames=3)
        self.assertEqual(restored, 1)
        self.assertEqual(len(out[0]["frames"]), 12)
        self.assertTrue(out[0].get("dense_track_restored"))

    def test_skips_when_persist_already_dense(self):
        tracks = {1: {"frames": _frames(5)}}
        rows = [{"source": "video", "detection_provider": "yolo", "track_id": 1, "frames": _frames(5)}]
        out, restored = restore_dense_persist_frames(rows, tracks)
        self.assertEqual(restored, 0)
        self.assertEqual(len(out[0]["frames"]), 5)


if __name__ == "__main__":
    unittest.main()
