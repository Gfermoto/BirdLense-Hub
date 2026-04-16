"""POST /api/ui/feed/scale-tare: contributor может тару (не только admin/settings_check)."""

from __future__ import annotations

import pytest

from app_config.app_config import app_config


@pytest.fixture
def dual_password(monkeypatch):
    old_a = app_config.get("general.settings_password")
    old_c = app_config.get("general.contributor_password")
    app_config.set("general.settings_password", "test-admin-feed-scale")
    app_config.set("general.contributor_password", "test-contrib-feed-scale")
    yield
    app_config.set("general.settings_password", old_a)
    app_config.set("general.contributor_password", old_c)


def test_feed_scale_tare_403_without_session(client, dual_password, monkeypatch):
    monkeypatch.setattr(
        "services.feeder_scale.scale_tare_available",
        lambda: True,
    )
    monkeypatch.setattr(
        "services.feeder_scale.trigger_scale_tare",
        lambda: (True, "ok"),
    )
    r = client.post("/api/ui/feed/scale-tare")
    assert r.status_code == 403


def test_feed_scale_tare_200_contributor_session(client, dual_password, monkeypatch):
    monkeypatch.setattr(
        "services.feeder_scale.scale_tare_available",
        lambda: True,
    )
    monkeypatch.setattr(
        "services.feeder_scale.trigger_scale_tare",
        lambda: (True, "ok"),
    )
    with client.session_transaction() as sess:
        sess["access_role"] = "contributor"
        sess["settings_unlocked"] = True
    r = client.post("/api/ui/feed/scale-tare")
    assert r.status_code == 200
    assert r.json.get("ok") is True
