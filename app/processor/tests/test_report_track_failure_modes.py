"""Synthetic tests for scripts/report_track_failure_modes.py."""

import os
import sys
import unittest

_current_dir = os.path.dirname(os.path.abspath(__file__))
_repo_root = os.path.abspath(os.path.join(_current_dir, "../../.."))
_scripts_path = os.path.join(_repo_root, "scripts")
if _scripts_path not in sys.path:
    sys.path.insert(0, _scripts_path)


class TestTrackFailureModesReport(unittest.TestCase):
    def test_modes_report_passes_on_low_risk_metrics(self):
        from report_track_failure_modes import build_track_failure_modes_report

        sota = {
            "report_format": "benchmark_sota@v1",
            "clips": {
                "1816": {"metrics": {"yolo_accepted_boxes_total": 0}},
                "1819": {
                    "metrics": {
                        "track_id_switches_count": 2,
                        "avg_track_duration_sec": 0.4,
                        "yolo_frames_ran": 100,
                        "frames_with_tracks": 80,
                    }
                },
            },
        }
        trackers_ab = {
            "schema": "tracker_ab_report@v1",
            "rows": [
                {
                    "preset": "botsort_birdlense",
                    "recall_ratio_vs_baseline": 0.95,
                }
            ],
        }
        core = {
            "schema": "track_quality_core_metrics_report@v1",
            "metrics": {"hota_proxy": 0.4, "idf1_proxy": 0.8},
        }
        out = build_track_failure_modes_report(
            benchmark_sota_report=sota,
            benchmark_trackers_ab_report=trackers_ab,
            track_quality_core_metrics_report=core,
        )
        self.assertTrue(out["ok"])
        self.assertEqual(out["failure_modes"]["occlusion"]["risk"], "low")

    def test_modes_report_fails_on_high_risk(self):
        from report_track_failure_modes import build_track_failure_modes_report

        sota = {
            "report_format": "benchmark_sota@v1",
            "clips": {
                "1816": {"metrics": {"yolo_accepted_boxes_total": 5}},
                "1819": {
                    "metrics": {
                        "track_id_switches_count": 10,
                        "avg_track_duration_sec": 0.05,
                        "yolo_frames_ran": 100,
                        "frames_with_tracks": 20,
                    }
                },
            },
        }
        trackers_ab = {"schema": "tracker_ab_report@v1", "rows": []}
        core = {
            "schema": "track_quality_core_metrics_report@v1",
            "metrics": {"hota_proxy": 0.01, "idf1_proxy": 0.02},
        }
        out = build_track_failure_modes_report(
            benchmark_sota_report=sota,
            benchmark_trackers_ab_report=trackers_ab,
            track_quality_core_metrics_report=core,
        )
        self.assertFalse(out["ok"])
        self.assertEqual(out["failure_modes"]["occlusion"]["risk"], "high")
        self.assertEqual(out["failure_modes"]["night_noise"]["risk"], "high")

    def test_modes_report_skips_gates_for_smoke_no_detections(self):
        from report_track_failure_modes import build_track_failure_modes_report

        sota = {
            "report_format": "benchmark_sota@v1",
            "clips": {
                "1819": {
                    "metrics": {
                        "track_id_switches_count": 0,
                        "avg_track_duration_sec": 0.0,
                        "yolo_frames_ran": 40,
                        "frames_with_tracks": 0,
                    }
                },
            },
        }
        core = {
            "schema": "track_quality_core_metrics_report@v1",
            "metrics": {
                "hota_proxy": None,
                "idf1_proxy": None,
                "skip_proxy_gates_smoke_no_detections": True,
            },
        }
        out = build_track_failure_modes_report(
            benchmark_sota_report=sota,
            benchmark_trackers_ab_report={"schema": "tracker_ab_report@v1", "rows": []},
            track_quality_core_metrics_report=core,
        )
        self.assertTrue(out["ok"])
        self.assertTrue(out["metrics"]["skip_gates_smoke_no_detections"])


if __name__ == "__main__":
    unittest.main()
