"""Frigate-style motion mask parsing and application."""

import os
import sys
import unittest

import numpy as np

current_dir = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.abspath(os.path.join(current_dir, "../src"))
sys.path.append(src_path)

from motion_detectors.opencv_motion_mask import (  # noqa: E402
    apply_exclusion_mask,
    build_exclusion_mask,
    parse_normalized_polygon,
)


class TestOpenCVMotionMask(unittest.TestCase):
    def test_parse_polygon(self):
        poly = parse_normalized_polygon("0.0,0.0,1.0,0.0,1.0,0.2,0.0,0.2")
        self.assertIsNotNone(poly)
        self.assertEqual(poly.shape, (4, 2))

    def test_exclusion_zeros_motion_inside_mask(self):
        mask = build_exclusion_mask((100, 200), ["0.0,0.0,0.5,0.0,0.5,1.0,0.0,1.0"])
        self.assertIsNotNone(mask)
        binary = np.zeros((100, 200), dtype=np.uint8)
        binary[:, 80:120] = 255
        out = apply_exclusion_mask(binary, mask)
        self.assertEqual(int(np.count_nonzero(out[:, :100])), 0)
        self.assertGreater(int(np.count_nonzero(out[:, 100:])), 0)


if __name__ == "__main__":
    unittest.main()
