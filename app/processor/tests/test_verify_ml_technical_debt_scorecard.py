"""Tests for scripts/verify_ml_technical_debt_scorecard.py (#537)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]


def _load_mod():
    path = _REPO_ROOT / "scripts" / "verify_ml_technical_debt_scorecard.py"
    spec = importlib.util.spec_from_file_location(
        "verify_ml_technical_debt_scorecard",
        path,
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["verify_ml_technical_debt_scorecard"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_scorecard_ok_when_contract_satisfied():
    mod = _load_mod()
    report = mod.evaluate_scorecard(
        {
            "min_checks_total": 2,
            "max_high_risk_open": 1,
            "allowed_status": ["closed", "open"],
            "allowed_risk": ["high", "low"],
            "checks": [
                {
                    "id": "x",
                    "owner": "ml",
                    "status": "closed",
                    "risk": "high",
                },
                {
                    "id": "y",
                    "owner": "ml",
                    "status": "open",
                    "risk": "low",
                },
            ],
        }
    )
    assert report["ok"] is True


def test_scorecard_fails_on_high_risk_open_overflow():
    mod = _load_mod()
    report = mod.evaluate_scorecard(
        {
            "min_checks_total": 1,
            "max_high_risk_open": 0,
            "allowed_status": ["open"],
            "allowed_risk": ["high"],
            "checks": [
                {
                    "id": "x",
                    "owner": "ml",
                    "status": "open",
                    "risk": "high",
                }
            ],
        }
    )
    assert report["ok"] is False
    assert report["checks"]["high_risk_open_ok"] is False
