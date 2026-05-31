"""Tests for scripts/verify_nas_storage_contract.py (#350)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]


def _load_mod():
    path = _REPO_ROOT / "scripts" / "verify_nas_storage_contract.py"
    spec = importlib.util.spec_from_file_location(
        "verify_nas_storage_contract",
        path,
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["verify_nas_storage_contract"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_nas_contract_passes_against_repo():
    mod = _load_mod()
    report = mod.evaluate_nas_contract(
        {
            "required_modes": [
                "local_plus_background_sync",
                "offload_after_success",
            ],
            "required_components": [
                "processor_remote_mirror",
                "ui_storage_card",
                "ui_api_test_endpoint",
                "default_config_block",
                "user_docs",
            ],
            "required_docs_keywords": [
                "NAS",
                "SFTP",
                "recordings_mirror",
                "delete_local_after_success",
            ],
        }
    )
    assert report["ok"] is True


def test_nas_contract_fails_on_missing_keywords():
    mod = _load_mod()
    report = mod.evaluate_nas_contract(
        {
            "required_modes": [],
            "required_components": [],
            "required_docs_keywords": ["__missing_keyword__"],
        }
    )
    assert report["ok"] is False
    assert report["checks"]["docs_keywords_ok"] is False
