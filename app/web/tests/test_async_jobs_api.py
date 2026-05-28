"""Unified /api/ui/jobs contract (#513)."""

from __future__ import annotations

import pytest

import routes.ui_system_jobs_state as job_state
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


def test_list_jobs(client):
    r = client.get("/api/ui/jobs")
    assert r.status_code == 200
    body = r.get_json()
    assert "jobs" in body
    ids = {j["id"] for j in body["jobs"]}
    assert "catalog_repair" in ids
    assert "track_regen" in ids


def test_get_catalog_repair_job_includes_coverage(client):
    r = client.get("/api/ui/jobs/catalog_repair")
    assert r.status_code == 200
    body = r.get_json()
    assert body["type"] == "catalog_repair"
    assert "status" in body


def test_post_unknown_job_type(client):
    r = client.post("/api/ui/jobs", json={"type": "not_a_job"})
    assert r.status_code == 400


def test_cancel_track_regen_when_idle(client):
    job_state._regenerate_tracks_status = {
        "status": "idle",
        "result": None,
        "error": None,
        "progress": None,
    }
    job_state._regenerate_tracks_cancel_requested = False
    r = client.delete("/api/ui/jobs/track_regen")
    assert r.status_code == 409
