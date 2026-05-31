"""Tests for scripts/verify_champion_challenger_shadow.py (#536)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]


def _load_mod():
    path = _REPO_ROOT / "scripts" / "verify_champion_challenger_shadow.py"
    spec = importlib.util.spec_from_file_location(
        "verify_champion_challenger_shadow",
        path,
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["verify_champion_challenger_shadow"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_shadow_pipeline_ok_for_safe_candidates():
    mod = _load_mod()
    report = mod.evaluate_shadow_pipeline(
        contract={
            "required_candidates": ["c1"],
            "min_shadow_coverage_ratio": 1.0,
            "require_documented_evidence": False,
            "require_safe_promotion_only": True,
        },
        history=[
            {
                "candidate_id": "c1",
                "champion_id": "base",
                "shadow_passed": True,
                "unsafe_promotion": False,
            }
        ],
    )
    assert report["ok"] is True


def test_shadow_pipeline_fails_on_unsafe_promotion():
    mod = _load_mod()
    report = mod.evaluate_shadow_pipeline(
        contract={
            "required_candidates": ["c1"],
            "min_shadow_coverage_ratio": 1.0,
            "require_documented_evidence": False,
            "require_safe_promotion_only": True,
        },
        history=[
            {
                "candidate_id": "c1",
                "champion_id": "base",
                "shadow_passed": True,
                "unsafe_promotion": True,
            }
        ],
    )
    assert report["ok"] is False
    assert report["checks"]["safe_promotion_only_ok"] is False
