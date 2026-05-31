"""Tests for scripts/verify_integration_contract_registry.py (#547)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]


def _load_mod():
    path = _REPO_ROOT / "scripts" / "verify_integration_contract_registry.py"
    spec = importlib.util.spec_from_file_location(
        "verify_integration_contract_registry",
        path,
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["verify_integration_contract_registry"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_registry_ok_when_required_entries_present():
    mod = _load_mod()
    report = mod.evaluate_registry(
        registry={
            "required_ids": ["x"],
            "min_registry_size": 1,
            "contracts": [
                {
                    "id": "x",
                    "channel": "http",
                    "auth_mode": "mcp_token",
                    "contract_doc": "docs/user/runbooks.md",
                    "status_endpoint": "/api/ui/status",
                }
            ],
        },
        openapi_text="  /api/ui/status:\n",
    )
    assert report["ok"] is True


def test_registry_fails_when_required_id_missing():
    mod = _load_mod()
    report = mod.evaluate_registry(
        registry={
            "required_ids": ["missing"],
            "min_registry_size": 1,
            "contracts": [],
        },
        openapi_text="",
    )
    assert report["ok"] is False
    assert report["checks"]["required_ids_ok"] is False
