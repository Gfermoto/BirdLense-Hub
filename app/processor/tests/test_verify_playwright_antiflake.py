"""Tests for scripts/verify_playwright_antiflake.py (#539)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]


def _load_mod():
    path = _REPO_ROOT / "scripts" / "verify_playwright_antiflake.py"
    spec = importlib.util.spec_from_file_location(
        "verify_playwright_antiflake",
        path,
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["verify_playwright_antiflake"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_flaky_rate_computation():
    mod = _load_mod()
    rate, tests_total, flaky_total = mod._flaky_rate(
        [
            {"tests_total": 10, "flaky_total": 1},
            {"tests_total": 20, "flaky_total": 2},
        ]
    )
    assert tests_total == 30
    assert flaky_total == 3
    assert round(rate, 6) == 0.1


def test_quarantine_schema_validation():
    mod = _load_mod()
    ok, issues = mod._quarantine_ok(
        {
            "tests": [
                {
                    "name": "a",
                    "reason": "unstable selector",
                    "owner": "qa",
                    "expires_at": "2026-06-30T00:00:00Z",
                }
            ]
        }
    )
    assert ok is True
    assert issues == []
