import os
import sys
import unittest

import numpy as np

current_dir = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.abspath(os.path.join(current_dir, "../src"))
sys.path.insert(0, src_path)

from static_object_filter import StaticObjectFilter, StaticObjectFilterConfig  # noqa: E402


def _bird_box(
    *,
    track_id: int = 1,
    conf: float = 0.3,
    x1: int = 100,
    y1: int = 100,
    x2: int = 360,
    y2: int = 360,
    fw: int = 1280,
    fh: int = 720,
) -> dict:
    area = float((x2 - x1) * (y2 - y1))
    return {
        "track_id": track_id,
        "detector_label": "Bird",
        "conf": conf,
        "crop_coords": (x1, y1, x2, y2),
        "bbox_norm": (x1 / fw, y1 / fh, x2 / fw, y2 / fh),
        "box_area_norm": area / (fw * fh),
    }


class TestStaticObjectFilter(unittest.TestCase):
    def test_rejects_square_low_conf_empty_scene(self):
        filt = StaticObjectFilter(StaticObjectFilterConfig(enabled=True))
        boxes = [_bird_box(conf=0.31)]
        out = filt.filter_boxes(boxes, frame_bgr=np.zeros((720, 1280, 3), dtype=np.uint8), frame_index=1)
        self.assertEqual(len(out), 0)
        self.assertEqual(filt.last_stats["rejected_static_objects"], 1)

    def test_keeps_bird_like_vertical_high_conf(self):
        filt = StaticObjectFilter(StaticObjectFilterConfig(enabled=True))
        boxes = [_bird_box(conf=0.55, x2=200, y2=400)]
        out = filt.filter_boxes(boxes, frame_bgr=np.zeros((720, 1280, 3), dtype=np.uint8), frame_index=1)
        self.assertEqual(len(out), 1)

    def test_keeps_square_conf_041_without_anchor(self):
        filt = StaticObjectFilter(
            StaticObjectFilterConfig(enabled=True, static_square_hard_reject_max_conf=0.38)
        )
        boxes = [_bird_box(conf=0.41)]
        out = filt.filter_boxes(boxes, frame_bgr=np.zeros((720, 1280, 3), dtype=np.uint8), frame_index=1)
        self.assertEqual(len(out), 1)

    def test_keeps_anchor_bird_in_frame_for_square_peer(self):
        filt = StaticObjectFilter(StaticObjectFilterConfig(enabled=True))
        anchor = _bird_box(track_id=1, conf=0.62, x1=400, y1=80, x2=520, y2=420)
        phantom = _bird_box(track_id=2, conf=0.33, x1=900, y1=500, x2=1160, y2=680)
        out = filt.filter_boxes(
            [anchor, phantom],
            frame_bgr=np.zeros((720, 1280, 3), dtype=np.uint8),
            frame_index=1,
        )
        self.assertEqual(len(out), 2)

    def test_rejects_giant_phantom(self):
        filt = StaticObjectFilter(StaticObjectFilterConfig(enabled=True))
        boxes = [_bird_box(conf=0.5, x1=10, y1=10, x2=1200, y2=700)]
        out = filt.filter_boxes(boxes, frame_bgr=np.zeros((720, 1280, 3), dtype=np.uint8), frame_index=1)
        self.assertEqual(len(out), 0)
        self.assertEqual(filt.last_stats["rejected_phantom_boxes"], 1)

    def test_temporal_static_after_n_frames(self):
        cfg = StaticObjectFilterConfig(
            enabled=True,
            static_temporal_min_frames=3,
            static_temporal_max_jitter_px=5.0,
        )
        filt = StaticObjectFilter(cfg)
        frame = np.random.randint(0, 255, (720, 1280, 3), dtype=np.uint8)
        box = _bird_box(track_id=7, conf=0.32)
        for fi in range(1, 5):
            out = filt.filter_boxes([box], frame_bgr=frame, frame_index=fi)
        self.assertEqual(len(out), 0)
        self.assertGreaterEqual(filt.last_stats["rejected_static_objects"], 1)


if __name__ == "__main__":
    unittest.main()
