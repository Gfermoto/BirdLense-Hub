"""Tests for Frigate live bbox store."""

import os
import sys
import time
import unittest

current_dir = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.abspath(os.path.join(current_dir, "../src"))
sys.path.append(src_path)

import frigate_live_track as flt  # noqa: E402


class TestFrigateLiveTrack(unittest.TestCase):
    def setUp(self):
        flt.clear_frigate_live_track("Forest")

    def test_update_and_get_bird_bbox(self):
        flt.update_frigate_live_track(
            "Forest",
            bbox_norm=[0.1, 0.2, 0.4, 0.5],
            score=0.88,
            event_id="abc",
            event_type="update",
            labels={"bird"},
        )
        bbox = flt.get_frigate_live_bbox("Forest", max_age_sec=5.0)
        self.assertEqual(bbox, [0.1, 0.2, 0.4, 0.5])

    def test_end_clears_matching_event(self):
        flt.update_frigate_live_track(
            "Forest",
            bbox_norm=[0.1, 0.2, 0.4, 0.5],
            event_id="ev1",
            event_type="new",
            labels={"bird"},
        )
        flt.update_frigate_live_track(
            "Forest",
            bbox_norm=[0.1, 0.2, 0.4, 0.5],
            event_id="ev1",
            event_type="end",
            labels={"bird"},
        )
        self.assertIsNone(flt.get_frigate_live_bbox("Forest", max_age_sec=5.0))

    def test_non_bird_ignored(self):
        flt.update_frigate_live_track(
            "Forest",
            bbox_norm=[0.1, 0.2, 0.4, 0.5],
            event_type="update",
            labels={"cat"},
        )
        self.assertIsNone(flt.get_frigate_live_bbox("Forest", max_age_sec=5.0))

    def test_stale_bbox_expires(self):
        flt.update_frigate_live_track(
            "Forest",
            bbox_norm=[0.1, 0.2, 0.4, 0.5],
            event_type="update",
            labels={"bird"},
        )
        snap = flt.snapshot_frigate_live_tracks()
        snap["Forest"]["updated_at"] = time.time() - 10.0
        with flt._lock:
            flt._by_camera["Forest"] = snap["Forest"]
        self.assertIsNone(flt.get_frigate_live_bbox("Forest", max_age_sec=2.0))


if __name__ == "__main__":
    unittest.main()
