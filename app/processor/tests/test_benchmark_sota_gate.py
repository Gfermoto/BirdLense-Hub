"""Unit tests for SOTA-09 benchmark gate logic (no YOLO)."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "scripts"))

from benchmark_sota import evaluate_clip, load_json  # noqa: E402


class TestBenchmarkSotaGate(unittest.TestCase):
    def setUp(self):
        self.baseline = load_json(REPO / "benchmarks" / "golden_baseline.json")
        self.thresholds = self.baseline["thresholds"]
        self.baseline_metrics = self.baseline["metrics"]

    def test_1816_pass_zero_tracks(self):
        metrics = {"fused_track_count": 0, "yolo_accepted_boxes_total": 0, "species_detected_count": 0}
        self.assertEqual(
            evaluate_clip("1816", metrics, thresholds=self.thresholds, baseline_metrics=self.baseline_metrics),
            [],
        )

    def test_1816_fail_fp_tracks(self):
        metrics = {"fused_track_count": 2, "yolo_accepted_boxes_total": 1, "species_detected_count": 1}
        fails = evaluate_clip("1816", metrics, thresholds=self.thresholds, baseline_metrics=self.baseline_metrics)
        self.assertTrue(any("1816 FP" in f for f in fails))

    def test_1819_pass_with_tracks(self):
        metrics = {
            "fused_track_count": 2,
            "frames_with_tracks": 2,
            "species_detected_count": 1,
            "track_id_switches_count": 0,
            "avg_track_duration_sec": 0.5,
            "tracking_unified_with_live": True,
        }
        self.assertEqual(
            evaluate_clip("1819", metrics, thresholds=self.thresholds, baseline_metrics=self.baseline_metrics),
            [],
        )

    def test_1819_fail_recall(self):
        metrics = {"fused_track_count": 0, "frames_with_tracks": 0, "species_detected_count": 0}
        fails = evaluate_clip("1819", metrics, thresholds=self.thresholds, baseline_metrics=self.baseline_metrics)
        self.assertTrue(any("1819 recall" in f for f in fails))

    def test_1819_fail_stability_switches(self):
        metrics = {
            "fused_track_count": 2,
            "frames_with_tracks": 2,
            "species_detected_count": 1,
            "track_id_switches_count": 20,
            "avg_track_duration_sec": 1.0,
        }
        fails = evaluate_clip("1819", metrics, thresholds=self.thresholds, baseline_metrics=self.baseline_metrics)
        self.assertTrue(any("stability" in f for f in fails))

    def test_manifest_and_baseline_schema(self):
        manifest = json.loads((REPO / "benchmarks" / "golden_clips.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest.get("schema"), "sota_golden_clips@v1")
        self.assertIn("1816", manifest.get("clips", {}))
        self.assertIn("1819", manifest.get("clips", {}))


if __name__ == "__main__":
    unittest.main()
