"""Synthetic tests for scripts/report_track_quality_truthset_delta.py."""

import os
import sys
import unittest

_current_dir = os.path.dirname(os.path.abspath(__file__))
_repo_root = os.path.abspath(os.path.join(_current_dir, "../../.."))
_scripts_path = os.path.join(_repo_root, "scripts")
if _scripts_path not in sys.path:
    sys.path.insert(0, _scripts_path)


class TestTrackQualityTruthsetDeltaReport(unittest.TestCase):
    def test_delta_report_passes_when_improvements_present(self):
        from report_track_quality_truthset_delta import (
            build_truthset_delta_report,
        )

        baseline = {
            "schema": "sota_golden_baseline@v1",
            "thresholds": {"1819": {"max_track_id_switches": 8}},
            "metrics": {
                "1819": {
                    "yolo_frames_ran": 100,
                    "frames_with_tracks": 50,
                    "track_id_switches_count": 5,
                    "avg_track_duration_sec": 0.2,
                }
            },
        }
        sota = {
            "report_format": "benchmark_sota@v1",
            "clips": {
                "1819": {
                    "status": "PASS",
                    "metrics": {
                        "yolo_frames_ran": 100,
                        "frames_with_tracks": 70,
                        "track_id_switches_count": 3,
                        "avg_track_duration_sec": 0.3,
                    },
                }
            },
        }
        out = build_truthset_delta_report(
            baseline=baseline,
            benchmark_sota_report=sota,
            target_switch_reduction_ratio=0.2,
        )
        self.assertTrue(out["ok"])
        self.assertGreater(float(out["deltas"]["idf1_proxy_delta"]), 0.0)
        self.assertGreater(float(out["deltas"]["hota_proxy_delta"]), 0.0)

    def test_delta_report_fails_when_regression(self):
        from report_track_quality_truthset_delta import (
            build_truthset_delta_report,
        )

        baseline = {
            "schema": "sota_golden_baseline@v1",
            "thresholds": {"1819": {"max_track_id_switches": 8}},
            "metrics": {
                "1819": {
                    "yolo_frames_ran": 100,
                    "frames_with_tracks": 70,
                    "track_id_switches_count": 2,
                    "avg_track_duration_sec": 0.4,
                }
            },
        }
        sota = {
            "report_format": "benchmark_sota@v1",
            "clips": {
                "1819": {
                    "status": "FAIL",
                    "metrics": {
                        "yolo_frames_ran": 100,
                        "frames_with_tracks": 30,
                        "track_id_switches_count": 9,
                        "avg_track_duration_sec": 0.05,
                    },
                }
            },
        }
        out = build_truthset_delta_report(
            baseline=baseline,
            benchmark_sota_report=sota,
            target_switch_reduction_ratio=0.2,
        )
        self.assertFalse(out["ok"])
        self.assertFalse(out["gates"]["idsw_reduction_target_met"])


if __name__ == "__main__":
    unittest.main()
