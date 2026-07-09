"""Tests for scripts/report_deploy_contract.py (#545)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]


def _load_mod():
    path = _REPO_ROOT / "scripts" / "report_deploy_contract.py"
    spec = importlib.util.spec_from_file_location(
        "report_deploy_contract",
        path,
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["report_deploy_contract"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_idempotency_rate_is_one_for_repeated_success():
    mod = _load_mod()
    report = mod.evaluate_contract(
        [
            {"git_commit": "a", "status": "success"},
            {"git_commit": "a", "status": "success"},
            {"git_commit": "b", "status": "success"},
        ]
    )
    assert report["idempotency"]["pass_rate"] == 1.0


def test_idempotency_rate_drops_on_failed_repeat():
    mod = _load_mod()
    report = mod.evaluate_contract(
        [
            {"git_commit": "a", "status": "success"},
            {"git_commit": "a", "status": "failed"},
        ]
    )
    assert report["idempotency"]["pass_rate"] == 0.0
