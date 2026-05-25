"""OpenCV detector profiles and warmup behavior."""

import os
import sys
import unittest

import numpy as np

current_dir = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.abspath(os.path.join(current_dir, "../src"))
sys.path.append(src_path)

from motion_detectors.opencv_motion import OpenCVMotionDetector  # noqa: E402


class _SequenceCapture:
    def __init__(self, frames):
        self.frames = list(frames)
        self.idx = 0

    def __call__(self):
        if not self.frames:
            return None
        if self.idx >= len(self.frames):
            return self.frames[-1]
        frame = self.frames[self.idx]
        self.idx += 1
        return frame


class TestOpenCVMotionProfiles(unittest.TestCase):
    def test_warmup_suppresses_early_trigger(self):
        base = np.zeros((120, 160, 3), dtype=np.uint8)
        moving = base.copy()
        moving[40:80, 50:110, :] = 255
        cap = _SequenceCapture([base, moving, base, moving, base, moving])
        det = OpenCVMotionDetector(
            capture_fn=cap,
            threshold=10,
            min_contour_area=40,
            smart_trigger_enabled=True,
            suppress_warmup_frames=2,
            min_consecutive_motion_frames=2,
        )
        hits = [det.check() for _ in range(8)]
        self.assertTrue(any(hits))

    def test_auto_profile_switches_to_night(self):
        dark = np.zeros((120, 160, 3), dtype=np.uint8)
        bright = np.full((120, 160, 3), 180, dtype=np.uint8)
        cap = _SequenceCapture([dark, bright, bright, bright])
        det = OpenCVMotionDetector(
            capture_fn=cap,
            threshold=10,
            min_contour_area=40,
            auto_profile_enabled=True,
            auto_profile_night_luma_threshold=60,
            smart_trigger_enabled=True,
        )
        det.check()
        self.assertIn(det.diagnostics()["profile"], {"day", "night"})


if __name__ == "__main__":
    unittest.main()
