"""Synthetic tests for scripts/report_track_quality_core_metrics.py (#519)."""

import os
import sys
import unittest

_current_dir = os.path.dirname(os.path.abspath(__file__))
_repo_root = os.path.abspath(os.path.join(_current_dir, "../../.."))
_scripts_path = os.path.join(_repo_root, "scripts")
if _scripts_path not in sys.path:
    sys.path.insert(0, _scripts_path)


class TestTrackQualityCoreMetricsReport(unittest.TestCase):
    def test_report_passes_when_switches_and_proxies_are_ok(self):
        from report_track_quality_core_metrics import (
            build_track_quality_core_metrics_report,
        )

        sota = {
            "report_format": "benchmark_sota@v1",
            "clips": {
                "1819": {
                    "status": "PASS",
                    "metrics": {
                        "yolo_frames_ran": 100,
                        "frames_with_tracks": 80,
                        "fused_track_count": 5,
                        "track_id_switches_count": 1,
                        "avg_track_duration_sec": 0.5,
                    },
                }
            },
        }
        baseline = {
            "schema": "sota_golden_baseline@v1",
            "thresholds": {
                "1819": {
                    "max_track_id_switches": 8,
                    "min_avg_track_duration_sec": 0.2,
                }
            },
        }
        out = build_track_quality_core_metrics_report(
            benchmark_sota_report=sota,
            baseline=baseline,
            min_idf1_proxy=0.1,
            min_hota_proxy=0.1,
            max_fragmentation_proxy=0.95,
        )
        self.assertTrue(out["ok"])
        self.assertEqual(out["metrics"]["idsw_count"], 1)
        self.assertGreaterEqual(float(out["metrics"]["idf1_proxy"]), 0.1)

    def test_report_fails_when_idsw_and_hota_gate_fail(self):
        from report_track_quality_core_metrics import (
            build_track_quality_core_metrics_report,
        )

        sota = {
            "report_format": "benchmark_sota@v1",
            "clips": {
                "1819": {
                    "status": "FAIL",
                    "metrics": {
                        "yolo_frames_ran": 100,
                        "frames_with_tracks": 20,
                        "fused_track_count": 1,
                        "track_id_switches_count": 10,
                        "avg_track_duration_sec": 0.01,
                    },
                }
            },
        }
        baseline = {
            "schema": "sota_golden_baseline@v1",
            "thresholds": {
                "1819": {
                    "max_track_id_switches": 8,
                    "min_avg_track_duration_sec": 0.2,
                }
            },
        }
        out = build_track_quality_core_metrics_report(
            benchmark_sota_report=sota,
            baseline=baseline,
            min_idf1_proxy=0.6,
            min_hota_proxy=0.6,
            max_fragmentation_proxy=0.95,
        )
        self.assertFalse(out["ok"])
        self.assertFalse(out["gates"]["idsw_count_ok"])
        self.assertFalse(out["gates"]["hota_proxy_ok"])

    def test_report_skips_proxy_gates_for_smoke_baseline_without_tracks(self):
        from report_track_quality_core_metrics import (
            build_track_quality_core_metrics_report,
        )

        sota = {
            "report_format": "benchmark_sota@v1",
            "clips": {
                "1819": {
                    "status": "PASS",
                    "metrics": {
                        "yolo_frames_ran": 1,
                        "frames_with_tracks": 0,
                        "fused_track_count": 0,
                        "track_id_switches_count": 0,
                        "avg_track_duration_sec": 0.0,
                    },
                }
            },
        }
        baseline = {
            "schema": "sota_golden_baseline@v1",
            "thresholds": {
                "1819": {
                    "min_fused_track_count": 0,
                    "min_frames_with_tracks": 0,
                    "max_track_id_switches": 999,
                    "min_avg_track_duration_sec": 0.0,
                }
            },
        }
        out = build_track_quality_core_metrics_report(
            benchmark_sota_report=sota,
            baseline=baseline,
        )
        self.assertTrue(out["ok"])
        self.assertTrue(out["metrics"]["skip_proxy_gates_smoke_no_detections"])
        self.assertIsNone(out["metrics"]["idf1_proxy"])


if __name__ == "__main__":
    unittest.main()
