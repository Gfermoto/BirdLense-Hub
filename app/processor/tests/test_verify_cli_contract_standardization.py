"""Tests for scripts/verify_cli_contract_standardization.py (#550)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]


def _load_mod():
    path = _REPO_ROOT / "scripts" / "verify_cli_contract_standardization.py"
    spec = importlib.util.spec_from_file_location(
        "verify_cli_contract_standardization",
        path,
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["verify_cli_contract_standardization"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_cli_contract_ok_when_all_probes_pass():
    mod = _load_mod()
    report = mod.evaluate_cli_contract(
        registry={
            "required_cli_ids": ["a"],
            "min_cli_total": 1,
            "require_help_exit_zero": True,
            "require_invalid_arg_nonzero": True,
            "require_structured_json_output": True,
        },
        probes=[
            {
                "id": "a",
                "owner": "cli-lead",
                "exists": True,
                "help_code": 0,
                "invalid_code": 2,
                "help_has_usage": True,
                "structured_json_output": True,
            }
        ],
    )
    assert report["ok"] is True


def test_cli_contract_fails_on_help_exit():
    mod = _load_mod()
    report = mod.evaluate_cli_contract(
        registry={
            "required_cli_ids": ["a"],
            "min_cli_total": 1,
            "require_help_exit_zero": True,
            "require_invalid_arg_nonzero": True,
            "require_structured_json_output": True,
        },
        probes=[
            {
                "id": "a",
                "owner": "cli-lead",
                "exists": True,
                "help_code": 1,
                "invalid_code": 2,
                "help_has_usage": True,
                "structured_json_output": True,
            }
        ],
    )
    assert report["ok"] is False
    assert report["checks"]["help_exit_ok"] is False
