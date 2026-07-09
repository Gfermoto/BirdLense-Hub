"""Tests for scripts/verify_critical_ux_suite.py (#540)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]


def _load_mod():
    path = _REPO_ROOT / "scripts" / "verify_critical_ux_suite.py"
    spec = importlib.util.spec_from_file_location(
        "verify_critical_ux_suite",
        path,
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["verify_critical_ux_suite"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_suite_pass_rate_computation():
    mod = _load_mod()
    rate, total, passed = mod._suite_pass_rate(
        [
            {"suite": "smoke", "total": 10, "passed": 9},
            {"suite": "smoke", "total": 10, "passed": 10},
            {"suite": "api", "total": 5, "passed": 5},
        ]
    )
    assert total == 20
    assert passed == 19
    assert round(rate, 6) == 0.95


def test_report_pass_rate_gate():
    mod = _load_mod()
    report = mod.evaluate_suite(
        contract={
            "flows": [
                {
                    "id": "timeline",
                    "path": "/timeline",
                    "test_name_pattern": "Timeline page loads",
                }
            ],
            "min_pass_rate": 0.90,
        },
        history=[{"suite": "smoke", "total": 10, "passed": 10}],
    )
    assert report["reliability"]["ok"] is True
