"""Unit tests for scripts/report_quality_outcome_metrics.py."""

import os
import sys
import unittest


_current_dir = os.path.dirname(os.path.abspath(__file__))
_repo_root = os.path.abspath(os.path.join(_current_dir, "../../.."))
_scripts_path = os.path.join(_repo_root, "scripts")
if _scripts_path not in sys.path:
    sys.path.insert(0, _scripts_path)


class TestReportQualityOutcomeMetrics(unittest.TestCase):
    def test_tracks_coverage_excludes_fp_empty_recording_sessions(self):
        from report_quality_outcome_metrics import evaluate

        fp_payload = {
            "trigger_source": "opencv",
            "trigger_graph": {
                "init_source": "opencv",
                "metrics_by_source": {
                    "opencv": {"fp_empty_recording": 1},
                },
            },
        }
        hit_payload = {
            "trigger_source": "frigate",
            "trigger_graph": {
                "init_source": "frigate",
                "metrics_by_source": {
                    "frigate": {"fp_empty_recording": 0},
                },
            },
        }
        rows = [
            {
                "yolo_frames_ran": 40,
                "yolo_frames_with_tracks": 0,
                "yolo_raw_boxes_total": 0,
                "session_extended_by_frigate_only": 0,
                "yolo_blind_confirmed": 0,
                "rejected_decision_rows": 0,
                "trigger_to_first_bbox_latency_s": None,
                "finalize_duration_ms": None,
                "payload_json": __import__("json").dumps(fp_payload),
            },
            {
                "yolo_frames_ran": 40,
                "yolo_frames_with_tracks": 10,
                "yolo_raw_boxes_total": 12,
                "session_extended_by_frigate_only": 0,
                "yolo_blind_confirmed": 0,
                "rejected_decision_rows": 0,
                "trigger_to_first_bbox_latency_s": 1.0,
                "finalize_duration_ms": 100.0,
                "payload_json": __import__("json").dumps(hit_payload),
            },
        ]

        report = evaluate(
            rows,
            {
                "lookback_hours": 24,
                "max_blind_rate": 0.3,
                "min_tracks_coverage": 0.5,
                "max_empty_bbox_rate": 0.2,
                "min_yolo_frames_with_tracks": 1,
                "max_ingest_pruned_rows_per_hour_delta_vs_7d": 0.0,
                "max_frigate_catches_missed_birds_rate": 0.1,
                "max_frigate_catches_missed_birds_rate_delta_vs_7d": 0.08,
            },
        )

        metrics = report["metrics"]
        self.assertEqual(metrics["sessions_fp_empty_recording"], 1)
        self.assertEqual(metrics["tracks_eligible_sessions"], 1)
        self.assertEqual(metrics["tracks_coverage"], 1.0)
        self.assertTrue(report["gate"]["ok"])


if __name__ == "__main__":
    unittest.main()
