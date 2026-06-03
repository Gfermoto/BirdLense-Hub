"""Synthetic tests for scripts/parity_runner.py."""

import os
import sys
import unittest

_current_dir = os.path.dirname(os.path.abspath(__file__))
_repo_root = os.path.abspath(os.path.join(_current_dir, "../../.."))
_scripts_path = os.path.join(_repo_root, "scripts")
if _scripts_path not in sys.path:
    sys.path.insert(0, _scripts_path)


class TestParityRunner(unittest.TestCase):
    def test_build_parity_report_ok(self):
        from parity_runner import build_parity_report

        sota = {
            "report_format": "benchmark_sota@v1",
            "clips": {
                "1816": {"metrics": {"yolo_accepted_boxes_total": 0}},
                "1819": {
                    "metrics": {
                        "yolo_frames_ran": 100,
                        "frames_with_tracks": 80,
                    }
                },
            },
        }
        core = {
            "schema": "track_quality_core_metrics_report@v1",
            "ok": True,
            "metrics": {
                "hota_proxy": 0.3,
                "idf1_proxy": 0.8,
                "idsw_count": 1,
                "fragmentation_proxy": 0.2,
            },
        }
        truth = {
            "schema": "track_quality_truthset_delta_report@v1",
            "ok": True,
            "deltas": {
                "idsw_reduction_ratio": 0.4,
                "fragmentation_reduction_ratio": 0.4,
            },
        }
        fail = {
            "schema": "track_failure_modes_report@v1",
            "ok": True,
            "failure_modes": {"occlusion": {"risk": "low"}},
        }
        ab = {"schema": "tracker_ab_report@v1", "ok": True}
        events = {
            "available": True,
            "duration_p50_sec": 2.0,
            "duration_p90_sec": 10.0,
            "duration_max_sec": 20.0,
            "unknown_share": 0.1,
            "zone_transition_rate": None,
            "total_events": 12,
        }
        out = build_parity_report(
            benchmark_sota_report=sota,
            core_metrics_report=core,
            truthset_delta_report=truth,
            failure_modes_report=fail,
            tracker_ab_report=ab,
            event_metrics=events,
            period="daily",
        )
        self.assertTrue(out["ok"])
        self.assertEqual(out["schema"], "parity_report@v1")

    def test_build_parity_report_skips_gates_for_smoke_no_detections(self):
        from parity_runner import build_parity_report

        sota = {
            "report_format": "benchmark_sota@v1",
            "clips": {
                "1819": {
                    "metrics": {
                        "yolo_frames_ran": 40,
                        "frames_with_tracks": 0,
                    }
                },
            },
        }
        core = {
            "schema": "track_quality_core_metrics_report@v1",
            "ok": True,
            "metrics": {"skip_proxy_gates_smoke_no_detections": True},
        }
        out = build_parity_report(
            benchmark_sota_report=sota,
            core_metrics_report=core,
            truthset_delta_report={"ok": False},
            failure_modes_report={"ok": False},
            tracker_ab_report={"ok": False},
            event_metrics={"available": False},
            period="daily",
        )
        self.assertTrue(out["ok"])
        self.assertTrue(out["inputs"]["skip_smoke_gates_no_detections"])


if __name__ == "__main__":
    unittest.main()
