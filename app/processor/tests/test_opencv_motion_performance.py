"""OpenCV motion CPU-oriented helpers."""

import os
import sys
import unittest

import numpy as np

current_dir = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.abspath(os.path.join(current_dir, "../src"))
sys.path.append(src_path)

from motion_detectors.opencv_motion import OpenCVMotionDetector  # noqa: E402


class TestOpenCVMotionPerformance(unittest.TestCase):
    def test_resize_gray_downscales_large_frame(self):
        det = OpenCVMotionDetector(capture_fn=lambda: None, motion_max_side_px=320)
        gray = np.zeros((1080, 1920), dtype=np.uint8)
        small = det._resize_gray(gray)
        self.assertLessEqual(max(small.shape), 320)

    def test_blur_kernel_smaller_on_downscaled(self):
        k = OpenCVMotionDetector._blur_kernel((480, 640))
        self.assertLessEqual(k[0], 15)
        self.assertGreaterEqual(k[0], 5)


if __name__ == "__main__":
    unittest.main()
