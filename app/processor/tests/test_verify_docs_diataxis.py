"""Tests for scripts/verify_docs_diataxis.py (#541)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]


def _load_mod():
    path = _REPO_ROOT / "scripts" / "verify_docs_diataxis.py"
    spec = importlib.util.spec_from_file_location(
        "verify_docs_diataxis",
        path,
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["verify_docs_diataxis"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_diataxis_ok_when_types_and_coverage_pass():
    mod = _load_mod()
    report = mod.evaluate_diataxis(
        {
            "targets": [
                {
                    "path": "docs/user/install.md",
                    "diataxis_type": "tutorial",
                }
            ],
            "min_coverage_pct": 100.0,
            "max_cross_type_bleed_pct": 30.0,
        }
    )
    assert report["ok"] is True


def test_diataxis_fails_on_invalid_type():
    mod = _load_mod()
    report = mod.evaluate_diataxis(
        {
            "targets": [
                {
                    "path": "docs/user/install.md",
                    "diataxis_type": "mixed",
                }
            ],
            "min_coverage_pct": 100.0,
            "max_cross_type_bleed_pct": 30.0,
        }
    )
    assert report["ok"] is False
