"""Detect-first BirdBox lores geometry + hit counting (incident a656199a)."""

from __future__ import annotations

import os
import sys
import unittest

current_dir = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.abspath(os.path.join(current_dir, "../src"))
app_path = os.path.abspath(os.path.join(current_dir, "..", ".."))
for _p in (app_path, src_path):
    sys.path.insert(0, _p)

import numpy as np

from detection_scheduler import frame_counts_as_detect_first_hit  # noqa: E402
from frame_geometry import resolve_binary_track_imgsz  # noqa: E402


class TestDetectFirstBirdBoxLores(unittest.TestCase):
    def test_native_lores_imgsz_for_576x704(self):
        frame = np.zeros((576, 704, 3), dtype=np.uint8)
        cfg = {
            "processor.inference_lores_wh": [704, 576],
            "processor.binary_imgsz": 704,
            "processor.inference_backend": "onnxruntime",
        }
        self.assertEqual(resolve_binary_track_imgsz(frame, cfg, inference_backend="onnxruntime"), [576, 704])

    def test_square_imgsz_when_lores_mismatch(self):
        frame = np.zeros((576, 704, 3), dtype=np.uint8)
        cfg = {
            "processor.binary_imgsz": 704,
        }
        self.assertEqual(resolve_binary_track_imgsz(frame, cfg, inference_backend="torch"), 704)

    def test_raw_yolo_boxes_count_as_detect_first_hit(self):
        self.assertTrue(
            frame_counts_as_detect_first_hit(
                {"yolo_raw_boxes": 2, "yolo_track_found": False, "result_count": 0},
            ),
        )
        self.assertFalse(frame_counts_as_detect_first_hit({"yolo_raw_boxes": 0}))


if __name__ == "__main__":
    unittest.main()
