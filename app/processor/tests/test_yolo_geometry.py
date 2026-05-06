"""Letterbox перед YOLO (без некорректного stretch)."""

import os
import sys
import unittest


current_dir = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.abspath(os.path.join(current_dir, "../src"))
sys.path.insert(0, src_path)

import numpy as np

from yolo_geometry import letterbox_bgr_to_wh


class TestLetterboxBGR(unittest.TestCase):
    def test_output_shape_wide_frame(self):
        frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
        out = letterbox_bgr_to_wh(frame, (640, 640))
        self.assertEqual(out.shape, (640, 640, 3))
        self.assertTrue(out.flags["C_CONTIGUOUS"])

    def test_letterbox_differs_from_naive_resize_on_wide(self):
        rng = np.random.default_rng(0)
        frame = rng.integers(0, 256, size=(540, 960, 3), dtype=np.uint8)
        import cv2

        stretched = cv2.resize(frame, (640, 640))
        boxed = letterbox_bgr_to_wh(frame, (640, 640))
        self.assertFalse(np.array_equal(stretched, boxed))
