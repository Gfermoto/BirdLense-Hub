"""GET /api/ui/system/diagnostics/backpressure (#510)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app_config.app_config import app_config


@pytest.fixture(autouse=True)
def _open_settings_access(monkeypatch):
    monkeypatch.delenv("BIRDLENSE_ENV", raising=False)
    monkeypatch.delenv("FLASK_ENV", raising=False)
    old_admin = app_config.get("general.settings_password")
    old_contrib = app_config.get("general.contributor_password")
    app_config.set("general.settings_password", "")
    app_config.set("general.contributor_password", "")
    try:
        yield
    finally:
        app_config.set("general.settings_password", old_admin)
        app_config.set("general.contributor_password", old_contrib)


def test_backpressure_endpoint_reads_snapshot(client, app, tmp_path, monkeypatch):
    from services import system_diagnostics_service as sds

    diag = tmp_path / "diagnostics"
    diag.mkdir()
    snap = {
        "generated_at": "2026-05-28T12:00:00Z",
        "gauges": {
            "finalize_queue_depth": 1,
            "classification_queue_depth": 2,
            "classification_queue_maxsize": 8,
        },
        "counters": {"classification_task_drops_total": 3},
    }
    (diag / "processor_runtime_stats.json").write_text(
        json.dumps(snap),
        encoding="utf-8",
    )
    monkeypatch.setattr(sds.data_paths, "data_dir", lambda: str(tmp_path))

    r = client.get("/api/ui/system/diagnostics/backpressure")
    assert r.status_code == 200
    body = r.get_json()
    assert body.get("gauges", {}).get("finalize_queue_depth") == 1
    assert body.get("counters", {}).get("classification_task_drops_total") == 3
