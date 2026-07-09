"""Tests for scripts/report_feedback_effect.py."""

import os
import sys

_CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.abspath(os.path.join(_CURRENT_DIR, "../../.."))
_SCRIPTS_PATH = os.path.join(_REPO_ROOT, "scripts")
if _SCRIPTS_PATH not in sys.path:
    sys.path.insert(0, _SCRIPTS_PATH)

from report_feedback_effect import build_feedback_effect_report  # noqa: E402


def test_feedback_effect_report_ok_when_metrics_improve():
    base = {
        "schema": "classifier_calibration_report@v1",
        "topk_metrics": {
            "top1_before": 0.5,
            "top3_proxy_before": 0.7,
            "false_species_rate_before": 0.4,
        },
        "calibration_metrics": {"ece": 0.2},
    }
    cur = {
        "schema": "classifier_calibration_report@v1",
        "topk_metrics": {
            "top1_before": 0.55,
            "top3_proxy_before": 0.72,
            "false_species_rate_before": 0.3,
        },
        "calibration_metrics": {"ece": 0.15},
    }
    out = build_feedback_effect_report(
        baseline_report=base,
        current_report=cur,
    )
    assert out["schema"] == "feedback_effect_report@v1"
    assert out["ok"] is True


def test_feedback_effect_report_not_ok_on_regression():
    base = {
        "schema": "classifier_calibration_report@v1",
        "topk_metrics": {
            "top1_before": 0.6,
            "top3_proxy_before": 0.8,
            "false_species_rate_before": 0.3,
        },
        "calibration_metrics": {"ece": 0.1},
    }
    cur = {
        "schema": "classifier_calibration_report@v1",
        "topk_metrics": {
            "top1_before": 0.5,
            "top3_proxy_before": 0.7,
            "false_species_rate_before": 0.35,
        },
        "calibration_metrics": {"ece": 0.2},
    }
    out = build_feedback_effect_report(
        baseline_report=base,
        current_report=cur,
    )
    assert out["ok"] is False
