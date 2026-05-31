"""Tests for scripts/verify_ui_contract_guard.py (#538)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]


def _load_mod():
    path = _REPO_ROOT / "scripts" / "verify_ui_contract_guard.py"
    spec = importlib.util.spec_from_file_location(
        "verify_ui_contract_guard",
        path,
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["verify_ui_contract_guard"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_guard_passes_when_codegen_and_typecheck_ok_without_drift():
    mod = _load_mod()
    report = mod.evaluate_results(
        codegen_ok=True,
        changed=False,
        typecheck_ok=True,
    )
    assert report["ok"] is True


def test_guard_fails_when_codegen_drift_detected():
    mod = _load_mod()
    report = mod.evaluate_results(
        codegen_ok=True,
        changed=True,
        typecheck_ok=True,
    )
    assert report["ok"] is False
