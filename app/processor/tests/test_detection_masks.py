import os
import sys
import unittest

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(current_dir, "../src"))

from detection_masks import DetectionMaskConfig, DetectionMaskFilter  # noqa: E402


class TestDetectionMasks(unittest.TestCase):
    def test_ignore_mask_rejects_center(self):
        cfg = DetectionMaskConfig(
            ignore_masks=[[[0.0, 0.0], [0.5, 0.0], [0.5, 0.5], [0.0, 0.5]]],
            interest_zones=[],
            interest_zones_required=False,
        )
        filt = DetectionMaskFilter(cfg)
        box = {
            "crop_coords": (200, 150, 300, 250),
            "detector_label": "Bird",
        }
        reason = filt.reject_reason(box, frame_shape=(720, 1280, 3))
        self.assertIsNotNone(reason)
        self.assertIn("ignore_mask", reason or "")

    def test_interest_zone_required(self):
        cfg = DetectionMaskConfig(
            ignore_masks=[],
            interest_zones=[[[0.6, 0.0], [1.0, 0.0], [1.0, 1.0], [0.6, 1.0]]],
            interest_zones_required=True,
        )
        filt = DetectionMaskFilter(cfg)
        box = {"crop_coords": (100, 100, 200, 200), "detector_label": "Bird"}
        self.assertIsNotNone(filt.reject_reason(box, frame_shape=(720, 1280, 3)))


if __name__ == "__main__":
    unittest.main()
