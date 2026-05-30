"""Tests for scripts/verify_health_readiness_contract.py (#530)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]


def _load_mod():
    path = _REPO_ROOT / "scripts" / "verify_health_readiness_contract.py"
    spec = importlib.util.spec_from_file_location(
        "verify_health_readiness_contract",
        path,
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["verify_health_readiness_contract"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_contract_ok_when_all_green():
    mod = _load_mod()
    report = mod.evaluate_contract(
        health_status_code=200,
        health_payload={"status": "ok"},
        readiness_status_code=200,
        readiness_payload={"ready": True},
        status_status_code=200,
        status_payload={"web": "ok", "processor": "ok"},
    )
    assert report["ok"] is True
    assert report["checks"]["false_green_detected"] is False


def test_contract_detects_false_green():
    mod = _load_mod()
    report = mod.evaluate_contract(
        health_status_code=200,
        health_payload={"status": "ok"},
        readiness_status_code=503,
        readiness_payload={"ready": False},
        status_status_code=200,
        status_payload={"web": "ok", "processor": "offline"},
    )
    assert report["ok"] is False
    assert report["checks"]["false_green_detected"] is True


def test_contract_fails_when_health_not_ok():
    mod = _load_mod()
    report = mod.evaluate_contract(
        health_status_code=500,
        health_payload={"status": "error"},
        readiness_status_code=200,
        readiness_payload={"ready": True},
        status_status_code=200,
        status_payload={"web": "ok", "processor": "ok"},
    )
    assert report["ok"] is False
    assert report["checks"]["health_ok"] is False
