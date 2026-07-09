"""Tests for scripts/compare_quality_cycle_reports.py."""

import os
import sys

_CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.abspath(os.path.join(_CURRENT_DIR, "../../.."))
_SCRIPTS_PATH = os.path.join(_REPO_ROOT, "scripts")
if _SCRIPTS_PATH not in sys.path:
    sys.path.insert(0, _SCRIPTS_PATH)

from compare_quality_cycle_reports import compare_reports  # noqa: E402


def test_compare_reports_ok_on_improvement():
    base = {
        "topk_metrics": {"top1_before": 0.5, "top3_proxy_before": 0.7},
        "calibration_metrics": {"ece": 0.2},
    }
    cur = {
        "topk_metrics": {"top1_before": 0.6, "top3_proxy_before": 0.8},
        "calibration_metrics": {"ece": 0.15},
    }
    out = compare_reports(baseline_report=base, current_report=cur)
    assert out["ok"] is True
    assert out["errors"] == []


def test_compare_reports_fail_on_regression():
    base = {
        "topk_metrics": {"top1_before": 0.6, "top3_proxy_before": 0.8},
        "calibration_metrics": {"ece": 0.1},
    }
    cur = {
        "topk_metrics": {"top1_before": 0.55, "top3_proxy_before": 0.75},
        "calibration_metrics": {"ece": 0.2},
    }
    out = compare_reports(baseline_report=base, current_report=cur)
    assert out["ok"] is False
    assert any("ece_regression" in e for e in out["errors"])
