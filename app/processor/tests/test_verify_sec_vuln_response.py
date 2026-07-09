"""Tests for scripts/verify_sec_vuln_response.py (#552)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]


def _load_mod():
    path = _REPO_ROOT / "scripts" / "verify_sec_vuln_response.py"
    spec = importlib.util.spec_from_file_location(
        "verify_sec_vuln_response",
        path,
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["verify_sec_vuln_response"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_gate_passes_when_controls_present_and_no_sla_gaps():
    mod = _load_mod()
    report = mod.evaluate_workflow(
        vuln_register={"items": []},
        gitleaks_present=True,
        ci_has_bandit=True,
        ci_has_pip_audit=True,
        ci_has_gitleaks=True,
        runbook_present=True,
    )
    assert report["ok"] is True


def test_gate_fails_when_p0_or_p1_vuln_has_no_owner_or_eta():
    mod = _load_mod()
    report = mod.evaluate_workflow(
        vuln_register={
            "items": [
                {"severity": "P0", "status": "open", "owner": "", "eta": ""},
            ]
        },
        gitleaks_present=True,
        ci_has_bandit=True,
        ci_has_pip_audit=True,
        ci_has_gitleaks=True,
        runbook_present=True,
    )
    assert report["ok"] is False
    assert report["vulnerability_register"]["p0_p1_missing_sla"] == 1
