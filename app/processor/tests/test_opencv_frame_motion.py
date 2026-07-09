"""Tests for OpenCV smart motion trigger analysis."""

import os
import sys
import unittest

import numpy as np

current_dir = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.abspath(os.path.join(current_dir, "../src"))
sys.path.append(src_path)

from motion_detectors.opencv_frame_motion import (  # noqa: E402
    OpenCVMotionAnalysis,
    analyze_frame_pair,
    decide_trigger_recording,
    should_trigger_recording,
)


class TestOpenCVFrameMotion(unittest.TestCase):
    def test_static_frame_no_contour_motion(self):
        gray = np.zeros((120, 160), dtype=np.uint8)
        analysis = analyze_frame_pair(
            gray, gray, diff_threshold=20, min_contour_area=200
        )
        self.assertFalse(analysis.has_contour_motion)
        self.assertFalse(
            should_trigger_recording(analysis, frame_area=gray.size, global_motion_mean_absdiff=2.5)
        )

    def test_localized_bird_like_motion_triggers(self):
        prev = np.full((200, 300), 40, dtype=np.uint8)
        curr = prev.copy()
        curr[80:120, 120:180] = 200
        analysis = analyze_frame_pair(
            prev, curr, diff_threshold=18, min_contour_area=120
        )
        self.assertTrue(analysis.has_contour_motion)
        self.assertTrue(
            should_trigger_recording(
                analysis,
                frame_area=prev.size,
                global_motion_mean_absdiff=2.5,
                min_motion_pixel_fraction=0.0005,
            )
        )
        self.assertGreater(len(analysis.motion_contour_polygons), 0)

    def test_compression_noise_suppressed(self):
        prev = np.random.randint(0, 255, (480, 704), dtype=np.uint8)
        curr = prev.copy()
        curr[0, 0] = (int(curr[0, 0]) + 3) % 255
        analysis = analyze_frame_pair(
            prev, curr, diff_threshold=18, min_contour_area=280
        )
        if not analysis.has_contour_motion:
            return
        self.assertFalse(
            should_trigger_recording(
                analysis,
                frame_area=prev.size,
                global_motion_mean_absdiff=2.5,
                min_motion_pixel_fraction=0.001,
            )
        )

    def test_giant_static_blob_suppressed(self):
        frame_area = 576 * 704
        analysis = OpenCVMotionAnalysis(
            global_mean_absdiff=1.2,
            motion_pixel_fraction=0.0002,
            max_contour_area=0.42 * frame_area,
            has_contour_motion=True,
        )
        self.assertFalse(
            should_trigger_recording(
                analysis,
                frame_area=frame_area,
                global_motion_mean_absdiff=2.5,
                max_contour_area_frac=0.35,
            )
        )

    def test_decision_contains_reject_reason(self):
        analysis = OpenCVMotionAnalysis(
            global_mean_absdiff=0.5,
            motion_pixel_fraction=0.0001,
            max_contour_area=0.0,
            has_contour_motion=False,
        )
        decision = decide_trigger_recording(
            analysis,
            frame_area=1000,
            profile="night",
        )
        self.assertFalse(decision.triggered)
        self.assertEqual(decision.reason, "no_contour_motion")
        self.assertEqual(decision.profile, "night")


if __name__ == "__main__":
    unittest.main()
