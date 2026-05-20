"""Unit tests for scoring_telemetry."""

from __future__ import annotations

import os
import sys
import unittest

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(current_dir, "../src"))

from scoring_telemetry import ScoringTelemetry  # noqa: E402


class TestScoringTelemetry(unittest.TestCase):
    def test_review_degradation_alert(self):
        tel = ScoringTelemetry()
        traces = []
        for i in range(30):
            zone = "review" if i < 25 else "accept"
            traces.append(
                {
                    "frame_index": i,
                    "track_id": 1,
                    "raw_conf": 0.45,
                    "final_score": 0.45,
                    "final_decision": zone,
                    "reject_reason": None,
                    "motion_score": 0.3,
                    "shape_score": 0.4,
                    "bg_score": 0.3,
                }
            )
        tel.record_decisions(traces)
        snap = tel.snapshot()
        self.assertTrue(snap.degradation_alert)
        self.assertIn("review_share", snap.degradation_reason or "")


if __name__ == "__main__":
    unittest.main()
