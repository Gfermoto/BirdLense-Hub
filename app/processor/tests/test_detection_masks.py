import os
import sys
import unittest

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(current_dir, "../src"))

import numpy as np

from detection_masks import DetectionMaskConfig, DetectionMaskFilter  # noqa: E402
from detection_quality import DetectionQualityConfig, DetectionQualityPipeline  # noqa: E402
from scene_adaptive import SceneAdaptiveConfig  # noqa: E402
from static_object_filter import StaticObjectFilterConfig  # noqa: E402


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

    def test_global_static_trusts_bird_floor(self):
        cfg = DetectionQualityConfig(
            motion_verified_enabled=True,
            motion_global_static_reject=True,
            motion_global_max_mean_absdiff=2.0,
            motion_hard_conf_ceiling=0.55,
            bird_base_min_confidence=0.32,
            scene=SceneAdaptiveConfig(
                bg_enabled=False,
                adaptive_conf_enabled=False,
            ),
            static=StaticObjectFilterConfig(enabled=False),
        )
        pipe = DetectionQualityPipeline(cfg)
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        box = {
            "detector_label": "Bird",
            "conf": 0.363,
            "crop_coords": (100, 100, 200, 200),
            "track_id": 1,
        }
        pipe.filter_boxes([box], frame_bgr=frame, frame_index=1, bird_trust_floor=0.32)
        kept = pipe.filter_boxes([box], frame_bgr=frame, frame_index=2, bird_trust_floor=0.32)
        self.assertEqual(len(kept), 1)


if __name__ == "__main__":
    unittest.main()
