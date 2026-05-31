"""Tests for scripts/verify_scripts_ownership.py (#549)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]


def _load_mod():
    path = _REPO_ROOT / "scripts" / "verify_scripts_ownership.py"
    spec = importlib.util.spec_from_file_location(
        "verify_scripts_ownership",
        path,
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["verify_scripts_ownership"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_registry_passes_with_required_entries():
    mod = _load_mod()
    report = mod.evaluate_registry(
        {
            "required_ids": ["x"],
            "allowed_lifecycle": ["active", "deprecated"],
            "min_coverage_ratio": 1.0,
            "scripts": [
                {
                    "id": "x",
                    "path": "scripts/verify_scripts_ownership.py",
                    "owner": "tooling",
                    "runbook": "docs/user/runbooks.md",
                    "lifecycle": "active",
                }
            ],
        }
    )
    assert report["ok"] is True


def test_registry_fails_without_owner_and_required():
    mod = _load_mod()
    report = mod.evaluate_registry(
        {
            "required_ids": ["y"],
            "allowed_lifecycle": ["active"],
            "min_coverage_ratio": 1.0,
            "scripts": [
                {
                    "id": "x",
                    "path": "scripts/verify_scripts_ownership.py",
                    "owner": "",
                    "runbook": "docs/user/runbooks.md",
                    "lifecycle": "active",
                }
            ],
        }
    )
    assert report["ok"] is False
    assert report["checks"]["required_ids_ok"] is False
    assert report["checks"]["owner_coverage_ok"] is False
