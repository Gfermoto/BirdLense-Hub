"""Tests for scripts/verify_docs_drift_gate.py (#542)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]


def _load_mod():
    path = _REPO_ROOT / "scripts" / "verify_docs_drift_gate.py"
    spec = importlib.util.spec_from_file_location(
        "verify_docs_drift_gate",
        path,
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["verify_docs_drift_gate"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_docs_drift_ok_when_all_contracts_hold():
    mod = _load_mod()
    report = mod.evaluate_docs_drift(
        nav_paths={"user/index.md"},
        redirects_mkdocs={"README.md": "index.md"},
        redirects_snippet={"README.md": "index.md"},
        inventory_rows=[
            {
                "path": "docs/user/index.md",
                "status": "keep",
            },
            {
                "path": "docs/README.md",
                "status": "redirect-stub",
            },
        ],
    )
    assert report["ok"] is True


def test_docs_drift_detects_nav_inventory_mismatch():
    mod = _load_mod()
    report = mod.evaluate_docs_drift(
        nav_paths={"user/missing.md"},
        redirects_mkdocs={},
        redirects_snippet={},
        inventory_rows=[],
    )
    assert report["ok"] is False
    assert report["checks"]["nav_inventory_sync_ok"] is False
