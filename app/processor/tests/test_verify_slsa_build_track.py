"""Tests for scripts/verify_slsa_build_track.py (#546)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]


def _load_mod():
    path = _REPO_ROOT / "scripts" / "verify_slsa_build_track.py"
    spec = importlib.util.spec_from_file_location(
        "verify_slsa_build_track",
        path,
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["verify_slsa_build_track"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_slsa_track_ok_when_all_controls_present():
    mod = _load_mod()
    report = mod.evaluate_slsa_track(
        plan={
            "required_controls": [
                "workflow_dispatch",
                "concurrency",
                "bandit_scan",
                "pip_audit_scan",
                "no_self_hosted_runner",
            ],
            "min_control_adoption_pct": 100.0,
        },
        ci_text=(
            "workflow_dispatch:\n"
            "concurrency:\n"
            "cancel-in-progress: true\n"
            "bandit -r web/ processor/src\n"
            "pip-audit -r web/requirements.txt\n"
            "runs-on: ubuntu-latest\n"
        ),
        workflow_exists=True,
    )
    assert report["ok"] is True


def test_slsa_track_fails_when_controls_missing():
    mod = _load_mod()
    report = mod.evaluate_slsa_track(
        plan={
            "required_controls": ["workflow_dispatch", "concurrency"],
            "min_control_adoption_pct": 100.0,
        },
        ci_text="workflow_dispatch:\n",
        workflow_exists=True,
    )
    assert report["ok"] is False
