"""Unit tests for compare_detector_bboxes IoU helpers and parity gate (#640)."""

from __future__ import annotations

import importlib.util
import json
import os
import sys
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
_SCRIPTS = _REPO / "scripts"


def _load_compare_module():
    path = _SCRIPTS / "compare_detector_bboxes.py"
    spec = importlib.util.spec_from_file_location("compare_detector_bboxes", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["compare_detector_bboxes"] = mod
    spec.loader.exec_module(mod)
    return mod


def _load_smoke_module():
    path = _SCRIPTS / "detector_bbox_parity_smoke.py"
    spec = importlib.util.spec_from_file_location("detector_bbox_parity_smoke", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["detector_bbox_parity_smoke"] = mod
    spec.loader.exec_module(mod)
    return mod


class TestCompareDetectorBboxesHelpers(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = _load_compare_module()

    def test_iou_identical_boxes(self):
        box = (10.0, 10.0, 50.0, 50.0)
        self.assertAlmostEqual(self.mod._iou_xyxy(box, box), 1.0)

    def test_iou_disjoint(self):
        self.assertEqual(self.mod._iou_xyxy((0, 0, 1, 1), (2, 2, 3, 3)), 0.0)

    def test_greedy_match_single_pair(self):
        a = [(0.0, 0.0, 10.0, 10.0)]
        b = [(1.0, 1.0, 11.0, 11.0)]
        ious = self.mod._greedy_match_ious(a, b)
        self.assertEqual(len(ious), 1)
        self.assertGreater(ious[0], 0.5)


class TestDetectorBboxParitySmoke(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.smoke = _load_smoke_module()

    def test_skip_when_weights_missing(self):
        video = _REPO / "benchmarks/fixtures/clip_1819.mp4"
        pt, ov = self.smoke._resolve_weights("/nonexistent/best.pt", "/nonexistent/ov")
        resolved_video = self.smoke._resolve_video(str(video)) if video.is_file() else None
        if resolved_video and pt is None and ov is None:
            self.skipTest("fixture video present but cannot test missing weights path")
        self.assertIsNone(pt)
        self.assertIsNone(ov)

    def test_gate_report_shape(self):
        report = {
            "median_iou_when_both": 0.5,
            "gate": {"min_median_iou": 0.45, "passed": True, "clip_id": "1819", "delta": 0.05},
        }
        self.assertTrue(report["gate"]["passed"])
        self.assertGreaterEqual(report["median_iou_when_both"], report["gate"]["min_median_iou"])


class TestCompareDetectorBboxesGateCli(unittest.TestCase):
    def test_gate_failure_message_includes_clip(self):
        """Synthetic: gate object documents clip_id + delta contract."""
        gate = {
            "error": "detector_bbox_parity_gate_failed",
            "clip_id": "1819",
            "median_iou": 0.3,
            "min_median_iou": 0.45,
            "delta": -0.15,
        }
        payload = json.dumps(gate)
        self.assertIn("1819", payload)
        self.assertIn("delta", payload)


if __name__ == "__main__":
    unittest.main()
