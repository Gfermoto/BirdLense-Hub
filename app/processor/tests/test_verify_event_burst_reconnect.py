"""Tests for scripts/verify_event_burst_reconnect.py (#548)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]


def _load_mod():
    path = _REPO_ROOT / "scripts" / "verify_event_burst_reconnect.py"
    spec = importlib.util.spec_from_file_location(
        "verify_event_burst_reconnect",
        path,
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["verify_event_burst_reconnect"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_resilience_report_passes_on_healthy_history():
    mod = _load_mod()
    report = mod.evaluate_resilience(
        contract={
            "required_scenarios": ["a", "b"],
            "min_history_rows": 2,
            "min_pass_rate": 0.95,
            "max_event_loss_rate": 0.02,
            "max_reconnect_recovery_ms_p95": 5000,
        },
        history=[
            {
                "scenario": "a",
                "runs_total": 100,
                "runs_passed": 98,
                "event_loss_rate": 0.01,
                "reconnect_recovery_ms_p95": 3200,
            },
            {
                "scenario": "b",
                "runs_total": 80,
                "runs_passed": 80,
                "event_loss_rate": 0.005,
                "reconnect_recovery_ms_p95": 2900,
            },
        ],
    )
    assert report["ok"] is True
    assert report["checks"]["required_scenarios_ok"] is True


def test_resilience_report_fails_on_missing_scenario_and_loss():
    mod = _load_mod()
    report = mod.evaluate_resilience(
        contract={
            "required_scenarios": ["a", "b"],
            "min_history_rows": 2,
            "min_pass_rate": 0.95,
            "max_event_loss_rate": 0.02,
            "max_reconnect_recovery_ms_p95": 5000,
        },
        history=[
            {
                "scenario": "a",
                "runs_total": 100,
                "runs_passed": 90,
                "event_loss_rate": 0.10,
                "reconnect_recovery_ms_p95": 6000,
            }
        ],
    )
    assert report["ok"] is False
    assert report["checks"]["required_scenarios_ok"] is False
    assert report["checks"]["event_loss_ok"] is False
