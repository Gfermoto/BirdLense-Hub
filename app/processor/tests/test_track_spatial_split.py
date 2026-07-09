"""Track split when ByteTrack merges distant spatial zones."""

from __future__ import annotations

import os
import sys
import unittest

current_dir = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.abspath(os.path.join(current_dir, "../src"))
sys.path.insert(0, src_path)

from track_spatial_split import split_track_by_spatial_jumps, split_tracks_by_spatial_jumps  # noqa: E402


def _merged_track() -> dict:
    """Incident 3149 pattern: left perch then feeder-right (~0.41 vs ~0.66 x)."""
    return {
        "start_time": 4.5,
        "end_time": 11.2,
        "detector_events": [
            {"label": "Bird", "confidence": 0.42, "t": 4.5},
            {"label": "Bird", "confidence": 0.38, "t": 10.6},
        ],
        "classifier_events": [],
        "key_frames": [
            {"t": 4.5, "bbox": [0.39, 0.67, 0.48, 0.82], "score": 8.0, "crop": "left"},
            {"t": 10.6, "bbox": [0.66, 0.42, 0.75, 0.54], "score": 9.0, "crop": "right"},
        ],
        "best_frame": "left",
        "best_frame_score": 8.0,
        "frames": [
            {"t": 4.5, "bbox": [0.39, 0.67, 0.48, 0.82]},
            {"t": 7.0, "bbox": [0.41, 0.68, 0.49, 0.81]},
            {"t": 10.6, "bbox": [0.66, 0.42, 0.75, 0.54]},
            {"t": 11.2, "bbox": [0.67, 0.43, 0.76, 0.55]},
        ],
    }


class TestTrackSpatialSplit(unittest.TestCase):
    def test_splits_merged_zones_into_two_tracks(self):
        out = split_track_by_spatial_jumps(
            1,
            _merged_track(),
            max_center_jump_norm=0.18,
            min_segment_frames=2,
        )
        self.assertEqual(len(out), 2)
        self.assertIn(1, out)
        self.assertIn("1:s1", out)
        left = out[1]["frames"]
        right = out["1:s1"]["frames"]
        self.assertEqual(len(left), 2)
        self.assertEqual(len(right), 2)
        self.assertLess(float(left[0]["bbox"][0]), 0.5)
        self.assertGreater(float(right[0]["bbox"][0]), 0.6)

    def test_best_frame_follows_segment_key_frames(self):
        out = split_track_by_spatial_jumps(
            6,
            _merged_track(),
            max_center_jump_norm=0.18,
            min_segment_frames=2,
        )
        self.assertEqual(out[6]["best_frame"], "left")
        self.assertEqual(out["6:s1"]["best_frame"], "right")

    def test_no_split_when_motion_continuous(self):
        track = {
            "frames": [
                {"t": 0.0, "bbox": [0.40, 0.50, 0.50, 0.60]},
                {"t": 0.5, "bbox": [0.42, 0.51, 0.52, 0.61]},
                {"t": 1.0, "bbox": [0.44, 0.52, 0.54, 0.62]},
            ],
            "detector_events": [],
            "key_frames": [],
        }
        out = split_track_by_spatial_jumps(
            3,
            track,
            max_center_jump_norm=0.18,
            min_segment_frames=2,
        )
        self.assertEqual(out, {3: track})

    def test_disabled_via_config(self):
        cfg = {"processor.track_spatial_split_enabled": False}

        class _Cfg:
            config = cfg

            def get(self, key, default=None):
                return cfg.get(key, default)

        tracks = {1: _merged_track()}
        out = split_tracks_by_spatial_jumps(tracks, _Cfg())
        self.assertEqual(out, tracks)

    def test_default_on_without_explicit_config(self):
        class _Cfg:
            config = {}

            def get(self, key, default=None):
                return default

        tracks = {1: _merged_track()}
        out = split_tracks_by_spatial_jumps(tracks, _Cfg())
        self.assertEqual(len(out), 2)


if __name__ == "__main__":
    unittest.main()
