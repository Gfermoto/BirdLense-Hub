"""Таймаут неактивности сессии (#280)."""

from __future__ import annotations

import time


def test_session_idle_expires_unlocked_session(client, monkeypatch):
    from app_config.app_config import app_config

    gen = app_config.config.setdefault("general", {})
    monkeypatch.setitem(gen, "settings_password", "idle-test-pw")
    monkeypatch.setitem(gen, "contributor_password", "")
    monkeypatch.setitem(gen, "session_idle_minutes", 1)
    monkeypatch.delenv("BIRDLENSE_ENV", raising=False)
    monkeypatch.delenv("FLASK_ENV", raising=False)

    clock = {"t": 1_000_000.0}
    monkeypatch.setattr(time, "time", lambda: clock["t"])

    from services.session_idle_service import SESSION_ACTIVITY_KEY

    with client.session_transaction() as sess:
        sess["access_role"] = "admin"
        sess["settings_unlocked"] = True
        sess[SESSION_ACTIVITY_KEY] = clock["t"]

    assert client.get("/api/ui/settings/check-access").get_json()["unlocked"] is True

    clock["t"] += 120.0
    assert client.get("/api/ui/settings/check-access").get_json()["unlocked"] is False


def test_session_idle_disabled_when_zero(client, monkeypatch):
    from app_config.app_config import app_config

    gen = app_config.config.setdefault("general", {})
    monkeypatch.setitem(gen, "settings_password", "idle-test-pw2")
    monkeypatch.setitem(gen, "contributor_password", "")
    monkeypatch.setitem(gen, "session_idle_minutes", 0)
    monkeypatch.delenv("BIRDLENSE_ENV", raising=False)
    monkeypatch.delenv("FLASK_ENV", raising=False)

    clock = {"t": 2_000_000.0}
    monkeypatch.setattr(time, "time", lambda: clock["t"])

    from services.session_idle_service import SESSION_ACTIVITY_KEY

    with client.session_transaction() as sess:
        sess["access_role"] = "admin"
        sess["settings_unlocked"] = True
        sess[SESSION_ACTIVITY_KEY] = clock["t"]

    clock["t"] += 3600.0
    assert client.get("/api/ui/settings/check-access").get_json()["unlocked"] is True
