"""Tests for scripts/verify_classifier_calibration_report.py."""

import os
import sys

_CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.abspath(os.path.join(_CURRENT_DIR, "../../.."))
_SCRIPTS_PATH = os.path.join(_REPO_ROOT, "scripts")
if _SCRIPTS_PATH not in sys.path:
    sys.path.insert(0, _SCRIPTS_PATH)

from verify_classifier_calibration_report import verify_report  # noqa: E402


def test_verify_report_passes_on_healthy_payload():
    report = {
        "corrections_analyzed": 10,
        "calibration_metrics": {"ece": 0.11},
        "topk_metrics": {
            "false_species_rate_before": 0.5,
            "unknown_share_after_policy": 0.3,
        },
    }
    ok, errs = verify_report(report=report)
    assert ok is True
    assert errs == []


def test_verify_report_fails_on_bad_payload():
    report = {
        "corrections_analyzed": 0,
        "calibration_metrics": {"ece": 0.9},
        "topk_metrics": {
            "false_species_rate_before": 0.99,
            "unknown_share_after_policy": 0.95,
        },
    }
    ok, errs = verify_report(report=report)
    assert ok is False
    assert any("no_corrections_samples" in e for e in errs)
    assert any("ece_too_high" in e for e in errs)
