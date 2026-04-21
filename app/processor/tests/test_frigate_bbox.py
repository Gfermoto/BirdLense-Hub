"""frigate_after_to_normalized_xyxy — bbox для Frigate standalone / кропы."""

import os
import sys
import unittest

current_dir = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.abspath(os.path.join(current_dir, "../src"))
sys.path.insert(0, src_path)

import frigate_bbox as fb  # noqa: E402


class TestFrigateBbox(unittest.TestCase):
    def test_normalized_box_passthrough(self):
        self.assertEqual(
            fb.frigate_after_to_normalized_xyxy({"box": [0.1, 0.2, 0.5, 0.6]}),
            [0.1, 0.2, 0.5, 0.6],
        )

    def test_pixel_box_with_frame_shape(self):
        after = {
            "frame_shape": [480, 640],
            "box": [64.0, 96.0, 192.0, 240.0],
        }
        self.assertEqual(
            fb.frigate_after_to_normalized_xyxy(after),
            [0.1, 0.2, 0.3, 0.5],
        )

    def test_snapshot_box_uses_parent_dimensions(self):
        after = {
            "frame_shape": [480, 640],
            "snapshot": {"box": [0.0, 0.0, 640.0, 480.0]},
        }
        self.assertEqual(
            fb.frigate_after_to_normalized_xyxy(after),
            [0.0, 0.0, 1.0, 1.0],
        )

    def test_region_xywh_when_not_valid_xyxy(self):
        """region как x,y,w,h если не получается прочитать как xyxy."""
        after = {"frame_shape": [480, 640], "region": [100.0, 100.0, 50.0, 60.0]}
        exp = [100 / 640, 100 / 480, 150 / 640, 160 / 480]
        got = fb.frigate_after_to_normalized_xyxy(after)
        self.assertIsNotNone(got)
        for a, b in zip(got, exp):
            self.assertAlmostEqual(a, b, places=5)

    def test_invalid_returns_none(self):
        self.assertIsNone(fb.frigate_after_to_normalized_xyxy(None))
        self.assertIsNone(fb.frigate_after_to_normalized_xyxy({"box": [0, 0, 0, 0]}))
        self.assertIsNone(
            fb.frigate_after_to_normalized_xyxy({"box": [300, 400, 100, 200]})
        )


if __name__ == "__main__":
    unittest.main()
