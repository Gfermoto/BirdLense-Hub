import os
import sys
import unittest

import numpy as np

current_dir = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.abspath(os.path.join(current_dir, "../src"))
project_root = os.path.abspath(os.path.join(current_dir, "../../.."))
sys.path.append(src_path)
sys.path.append(os.path.join(project_root, "app"))

from app_config.app_config import app_config
from frame_processor import FrameProcessor


class _Res:
    def __init__(self, bbox, track_id: int = 1):
        self.bbox = bbox
        self.track_id = track_id
        self.class_name = "sparrow"
        self.detector_label = "Bird"
        self.detector_confidence = 0.9
        self.classifier_confidence = 0.8
        self.crop = np.zeros((16, 16, 3), dtype=np.uint8)
        self.blur_variance = 12.0
        self.confidence = 0.8


class _Strategy:
    def __init__(self):
        self.calls = 0
        self.last_detect_metrics = {}

    def detect(
        self,
        frame,
        tracker_config,
        *,
        min_confidence,
        profile_overrides=None,
        classification_frame=None,
    ):
        self.calls += 1
        if self.calls == 1:
            self.last_detect_metrics = {
                "raw_boxes": 1,
                "boxes_with_track_id": 1,
                "accepted": 1,
            }
            return [_Res([0.1, 0.2, 0.3, 0.4], track_id=7)]
        self.last_detect_metrics = {
            "raw_boxes": 0,
            "boxes_with_track_id": 0,
            "accepted": 0,
        }
        return []

    def reset(self):
        return None


class TestFrameProcessorLiveOverlay(unittest.TestCase):
    def test_live_overlay_keeps_recent_track_then_expires(self):
        prev_ttl = app_config.get("ui.live_overlay_track_ttl_seconds")
        app_config.set("ui.live_overlay_track_ttl_seconds", 0.6)
        try:
            fp = FrameProcessor(_Strategy())
            frame = np.zeros((64, 64, 3), dtype=np.uint8)

            fp.run(frame, frame_time=1.0)
            self.assertEqual(len(fp.live_detector_polygons), 1)

            fp.run(frame, frame_time=1.2)
            self.assertEqual(len(fp.live_detector_polygons), 1)

            fp.run(frame, frame_time=2.0)
            self.assertEqual(fp.live_detector_polygons, [])
        finally:
            app_config.set("ui.live_overlay_track_ttl_seconds", prev_ttl)


if __name__ == "__main__":
    unittest.main()
