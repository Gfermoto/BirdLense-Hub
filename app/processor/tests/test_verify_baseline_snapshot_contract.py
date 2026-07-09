"""Tests for scripts/verify_baseline_snapshot_contract.py (#528)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]


def _load_mod():
    path = _REPO_ROOT / "scripts" / "verify_baseline_snapshot_contract.py"
    spec = importlib.util.spec_from_file_location(
        "verify_baseline_snapshot_contract",
        path,
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["verify_baseline_snapshot_contract"] = mod
    spec.loader.exec_module(mod)
    return mod


def _snapshot(*, epoch: str, material: str, errors: int) -> dict:
    return {
        "schema": "parity_daily_hold@v1",
        "base_url": "http://example:8085",
        "epoch_fingerprint": epoch,
        "errors": [{"error": "x"}] * errors,
        "trigger_graph": {"active_triggers": ["opencv", "frigate"]},
        "core_contract": {
            "ok": True,
            "health_ok": True,
            "readiness_ok": True,
            "status_web_ok": True,
        },
        "checks": {"status": {"web": "ok", "mqtt": "ok"}},
        "config_fingerprint": {"material_sha256": material},
    }


def test_compare_ok_when_equal_snapshots():
    mod = _load_mod()
    report = mod.compare_snapshots(
        baseline=_snapshot(epoch="a", material="m1", errors=0),
        current=_snapshot(epoch="b", material="m1", errors=0),
        tolerance=0.01,
    )
    assert report["ok"] is True
    assert report["checks"]["material_match"] is True


def test_compare_fails_when_material_mismatch_required():
    mod = _load_mod()
    report = mod.compare_snapshots(
        baseline=_snapshot(epoch="a", material="m1", errors=0),
        current=_snapshot(epoch="b", material="m2", errors=0),
        tolerance=0.01,
    )
    assert report["ok"] is False
    assert report["checks"]["material_match"] is False


def test_compare_fails_when_delta_above_tolerance():
    mod = _load_mod()
    report = mod.compare_snapshots(
        baseline=_snapshot(epoch="a", material="m1", errors=0),
        current=_snapshot(epoch="b", material="m1", errors=2),
        tolerance=0.01,
        require_same_material=False,
    )
    assert report["ok"] is False
    assert report["deltas"]["errors_total"]["within_tolerance"] is False
