"""ROI SR must not crash classification when build_roi_super_resolution returns None."""

from __future__ import annotations

import unittest

import numpy as np

pytest = __import__("pytest")
cv2 = pytest.importorskip("cv2")

from detection_strategy import TwoStageStrategy  # noqa: E402


class TestRoiSrClassificationNullSafe(unittest.TestCase):
    def test_apply_roi_sr_to_crop_when_roi_sr_is_none(self):
        strategy = TwoStageStrategy.__new__(TwoStageStrategy)
        strategy._roi_sr = None
        crop = np.zeros((20, 20, 3), dtype=np.uint8)
        out, applied, latency = strategy._apply_roi_sr_to_crop(crop, min_box_size_px=32)
        self.assertIs(out, crop)
        self.assertEqual(applied, 0)
        self.assertEqual(latency, 0.0)

    def test_build_roi_super_resolution_none_assignable_on_strategy(self):
        from roi_super_resolution import build_roi_super_resolution

        strategy = TwoStageStrategy.__new__(TwoStageStrategy)
        strategy._roi_sr = build_roi_super_resolution({"experimental.sr_enabled": False})
        self.assertIsNone(strategy._roi_sr)
        crop = np.zeros((20, 20, 3), dtype=np.uint8)
        out, applied, _ = strategy._apply_roi_sr_to_crop(crop, min_box_size_px=32)
        self.assertIs(out, crop)
        self.assertEqual(applied, 0)


if __name__ == "__main__":
    unittest.main()
