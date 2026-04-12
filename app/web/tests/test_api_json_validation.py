"""Схемная валидация JSON для mutating API (#281)."""

from __future__ import annotations


def _open_settings_access(monkeypatch):
    from app_config.app_config import app_config

    gen = app_config.config.setdefault("general", {})
    monkeypatch.setitem(gen, "settings_password", "")
    monkeypatch.setitem(gen, "contributor_password", "")
    monkeypatch.delenv("BIRDLENSE_ENV", raising=False)
    monkeypatch.delenv("FLASK_ENV", raising=False)


def test_parse_request_json_dict_unit():
    from flask import Flask, request
    from services.api_json_validation import parse_request_json_dict

    app = Flask(__name__)
    with app.test_request_context("/x", method="POST", data="{}", content_type="application/json"):
        d, err = parse_request_json_dict(request)
        assert d == {}
        assert err is None

    with app.test_request_context("/x", method="POST", data="[1,2]", content_type="application/json"):
        d, err = parse_request_json_dict(request)
        assert d is None
        assert err["error"]
        assert "_body" in err["fields"]

    with app.test_request_context("/x", method="POST", data="", content_type="application/json"):
        d, err = parse_request_json_dict(request)
        assert d is None
        assert "JSON body required" in err["error"]


def test_birdfood_post_invalid_json_400(client, monkeypatch):
    _open_settings_access(monkeypatch)
    r = client.post(
        "/api/ui/birdfood",
        data="not-json{",
        content_type="application/json",
    )
    assert r.status_code == 400
    j = r.get_json()
    assert j["fields"]["_body"]


def test_birdfood_post_array_body_400(client, monkeypatch):
    _open_settings_access(monkeypatch)
    r = client.post("/api/ui/birdfood", json=[], content_type="application/json")
    assert r.status_code == 400
    assert "object" in r.get_json()["error"].lower()


def test_birdfood_post_name_type_and_active_type(client, monkeypatch):
    _open_settings_access(monkeypatch)
    r = client.post("/api/ui/birdfood", json={"name": 42})
    assert r.status_code == 400
    j = r.get_json()
    assert "name" in j["fields"]

    r2 = client.post("/api/ui/birdfood", json={"name": "ok", "active": "yes"})
    assert r2.status_code == 400
    assert "active" in r2.get_json()["fields"]


def test_purge_storage_requires_json_object(client, monkeypatch):
    from app_config.app_config import app_config

    old_admin = app_config.get("general.settings_password")
    old_contrib = app_config.get("general.contributor_password")
    app_config.set("general.settings_password", "")
    app_config.set("general.contributor_password", "")
    try:
        r = client.post(
            "/api/ui/storage/purge",
            data="[]",
            content_type="application/json",
        )
        assert r.status_code == 400
        assert r.get_json()["fields"]
    finally:
        app_config.set("general.settings_password", old_admin)
        app_config.set("general.contributor_password", old_contrib)


def test_purge_storage_date_must_be_string(client, monkeypatch):
    from app_config.app_config import app_config

    old_admin = app_config.get("general.settings_password")
    old_contrib = app_config.get("general.contributor_password")
    app_config.set("general.settings_password", "")
    app_config.set("general.contributor_password", "")
    try:
        r = client.post("/api/ui/storage/purge", json={"date": 20260326})
        assert r.status_code == 400
        j = r.get_json()
        assert "date" in j["fields"]
    finally:
        app_config.set("general.settings_password", old_admin)
        app_config.set("general.contributor_password", old_contrib)
