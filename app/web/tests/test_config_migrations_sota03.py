"""SOTA-03: versioned user_config migrations and PATCH warnings."""

from __future__ import annotations

import yaml

from app_config.config_migrations import (
    USER_CONFIG_SCHEMA_VERSION,
    current_schema_version,
    deprecated_keys_present,
    run_user_config_migrations,
)


def test_run_user_config_migrations_sets_schema_version():
    user = {"weather": {"ha_url": "http://ha", "ha_token": "t"}}
    assert run_user_config_migrations(user) is True
    assert current_schema_version(user) == USER_CONFIG_SCHEMA_VERSION
    assert "ha_url" not in (user.get("weather") or {})


def test_deprecated_keys_present_detects_legacy_weather():
    user = {"weather": {"ha_url": "http://x"}}
    keys = deprecated_keys_present(user)
    assert "weather.ha_url" in keys


def test_settings_patch_returns_deprecated_warnings(client, tmp_path, monkeypatch):
    from app_config import app_config as ac_mod

    user_path = tmp_path / "user_config.yaml"
    user_path.write_text(
        yaml.safe_dump({"weather": {"ha_url": "http://legacy"}}),
        encoding="utf-8",
    )
    monkeypatch.setattr(ac_mod.app_config, "user_config_file", str(user_path))

    with client.session_transaction() as sess:
        sess["access_role"] = "admin"

    r = client.patch(
        "/api/ui/settings",
        json={"general": {"app_name": "BirdLense Test"}},
    )
    assert r.status_code == 200
    body = r.get_json()
    assert body.get("_settings_warnings", {}).get("deprecated_keys_present")
