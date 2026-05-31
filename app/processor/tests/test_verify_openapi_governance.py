"""Tests for scripts/verify_openapi_governance.py (#532)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]


def _load_mod():
    path = _REPO_ROOT / "scripts" / "verify_openapi_governance.py"
    spec = importlib.util.spec_from_file_location(
        "verify_openapi_governance",
        path,
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["verify_openapi_governance"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_governance_ok_when_ruleset_and_lint_pass():
    mod = _load_mod()
    report = mod.evaluate_governance(
        ruleset_present=True,
        spectral_ran=True,
        error_count=3,
        max_errors=5,
    )
    assert report["ok"] is True


def test_governance_fails_when_lint_fails():
    mod = _load_mod()
    report = mod.evaluate_governance(
        ruleset_present=True,
        spectral_ran=True,
        error_count=7,
        max_errors=5,
    )
    assert report["ok"] is False
