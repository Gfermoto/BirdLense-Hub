"""Tests for scripts/error_budget_gate.py."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]


def _load_mod():
    path = _REPO_ROOT / "scripts" / "error_budget_gate.py"
    spec = importlib.util.spec_from_file_location("error_budget_gate", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["error_budget_gate"] = mod
    spec.loader.exec_module(mod)
    return mod


def _report(*, critical: int, warning: int, status_ok: bool, cam_warn: int):
    rules = []
    for _ in range(critical):
        rules.append({"breach": True, "severity": "critical"})
    for _ in range(warning):
        rules.append({"breach": True, "severity": "warning"})
    return {
        "alerting_rules": rules,
        "slo_dashboard": {
            "snapshot": {"per_camera_warn_count_24h": cam_warn},
            "status": {"ok": status_ok},
        },
        "reliability_alerts": {
            "alerts": {"recording_artifact_failures": False},
        },
    }


def test_gate_ok_when_budget_not_exhausted():
    mod = _load_mod()
    payload = mod.evaluate_gate(
        _report(critical=1, warning=0, status_ok=True, cam_warn=0),
        override_reason="",
    )
    assert payload["budget"]["state"] == "ok"
    assert payload["gate"]["ok"] is True
    assert payload["gate"]["block_release"] is False


def test_gate_blocks_when_budget_exhausted():
    mod = _load_mod()
    payload = mod.evaluate_gate(
        _report(critical=2, warning=1, status_ok=False, cam_warn=2),
        override_reason="",
    )
    assert payload["budget"]["exhausted"] is True
    assert payload["gate"]["ok"] is False
    assert payload["gate"]["block_release"] is True


def test_gate_override_allows_release_when_exhausted():
    mod = _load_mod()
    payload = mod.evaluate_gate(
        _report(critical=3, warning=0, status_ok=False, cam_warn=4),
        override_reason="SRE approved emergency hotfix #529",
    )
    assert payload["budget"]["exhausted"] is True
    assert payload["gate"]["override_used"] is True
    assert payload["gate"]["ok"] is True


def test_unreachable_hub_payload_passes_without_require_hub():
    mod = _load_mod()
    payload = mod.build_unreachable_hub_payload(
        error="url_error:Connection refused",
        base_url="http://127.0.0.1:8085",
    )
    assert payload["gate"]["ok"] is True
    assert payload["gate"]["hub_unreachable"] is True
    assert payload["budget"]["state"] == "hub_unreachable"
