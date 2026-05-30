"""Tests for scripts/verify_ssdf_control_map.py (#551)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]


def _load_mod():
    path = _REPO_ROOT / "scripts" / "verify_ssdf_control_map.py"
    spec = importlib.util.spec_from_file_location(
        "verify_ssdf_control_map",
        path,
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["verify_ssdf_control_map"] = mod
    spec.loader.exec_module(mod)
    return mod


def _full_payload(status: str = "implemented") -> dict:
    controls = []
    for pid in (
        "PO.1",
        "PO.3",
        "PS.1",
        "PS.2",
        "PW.4",
        "PW.8",
        "RV.1",
        "RV.3",
    ):
        controls.append(
            {
                "ssdf_practice": pid,
                "priority": "P0",
                "owner": "Security",
                "status": status,
                "evidence": ["x"],
            }
        )
    return {"controls": controls}


def test_ssdf_map_passes_when_complete():
    mod = _load_mod()
    report = mod.evaluate_ssdf_map(_full_payload())
    assert report["ok"] is True
    assert report["coverage"]["percent"] == 100.0


def test_ssdf_map_fails_when_practice_missing():
    mod = _load_mod()
    payload = _full_payload()
    payload["controls"] = payload["controls"][:-1]
    report = mod.evaluate_ssdf_map(payload)
    assert report["ok"] is False
    assert "RV.3" in report["missing_practices"]


def test_ssdf_map_fails_when_p0_gap_not_implemented():
    mod = _load_mod()
    report = mod.evaluate_ssdf_map(_full_payload(status="planned"))
    assert report["ok"] is False
    assert report["p0_p1_open_gaps"] > 0
