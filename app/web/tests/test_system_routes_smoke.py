"""Lightweight tests for /api/ui/system/* (issue #202)."""


def _patch_general_key(monkeypatch, key: str, value):
    from app_config.app_config import app_config

    gen = app_config.config.setdefault("general", {})
    monkeypatch.setitem(gen, key, value)


def _open_settings_access(monkeypatch):
    monkeypatch.delenv("BIRDLENSE_ENV", raising=False)
    monkeypatch.delenv("FLASK_ENV", raising=False)
    _patch_general_key(monkeypatch, "settings_password", "")
    _patch_general_key(monkeypatch, "contributor_password", "")


def test_system_activity_returns_list(client):
    r = client.get("/api/ui/system/activity")
    assert r.status_code == 200
    assert isinstance(r.json, list)


def test_system_activity_invalid_month_400(client):
    r = client.get("/api/ui/system/activity", query_string={"month": "bad"})
    assert r.status_code == 400


def test_system_metrics_history_shape(client):
    r = client.get("/api/ui/system/metrics/history", query_string={"hours": "1"})
    assert r.status_code == 200
    data = r.json
    assert "samples" in data
    assert isinstance(data["samples"], list)


def test_system_logs_forbidden_when_locked(client, monkeypatch):
    _patch_general_key(monkeypatch, "settings_password", "syslogs-lock")
    _patch_general_key(monkeypatch, "contributor_password", "")
    monkeypatch.delenv("BIRDLENSE_ENV", raising=False)
    monkeypatch.delenv("FLASK_ENV", raising=False)

    r = client.get("/api/ui/system/logs")
    assert r.status_code == 403


def test_system_logs_ok_when_settings_open(client, monkeypatch):
    _open_settings_access(monkeypatch)
    r = client.get("/api/ui/system/logs")
    assert r.status_code == 200
    body = r.json
    assert "lines" in body
    assert isinstance(body["lines"], list)
