"""Tests for scripts/verify_similarity_behavior_summary.py."""

import os
import sys

_CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.abspath(os.path.join(_CURRENT_DIR, "../../.."))
_SCRIPTS_PATH = os.path.join(_REPO_ROOT, "scripts")
if _SCRIPTS_PATH not in sys.path:
    sys.path.insert(0, _SCRIPTS_PATH)

from verify_similarity_behavior_summary import verify_report  # noqa: E402


def test_verify_similarity_behavior_summary_ok():
    report = {
        "schema": "similarity_behavior_summary@v1",
        "similarity": {"topk_hit_rate": 0.8, "p95_query_ms": 22.5},
        "behavior": {"macro_f1": 0.67},
        "runtime_cost": {"retrieval_p95_ok": True},
    }
    errs = verify_report(
        report,
        min_topk_hit_rate=0.6,
        min_behavior_macro_f1=0.4,
        max_retrieval_p95_ms=50.0,
    )
    assert errs == []


def test_verify_similarity_behavior_summary_fails():
    report = {
        "schema": "similarity_behavior_summary@v1",
        "similarity": {"topk_hit_rate": 0.2, "p95_query_ms": 90.0},
        "behavior": {"macro_f1": 0.1},
        "runtime_cost": {"retrieval_p95_ok": False},
    }
    errs = verify_report(
        report,
        min_topk_hit_rate=0.6,
        min_behavior_macro_f1=0.4,
        max_retrieval_p95_ms=50.0,
    )
    assert "topk_hit_rate_below_threshold" in errs
    assert "behavior_macro_f1_below_threshold" in errs
    assert "retrieval_p95_ms_above_threshold" in errs
    assert "runtime_guardrail_failed" in errs
