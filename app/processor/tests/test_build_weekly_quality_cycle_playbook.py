"""Tests for scripts/build_weekly_quality_cycle_playbook.py."""

import os
import sys

_CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.abspath(os.path.join(_CURRENT_DIR, "../../.."))
_SCRIPTS_PATH = os.path.join(_REPO_ROOT, "scripts")
if _SCRIPTS_PATH not in sys.path:
    sys.path.insert(0, _SCRIPTS_PATH)

from build_weekly_quality_cycle_playbook import build_playbook  # noqa: E402


def test_build_playbook_ok_when_backlog_has_items():
    backlog = {
        "schema": "active_learning_backlog@v1",
        "items": [
            {"action": "mine_fp_fn_from_recent_sessions"},
            {"action": "sample_negative_flip_subset"},
        ],
    }
    feedback = {"schema": "feedback_loop_status@v1", "events_total": 12}
    out = build_playbook(
        backlog_report=backlog,
        feedback_loop_status=feedback,
    )
    assert out["schema"] == "weekly_quality_cycle_playbook@v1"
    assert out["ok"] is True
    assert out["backlog_items_total"] == 2
