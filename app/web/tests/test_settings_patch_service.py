"""Юнит-тесты services.settings_patch_service (#293)."""

import pytest


@pytest.fixture
def _noop_caches(monkeypatch):
    monkeypatch.setattr(
        "services.settings_patch_service.bust_response_caches",
        lambda: None,
    )
    monkeypatch.setattr(
        "services.settings_patch_service.cache_delete_prefix",
        lambda *_a, **_k: None,
    )
    monkeypatch.setattr(
        "services.settings_patch_service.reset_redis_client",
        lambda: None,
    )


def test_normalize_drops_cameras_without_stream_name(monkeypatch):
    from app_config.app_config import app_config
    from services.settings_patch_service import normalize_settings_patch_updates

    monkeypatch.setattr(
        app_config,
        "strip_contributor_admin_only_updates",
        lambda u: u,
    )
    monkeypatch.setattr(
        app_config,
        "filter_sensitive_placeholders",
        lambda u: u,
    )
    app_config.config.setdefault("secrets", {})["zip"] = "dropme"
    updates = {
        "video": {
            "cameras": [
                {"stream_name": "ok"},
                {"stream_name": ""},
                {"foo": 1},
            ],
        },
    }
    out = normalize_settings_patch_updates(
        updates,
        access_role="admin",
        contributor_tier_configured=False,
    )
    assert len(out["video"]["cameras"]) == 1
    assert out["video"]["cameras"][0]["stream_name"] == "ok"
    assert "zip" not in (app_config.config.get("secrets") or {})


def test_normalize_contributor_calls_strip_when_tier(monkeypatch):
    from app_config.app_config import app_config
    from services.settings_patch_service import normalize_settings_patch_updates

    called = {"n": 0}

    def strip(u):
        called["n"] += 1
        return {"stripped": True}

    monkeypatch.setattr(app_config, "strip_contributor_admin_only_updates", strip)
    monkeypatch.setattr(
        app_config,
        "filter_sensitive_placeholders",
        lambda u: u,
    )
    out = normalize_settings_patch_updates(
        {"general": {"x": 1}},
        access_role="contributor",
        contributor_tier_configured=True,
    )
    assert called["n"] == 1
    assert out == {"stripped": True}


def test_normalize_contributor_skips_strip_without_tier(monkeypatch):
    from app_config.app_config import app_config
    from services.settings_patch_service import normalize_settings_patch_updates

    def should_not_strip(_u):
        pytest.fail("strip should not run")

    monkeypatch.setattr(
        app_config,
        "strip_contributor_admin_only_updates",
        should_not_strip,
    )
    monkeypatch.setattr(
        app_config,
        "filter_sensitive_placeholders",
        lambda u: u,
    )
    out = normalize_settings_patch_updates(
        {"general": {"donate_url": "https://example.test"}},
        access_role="contributor",
        contributor_tier_configured=False,
    )
    assert out["general"]["donate_url"] == "https://example.test"


def test_strip_contributor_admin_only_removes_session_idle_minutes():
    from app_config.app_config import app_config

    updates = {
        "general": {
            "session_idle_minutes": 999,
            "donate_url": "https://example.test/strip-idle",
        },
    }
    out = app_config.strip_contributor_admin_only_updates(updates)
    assert "session_idle_minutes" not in out.get("general", {})
    assert out["general"]["donate_url"] == "https://example.test/strip-idle"


def test_filter_sensitive_json_null_removes_secret_from_patch():
    """JSON null для секрета не должен попадать в merge (иначе затирает хранимое значение)."""
    from app_config.app_config import app_config

    out = app_config.filter_sensitive_placeholders(
        {
            "general": {
                "contributor_password": None,
                "donate_url": "https://example.test/null-secret",
            },
        },
    )
    gen = out.get("general") or {}
    assert "contributor_password" not in gen
    assert gen.get("donate_url") == "https://example.test/null-secret"


def test_apply_merge_updates_donate_url(app, monkeypatch, _noop_caches):
    from app_config.app_config import app_config
    from services.settings_patch_service import apply_settings_patch_from_request

    monkeypatch.setattr(app_config, "save", lambda: None)
    token = f"https://svc-patch-{id(app)}.example/donate"
    old = app_config.get("general.donate_url")
    try:
        apply_settings_patch_from_request(
            {"general": {"donate_url": token}},
            access_role="admin",
            contributor_tier_configured=False,
        )
        assert app_config.get("general.donate_url") == token
    finally:
        app_config.set("general.donate_url", old)
