"""Tests for scripts/report_active_learning_backlog.py."""

import os
import sys

_CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.abspath(os.path.join(_CURRENT_DIR, "../../.."))
_SCRIPTS_PATH = os.path.join(_REPO_ROOT, "scripts")
if _SCRIPTS_PATH not in sys.path:
    sys.path.insert(0, _SCRIPTS_PATH)

from report_active_learning_backlog import build_backlog_report  # noqa: E402


def test_build_backlog_report_emits_priority_items():
    track = {
        "schema": "track_quality_regression_report@v1",
        "metrics": {
            "parity_mismatch_rate_24h": 0.3,
            "track_id_switch_rate_24h": 0.1,
        },
    }
    species = {
        "schema": "classifier_calibration_report@v1",
        "topk_metrics": {
            "false_species_rate_before": 0.4,
        },
        "unknown_ood_dashboard": {
            "unknown_policy": {"unknown_share_after_policy": 0.4},
        },
        "top_confusion_pairs": [
            {"from": "Wood Mouse", "to": "Great Tit", "count": 7}
        ],
    }
    truth = {
        "schema": "track_quality_truthset_delta_report@v1",
        "deltas": {"idsw_reduction_ratio": -0.2},
    }
    out = build_backlog_report(
        track_regression_report=track,
        species_calibration_report=species,
        truthset_delta_report=truth,
    )
    assert out["schema"] == "active_learning_backlog@v1"
    assert out["ok"] is True
    assert out["items_total"] >= 4
