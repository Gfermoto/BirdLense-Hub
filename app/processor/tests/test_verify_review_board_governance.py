"""Tests for scripts/verify_review_board_governance.py (#553)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]


def _load_mod():
    path = _REPO_ROOT / "scripts" / "verify_review_board_governance.py"
    spec = importlib.util.spec_from_file_location(
        "verify_review_board_governance",
        path,
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["verify_review_board_governance"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_review_board_ok_when_sessions_and_triage_are_complete():
    mod = _load_mod()
    report = mod.evaluate_review_board(
        contract={
            "required_domains": ["reliability", "security"],
            "min_sessions_total": 2,
            "max_untriaged_p0_p1": 0,
            "min_cadence_adherence_ratio": 1.0,
        },
        sessions=[
            {
                "session_id": "a",
                "domain": "reliability",
                "conducted": True,
                "findings": [
                    {
                        "id": "F1",
                        "severity": "p1",
                        "owner": "x",
                        "decision": "mitigate",
                    }
                ],
            },
            {
                "session_id": "b",
                "domain": "security",
                "conducted": True,
                "findings": [],
            },
        ],
    )
    assert report["ok"] is True


def test_review_board_fails_on_untriaged_critical():
    mod = _load_mod()
    report = mod.evaluate_review_board(
        contract={
            "required_domains": ["reliability"],
            "min_sessions_total": 1,
            "max_untriaged_p0_p1": 0,
            "min_cadence_adherence_ratio": 1.0,
        },
        sessions=[
            {
                "session_id": "a",
                "domain": "reliability",
                "conducted": True,
                "findings": [
                    {
                        "id": "F1",
                        "severity": "p0",
                        "owner": "",
                        "decision": "",
                    }
                ],
            }
        ],
    )
    assert report["ok"] is False
    assert report["checks"]["untriaged_critical_ok"] is False
