"""Tests for scripts/verify_runbook_coverage.py (#543)."""

from __future__ import annotations

import importlib.util
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]


def _load_mod():
    path = _REPO_ROOT / "scripts" / "verify_runbook_coverage.py"
    spec = importlib.util.spec_from_file_location(
        "verify_runbook_coverage",
        path,
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["verify_runbook_coverage"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_report_ok_when_coverage_and_cadence_satisfied():
    mod = _load_mod()
    report = mod.evaluate_coverage(
        catalog={
            "incidents": [
                {
                    "id": "x",
                    "title": "X",
                    "runbook": "docs/runbooks/runtime-slo-stability.md",
                }
            ]
        },
        validation_history=[{"checked_at": (datetime.now(UTC) - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")}],
        min_cycles_per_week=1,
    )
    assert report["ok"] is True


def test_report_fails_when_weekly_cadence_missing():
    mod = _load_mod()
    report = mod.evaluate_coverage(
        catalog={
            "incidents": [
                {
                    "id": "x",
                    "title": "X",
                    "runbook": "docs/runbooks/runtime-slo-stability.md",
                }
            ]
        },
        validation_history=[],
        min_cycles_per_week=1,
    )
    assert report["ok"] is False
    assert report["validation_cadence"]["ok"] is False
