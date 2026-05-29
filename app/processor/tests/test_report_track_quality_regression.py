"""Synthetic tests for scripts/report_track_quality_regression.py (#519)."""

import os
import sys
import unittest

_current_dir = os.path.dirname(os.path.abspath(__file__))
_repo_root = os.path.abspath(os.path.join(_current_dir, "../../.."))
_scripts_path = os.path.join(_repo_root, "scripts")
if _scripts_path not in sys.path:
    sys.path.insert(0, _scripts_path)


class TestTrackQualityRegressionReport(unittest.TestCase):
    def test_report_passes_when_no_regression(self):
        from report_track_quality_regression import (
            build_track_quality_regression_report,
        )

        payload = {
            "domain_contract_version": "2026-04-polish-v1",
            "metrics": {
                "track_rows_with_id_24h": 120,
                "track_stability_score_avg_24h": 0.82,
                "track_rows_fragmented_ratio_24h": 0.12,
                "track_rows_with_gaps_ratio_24h": 0.08,
                "track_stability_score_delta_prev_24h": 0.01,
                "track_fragmented_ratio_delta_prev_24h": -0.01,
                "track_gaps_ratio_delta_prev_24h": -0.01,
                "track_quality_regression_24h": False,
            },
            "samples": {
                "track_quality_regression_24h": {
                    "current_sample": 120,
                    "previous_sample": 130,
                    "reasons": [],
                },
                "track_unstable_examples_24h": [],
            },
            "strict_quality": {"strict_quality_ready": True},
        }
        out = build_track_quality_regression_report(
            domain_health_payload=payload,
            base_url="http://127.0.0.1:8085",
            fail_on_regression=True,
        )
        self.assertTrue(out["ok"])
        self.assertTrue(out["gates"]["track_quality_regression_absent"])
        self.assertTrue(out["gates"]["strict_quality_ready"])

    def test_report_fails_when_regression_present(self):
        from report_track_quality_regression import (
            build_track_quality_regression_report,
        )

        payload = {
            "domain_contract_version": "2026-04-polish-v1",
            "metrics": {
                "track_rows_with_id_24h": 240,
                "track_stability_score_avg_24h": 0.61,
                "track_rows_fragmented_ratio_24h": 0.33,
                "track_rows_with_gaps_ratio_24h": 0.27,
                "track_stability_score_delta_prev_24h": -0.08,
                "track_fragmented_ratio_delta_prev_24h": 0.09,
                "track_gaps_ratio_delta_prev_24h": 0.07,
                "track_quality_regression_24h": True,
            },
            "samples": {
                "track_quality_regression_24h": {
                    "current_sample": 240,
                    "previous_sample": 210,
                    "reasons": [
                        "stability_drop",
                        "fragmentation_rise",
                    ],
                },
                "track_unstable_examples_24h": [{"detection_id": 1}],
            },
            "strict_quality": {"strict_quality_ready": True},
        }
        out = build_track_quality_regression_report(
            domain_health_payload=payload,
            base_url="http://127.0.0.1:8085",
            fail_on_regression=True,
        )
        self.assertFalse(out["ok"])
        self.assertFalse(out["gates"]["track_quality_regression_absent"])
        self.assertTrue(out["gates"]["strict_quality_ready"])


if __name__ == "__main__":
    unittest.main()
