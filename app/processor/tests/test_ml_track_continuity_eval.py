"""Synthetic tests for scripts/ml_track_continuity_eval.py (#414)."""

import os
import sys
import unittest

_current_dir = os.path.dirname(os.path.abspath(__file__))
_repo_root = os.path.abspath(os.path.join(_current_dir, "../../.."))
_scripts_path = os.path.join(_repo_root, "scripts")
if _scripts_path not in sys.path:
    sys.path.insert(0, _scripts_path)


class TestMlTrackContinuityEval(unittest.TestCase):
    def test_eval_passes_for_good_ratios(self):
        from ml_track_continuity_eval import build_track_continuity_eval_report

        continuity = {
            "schema": "detector_continuity_report@v1",
            "rows": {
                "yolo_like_rows_total": 1000,
                "yolo_like_rows_with_track_id": 995,
            },
            "metrics": {"track_continuity_ratio": 0.995},
        }
        out = build_track_continuity_eval_report(continuity_report=continuity)
        self.assertTrue(out["ok"])
        self.assertTrue(out["gates"]["empty_track_with_detection_rate_ok"])
        self.assertTrue(out["gates"]["track_emit_success_rate_ok"])

    def test_eval_fails_for_missing_track_ids(self):
        from ml_track_continuity_eval import build_track_continuity_eval_report

        continuity = {
            "schema": "detector_continuity_report@v1",
            "rows": {
                "yolo_like_rows_total": 100,
                "yolo_like_rows_with_track_id": 92,
            },
            "metrics": {"track_continuity_ratio": 0.92},
        }
        out = build_track_continuity_eval_report(continuity_report=continuity)
        self.assertFalse(out["ok"])
        self.assertFalse(out["gates"]["empty_track_with_detection_rate_ok"])
        self.assertFalse(out["gates"]["track_emit_success_rate_ok"])


if __name__ == "__main__":
    unittest.main()
