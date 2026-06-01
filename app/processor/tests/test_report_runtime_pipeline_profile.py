"""Tests for scripts/report_runtime_pipeline_profile.py."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]


def _load_mod():
    path = _REPO_ROOT / "scripts" / "report_runtime_pipeline_profile.py"
    spec = importlib.util.spec_from_file_location("report_runtime_pipeline_profile", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["report_runtime_pipeline_profile"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_profile_detects_finalize_bottleneck_and_warning():
    mod = _load_mod()
    rows = [
        {
            "payload_json": '{"fusion_duration_ms": 300, "persist_duration_ms": 200, "camera_slot": "camera_1"}',
            "trigger_to_first_bbox_latency_s": 2.1,
            "finalize_duration_ms": 4300,
        },
        {
            "payload_json": '{"fusion_duration_ms": 500, "persist_duration_ms": 250, "camera_slot": "camera_1"}',
            "trigger_to_first_bbox_latency_s": 2.4,
            "finalize_duration_ms": 6200,
        },
        {
            "payload_json": '{"fusion_duration_ms": 600, "persist_duration_ms": 320, "camera_slot": "camera_2"}',
            "trigger_to_first_bbox_latency_s": 6.4,
            "finalize_duration_ms": 9100,
        },
    ]
    report = mod.build_profile(
        rows,
        lookback_hours=24,
        first_bbox_warn_s=5.0,
        finalize_warn_ms=5000.0,
    )
    assert report["ok"] is True
    assert report["bottleneck_stage_p95"] == "finalize_duration_ms"
    assert any("finalize_duration_p95" in w for w in report["warnings"])
    assert report["by_slot_finalize_duration_ms"]["camera_1"]["n"] == 2
