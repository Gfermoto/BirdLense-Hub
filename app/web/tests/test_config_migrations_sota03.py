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


def test_settings_patch_returns_deprecated_warnings(tmp_path, monkeypatch):
    from app_config.app_config import app_config
    from services.settings_patch_service import apply_settings_patch_from_request

    user_path = tmp_path / "user_config.yaml"
    user_path.write_text(
        yaml.safe_dump({"weather": {"ha_url": "http://legacy"}}),
        encoding="utf-8",
    )
    monkeypatch.setattr(app_config, "user_config_file", str(user_path))
    assert "weather.ha_url" in deprecated_keys_present(app_config.load_raw_user_config_dict())

    payload = apply_settings_patch_from_request(
        {"general": {"app_name": "BirdLense Test"}},
        access_role="admin",
        contributor_tier_configured=False,
    )
    warnings = payload.get("settings_warnings", {}).get("deprecated_keys_present")
    assert warnings
    assert "weather.ha_url" in warnings
