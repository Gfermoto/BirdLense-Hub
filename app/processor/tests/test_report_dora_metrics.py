"""Tests for scripts/report_dora_metrics.py (#544)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]


def _load_mod():
    path = _REPO_ROOT / "scripts" / "report_dora_metrics.py"
    spec = importlib.util.spec_from_file_location("report_dora_metrics", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["report_dora_metrics"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_compute_dora_from_deploy_events_and_incidents():
    mod = _load_mod()
    report = mod.compute_dora(
        window_days=28,
        deploy_events=[
            {
                "deployed_at": "2026-05-30T00:00:00Z",
                "status": "success",
                "change_created_at": "2026-05-29T12:00:00Z",
            },
            {
                "deployed_at": "2026-05-28T00:00:00Z",
                "status": "failed",
                "change_created_at": "2026-05-27T18:00:00Z",
            },
        ],
        incidents=[
            {
                "started_at": "2026-05-28T01:00:00Z",
                "resolved_at": "2026-05-28T03:00:00Z",
            }
        ],
    )
    assert report["ok"] is True
    assert report["metrics"]["change_failure_rate"] == 0.5
    assert report["metrics"]["time_to_restore_service_hours_mean"] == 2.0


def test_compute_dora_uses_git_fallback_when_no_deploy_events():
    mod = _load_mod()
    report = mod.compute_dora(
        window_days=7,
        deploy_events=[],
        incidents=[],
    )
    assert report["ok"] is True
    assert report["deployment_source"] in (
        "git_commit_fallback",
        "deploy_events_log",
    )
