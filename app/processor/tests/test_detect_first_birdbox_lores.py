"""Detect-first BirdBox lores geometry + hit counting (incident a656199a)."""

from __future__ import annotations

import os
import sys
import unittest

current_dir = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.abspath(os.path.join(current_dir, "../src"))
sys.path.insert(0, src_path)

import numpy as np

from detection_scheduler import frame_counts_as_detect_first_hit  # noqa: E402
from frame_geometry import resolve_binary_track_imgsz  # noqa: E402


class TestDetectFirstBirdBoxLores(unittest.TestCase):
    def test_openvino_native_lores_imgsz_for_576x704_without_square_ir(self):
        frame = np.zeros((576, 704, 3), dtype=np.uint8)
        cfg = {
            "processor.inference_lores_wh": [704, 576],
            "processor.binary_imgsz": 704,
            "processor.inference_backend": "openvino",
            "processor.openvino_native_lores_imgsz": True,
        }
        self.assertEqual(resolve_binary_track_imgsz(frame, cfg, inference_backend="openvino"), [576, 704])

    def test_openvino_square_when_native_lores_disabled(self):
        frame = np.zeros((576, 704, 3), dtype=np.uint8)
        cfg = {
            "processor.inference_lores_wh": [704, 576],
            "processor.binary_imgsz": 704,
            "processor.openvino_native_lores_imgsz": False,
        }
        self.assertEqual(resolve_binary_track_imgsz(frame, cfg, inference_backend="openvino"), 704)

    def test_raw_yolo_boxes_count_as_detect_first_hit(self):
        self.assertTrue(
            frame_counts_as_detect_first_hit(
                {"yolo_raw_boxes": 2, "yolo_track_found": False, "result_count": 0},
            ),
        )
        self.assertFalse(frame_counts_as_detect_first_hit({"yolo_raw_boxes": 0}))


if __name__ == "__main__":
    unittest.main()
