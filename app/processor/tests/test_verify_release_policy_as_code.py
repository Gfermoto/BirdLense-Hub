"""Tests for scripts/verify_release_policy_as_code.py (#554)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]


def _load_mod():
    path = _REPO_ROOT / "scripts" / "verify_release_policy_as_code.py"
    spec = importlib.util.spec_from_file_location(
        "verify_release_policy_as_code",
        path,
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["verify_release_policy_as_code"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_release_policy_ok_when_coverage_and_overrides_valid():
    mod = _load_mod()
    report = mod.evaluate_release_policy(
        contract={
            "required_policies": ["a", "b"],
            "min_release_events": 2,
            "min_policy_coverage_ratio": 1.0,
            "max_manual_override_ratio": 0.5,
            "require_override_audit_trail": True,
        },
        audit_rows=[
            {
                "release_id": "r1",
                "policy_id": "a",
                "gate_enforced": True,
                "manual_override": False,
            },
            {
                "release_id": "r2",
                "policy_id": "b",
                "gate_enforced": True,
                "manual_override": True,
                "override_reason": "incident",
                "override_approved_by": "gov",
                "override_ticket": "BL-1",
            },
        ],
    )
    assert report["ok"] is True


def test_release_policy_fails_on_missing_audit_for_override():
    mod = _load_mod()
    report = mod.evaluate_release_policy(
        contract={
            "required_policies": ["a"],
            "min_release_events": 1,
            "min_policy_coverage_ratio": 1.0,
            "max_manual_override_ratio": 1.0,
            "require_override_audit_trail": True,
        },
        audit_rows=[
            {
                "release_id": "r1",
                "policy_id": "a",
                "gate_enforced": True,
                "manual_override": True,
            }
        ],
    )
    assert report["ok"] is False
    assert report["checks"]["override_audit_ok"] is False
