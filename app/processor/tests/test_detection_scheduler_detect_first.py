"""Detect-first scheduler helpers (#612)."""

from __future__ import annotations

import os
import sys
import unittest

current_dir = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.abspath(os.path.join(current_dir, "../src"))
sys.path.insert(0, src_path)

from detection_scheduler import (  # noqa: E402
    DetectFirstConfig,
    frame_counts_as_detect_first_hit,
    resolve_detect_first_min_track_seconds,
)


class TestDetectFirstSchedulerHelpers(unittest.TestCase):
    def test_min_track_uses_detect_first_not_session_duration(self):
        cfg = DetectFirstConfig(
            enabled=True,
            triggers=("opencv",),
            window_seconds=4.0,
            max_frames=15,
            confirm_min_hits=1,
            confirm_min_track_seconds=0.35,
        )
        cam = {"min_track_duration": 0.8}
        self.assertEqual(resolve_detect_first_min_track_seconds(cfg, cam), 0.35)

    def test_camera_detect_first_override_wins(self):
        cfg = DetectFirstConfig(
            enabled=True,
            triggers=("opencv",),
            window_seconds=4.0,
            max_frames=15,
            confirm_min_hits=1,
            confirm_min_track_seconds=0.35,
        )
        cam = {
            "min_track_duration": 0.8,
            "detect_first_confirm_min_track_seconds": 0.25,
        }
        self.assertEqual(resolve_detect_first_min_track_seconds(cfg, cam), 0.25)

    def test_per_camera_confirm_min_hits_override(self):
        from detection_scheduler import resolve_detect_first_confirm_min_hits

        cfg = DetectFirstConfig(
            enabled=True,
            triggers=("opencv",),
            window_seconds=4.0,
            max_frames=30,
            confirm_min_hits=2,
            confirm_min_track_seconds=0.35,
        )
        cam = {"detect_first_confirm_min_hits": 1}
        self.assertEqual(resolve_detect_first_confirm_min_hits(cfg, cam), 1)
        self.assertEqual(resolve_detect_first_confirm_min_hits(cfg, {}), 2)

    def test_raw_boxes_alone_do_not_count_as_hit(self):
        self.assertFalse(
            frame_counts_as_detect_first_hit(
                {"yolo_raw_boxes": 2, "yolo_track_found": False, "result_count": 0},
            ),
        )
        self.assertFalse(frame_counts_as_detect_first_hit({"yolo_raw_boxes": 0}))

    def test_track_or_accepted_count_as_hit(self):
        self.assertTrue(
            frame_counts_as_detect_first_hit(
                {"yolo_raw_boxes": 0, "yolo_track_found": True, "result_count": 0},
            ),
        )
        self.assertTrue(
            frame_counts_as_detect_first_hit(
                {"yolo_raw_boxes": 0, "yolo_track_found": False, "result_count": 1},
            ),
        )


if __name__ == "__main__":
    unittest.main()
