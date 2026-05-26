"""SOTA-10: track stability metrics."""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from track_stability import TrackStabilityMonitor, summarize_tracks_stability
from tracker_low_fps import adaptive_track_buffer_frames


class TestTrackStability(unittest.TestCase):
    def test_adaptive_buffer_scales_with_fps(self):
        low = adaptive_track_buffer_frames(5.0, remember_seconds=8.0, min_buffer=24, max_buffer=120)
        high = adaptive_track_buffer_frames(20.0, remember_seconds=8.0, min_buffer=24, max_buffer=120)
        self.assertEqual(low, 40)
        self.assertEqual(high, 120)

    def test_id_switch_on_iou_mismatch(self):
        mon = TrackStabilityMonitor(iou_threshold=0.25)
        mon.observe_detections(
            [
                SimpleNamespace(track_id=1, bbox=[0.1, 0.1, 0.3, 0.3]),
            ]
        )
        mon.observe_detections(
            [
                SimpleNamespace(track_id=2, bbox=[0.12, 0.12, 0.32, 0.32]),
            ]
        )
        self.assertEqual(mon.track_id_switches_count, 1)

    def test_summarize_tracks_duration(self):
        tracks = {
            1: {
                "frames": [
                    {"t": 0.0, "bbox": [0.1, 0.1, 0.2, 0.2]},
                    {"t": 1.0, "bbox": [0.11, 0.11, 0.21, 0.21]},
                ]
            }
        }
        out = summarize_tracks_stability(tracks, stream_fps=10.0, id_switches_increment=2)
        self.assertEqual(out["track_id_switches_count"], 2)
        self.assertAlmostEqual(out["avg_track_duration_sec"], 1.0, places=3)


if __name__ == "__main__":
    unittest.main()
