"""Tests for bbox geometry IoU gate."""

from __future__ import annotations

import unittest

import numpy as np

from bbox_iou_gate import apply_bbox_geometry_iou_gate


class TestBboxIouGate(unittest.TestCase):
    def test_passes_valid_box(self):
        boxes = np.array([[100.0, 100.0, 200.0, 200.0]], dtype=np.float64)
        cfg = {"detection.bbox_iou_gate_enabled": True, "detection.bbox_iou_gate_min": 0.85}
        out, stats, idx = apply_bbox_geometry_iou_gate(
            boxes,
            detector_shape_hw=(576, 704),
            overlay_shape_hw=(576, 704),
            runtime_cfg=cfg,
        )
        self.assertEqual(len(out), 1)
        self.assertEqual(stats["passed"], 1)

    def test_disabled_passthrough(self):
        boxes = np.array([[1.0, 1.0, 2.0, 2.0]], dtype=np.float64)
        out, stats, idx = apply_bbox_geometry_iou_gate(
            boxes,
            detector_shape_hw=(640, 640),
            overlay_shape_hw=(720, 1280),
            runtime_cfg={"detection.bbox_iou_gate_enabled": False},
        )
        self.assertEqual(len(out), 1)
        self.assertEqual(len(idx), 1)


if __name__ == "__main__":
    unittest.main()
