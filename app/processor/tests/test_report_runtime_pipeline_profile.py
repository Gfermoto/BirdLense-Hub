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
        first_bbox_fail_s=None,
        finalize_warn_ms=5000.0,
        create_video_warn_ms=30000.0,
        create_video_fail_ms=None,
    )
    assert report["ok"] is True
    assert report["bottleneck_stage_p95"] == "finalize_duration_ms"
    assert any("finalize_duration_p95" in w for w in report["warnings"])
    assert report["by_slot_finalize_duration_ms"]["camera_1"]["n"] == 2


def test_profile_prefers_wall_clock_first_bbox_for_kpi():
    mod = _load_mod()
    rows = [
        {
            "payload_json": (
                '{"trigger_to_first_bbox_wall_s": 0.8, '
                '"trigger_to_first_track_wall_s": 1.1, "camera_slot": "camera_1"}'
            ),
            "trigger_to_first_bbox_latency_s": 35.0,
            "finalize_duration_ms": 900.0,
        },
        {
            "payload_json": '{"trigger_to_first_bbox_wall_s": 0.6, "camera_slot": "camera_2"}',
            "trigger_to_first_bbox_latency_s": 40.0,
            "finalize_duration_ms": 800.0,
        },
    ]
    report = mod.build_profile(
        rows,
        lookback_hours=24,
        first_bbox_warn_s=2.0,
        first_bbox_fail_s=None,
        finalize_warn_ms=5000.0,
        create_video_warn_ms=30000.0,
        create_video_fail_ms=None,
    )
    wall = report["profile"]["trigger_to_first_bbox_wall_s"]
    resolved = report["profile"]["trigger_to_first_bbox_latency_s"]
    assert wall["n"] == 2
    assert wall["max"] == 0.8
    assert resolved["max"] == 40.0
    assert report["warnings"] == []


def test_profile_bbox_kpi_fail_when_wall_p95_above_threshold():
    mod = _load_mod()
    rows = [
        {
            "payload_json": '{"trigger_to_first_bbox_wall_s": 3.5, "camera_slot": "camera_1"}',
            "trigger_to_first_bbox_latency_s": 0.5,
            "finalize_duration_ms": 900.0,
        },
        {
            "payload_json": '{"trigger_to_first_bbox_wall_s": 4.2, "camera_slot": "camera_2"}',
            "trigger_to_first_bbox_latency_s": 0.6,
            "finalize_duration_ms": 800.0,
        },
    ]
    report = mod.build_profile(
        rows,
        lookback_hours=24,
        first_bbox_warn_s=2.0,
        first_bbox_fail_s=2.0,
        finalize_warn_ms=5000.0,
        create_video_warn_ms=30000.0,
        create_video_fail_ms=60000.0,
    )
    assert report["kpi"]["ok"] is False
    assert report["failures"]
    assert report["ok"] is False


def test_profile_create_video_kpi_fail():
    mod = _load_mod()
    rows = [
        {
            "payload_json": '{"create_video_duration_ms": 72000, "camera_slot": "camera_1"}',
            "trigger_to_first_bbox_latency_s": 0.5,
            "finalize_duration_ms": 900.0,
        },
        {
            "payload_json": '{"create_video_duration_ms": 65000, "camera_slot": "camera_2"}',
            "trigger_to_first_bbox_latency_s": 0.6,
            "finalize_duration_ms": 800.0,
        },
    ]
    report = mod.build_profile(
        rows,
        lookback_hours=24,
        first_bbox_warn_s=5.0,
        first_bbox_fail_s=None,
        finalize_warn_ms=5000.0,
        create_video_warn_ms=30000.0,
        create_video_fail_ms=60000.0,
    )
    assert report["kpi"]["create_video_ok"] is False
    assert any("create_video_duration_p95" in f for f in report["failures"])


def test_profile_finalize_tail_dominant_create_video_warning():
    mod = _load_mod()
    rows = [
        {
            "payload_json": (
                '{"finalize_critical_path_ms": 70000, "create_video_duration_ms": 65000, '
                '"persist_duration_ms": 2000, "fusion_duration_ms": 500, "camera_slot": "camera_1"}'
            ),
            "trigger_to_first_bbox_latency_s": 0.5,
            "finalize_duration_ms": 72000.0,
        },
        {
            "payload_json": (
                '{"finalize_critical_path_ms": 68000, "create_video_duration_ms": 62000, '
                '"persist_duration_ms": 1800, "camera_slot": "camera_2"}'
            ),
            "trigger_to_first_bbox_latency_s": 0.6,
            "finalize_duration_ms": 70000.0,
        },
    ]
    report = mod.build_profile(
        rows,
        lookback_hours=24,
        first_bbox_warn_s=5.0,
        first_bbox_fail_s=None,
        finalize_warn_ms=5000.0,
        create_video_warn_ms=30000.0,
        create_video_fail_ms=None,
    )
    assert report["kpi"]["finalize_tail_dominant"] == "create_video"
    assert any("finalize tail dominated by create_video" in w for w in report["warnings"])


def test_profile_excludes_legacy_spectrogram_finalize_from_kpi_warn():
    mod = _load_mod()
    rows = [
        {
            "payload_json": "{}",
            "trigger_to_first_bbox_latency_s": 0.5,
            "finalize_duration_ms": 20000.0,
        },
        {
            "payload_json": '{"create_video_duration_ms": 800, "finalize_critical_path_ms": 900}',
            "trigger_to_first_bbox_latency_s": 0.6,
            "finalize_duration_ms": 4000.0,
        },
    ]
    report = mod.build_profile(
        rows,
        lookback_hours=24,
        first_bbox_warn_s=5.0,
        first_bbox_fail_s=None,
        finalize_warn_ms=5000.0,
        create_video_warn_ms=30000.0,
        create_video_fail_ms=None,
        legacy_spectrogram_finalize_ms=15000.0,
    )
    assert report["legacy_spectrogram_finalize"]["excluded_sessions"] == 1
    assert report["profile"]["finalize_duration_ms_kpi_excl_legacy"]["n"] == 1
    assert not any("finalize_duration_p95" in w for w in report["warnings"])
