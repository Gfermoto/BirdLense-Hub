"""Synthetic tests for scripts/ml_int8_candidate_eval.py (#415)."""

import os
import sys
import unittest

_current_dir = os.path.dirname(os.path.abspath(__file__))
if _current_dir not in sys.path:
    sys.path.insert(0, _current_dir)


def _mk_report(runtime_s: float, matched: int, gold: int) -> dict:
    return {
        "schema": "benchmark_track_regen@v1",
        "videos": [
            {
                "runtime_seconds": runtime_s,
                "label_eval": {
                    "matched": matched,
                    "gold_count": gold,
                },
            }
        ],
    }


class TestMlInt8CandidateEval(unittest.TestCase):
    def test_go_when_latency_and_quality_ok(self):
        from ml_int8_candidate_eval import build_int8_candidate_eval_report

        baseline = _mk_report(runtime_s=20.0, matched=90, gold=100)
        candidate = _mk_report(runtime_s=14.0, matched=89, gold=100)
        continuity = {"metrics": {"track_gate_ok": True, "crop_gate_ok": True}}
        out = build_int8_candidate_eval_report(
            baseline_report=baseline,
            candidate_report=candidate,
            continuity_report=continuity,
        )
        self.assertTrue(out["ok"])
        self.assertEqual(out["go_no_go"], "go")

    def test_no_go_when_latency_not_improved(self):
        from ml_int8_candidate_eval import build_int8_candidate_eval_report

        baseline = _mk_report(runtime_s=20.0, matched=90, gold=100)
        candidate = _mk_report(runtime_s=19.0, matched=90, gold=100)
        continuity = {"metrics": {"track_gate_ok": True, "crop_gate_ok": True}}
        out = build_int8_candidate_eval_report(
            baseline_report=baseline,
            candidate_report=candidate,
            continuity_report=continuity,
        )
        self.assertFalse(out["ok"])
        self.assertFalse(out["gates"]["latency_improvement_ok"])


if __name__ == "__main__":
    unittest.main()
