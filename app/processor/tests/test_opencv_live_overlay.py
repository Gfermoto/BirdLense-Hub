"""Tests for in-memory OpenCV live overlay snapshot."""

import os
import sys
import unittest

current_dir = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.abspath(os.path.join(current_dir, "../src"))
sys.path.append(src_path)

from motion_detectors.opencv_live_overlay import (  # noqa: E402
    refresh_all_opencv_live_detectors,
    register_opencv_live_detector,
    set_opencv_live_overlay,
    set_yolo_live_overlay,
    snapshot_opencv_live_by_camera,
    tracks_to_detector_polygons,
)


class TestOpenCVLiveOverlay(unittest.TestCase):
    def test_snapshot_per_camera(self):
        set_opencv_live_overlay(
            "BirdBox",
            {"trigger_polygons": [[[0.1, 0.2], [0.3, 0.2], [0.3, 0.4], [0.1, 0.4]]]},
        )
        snap = snapshot_opencv_live_by_camera()
        self.assertIn("BirdBox", snap)
        self.assertEqual(len(snap["BirdBox"]["trigger_polygons"]), 1)

    def test_merge_opencv_and_yolo(self):
        set_opencv_live_overlay("Forest", {"trigger_polygons": []})
        set_yolo_live_overlay(
            "Forest",
            {"detector_polygons": [[[0.0, 0.0], [0.1, 0.0], [0.1, 0.1], [0.0, 0.1]]]},
        )
        snap = snapshot_opencv_live_by_camera()
        self.assertEqual(len(snap["Forest"]["detector_polygons"]), 1)

    def test_refresh_registered_detector(self):
        class _Stub:
            def refresh_live_overlay(self):
                set_opencv_live_overlay(
                    "BirdBox",
                    {
                        "trigger_polygons": [[[0.2, 0.2], [0.4, 0.2], [0.4, 0.5], [0.2, 0.5]]],
                        "last_decision_reason": "stub",
                    },
                )

        register_opencv_live_detector("BirdBox", _Stub())
        refresh_all_opencv_live_detectors()
        snap = snapshot_opencv_live_by_camera()
        self.assertEqual(snap["BirdBox"]["last_decision_reason"], "stub")

    def test_tracks_to_polygons(self):
        tracks = {
            "1": {"frames": [{"bbox": [0.1, 0.2, 0.3, 0.4]}]},
        }
        polys = tracks_to_detector_polygons(tracks)
        self.assertEqual(len(polys), 1)
        self.assertEqual(len(polys[0]), 4)


if __name__ == "__main__":
    unittest.main()
