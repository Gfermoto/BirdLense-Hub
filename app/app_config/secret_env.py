"""Overlay secrets from environment onto merged config (before runtime use).

Sourced after default + user_config merge. Values in env **replace** YAML for the same keys.
See docs/SECURITY.md and docs/SECRETS_ROTATION.md — issue #278.
"""

from __future__ import annotations

import os
from typing import Any


def _set_nested(d: dict[str, Any], path: str, value: str) -> None:
    keys = path.split(".")
    for k in keys[:-1]:
        d = d.setdefault(k, {})  # type: ignore[assignment]
    d[keys[-1]] = value


# (ENV_VAR, config_path) — only non-empty env wins.
_SECRET_ENV_MAPPINGS: tuple[tuple[str, str], ...] = (
    ("BIRDLENSE_TELEGRAM_BOT_TOKEN", "notifications.telegram_bot_token"),
    ("BIRDLENSE_TELEGRAM_MTPROTO_SECRET", "notifications.telegram_mtproto_secret"),
    ("BIRDLENSE_TELEGRAM_API_HASH", "notifications.telegram_api_hash"),
    ("BIRDLENSE_HA_TOKEN", "homeassistant.token"),
    ("BIRDLENSE_SETTINGS_PASSWORD", "general.settings_password"),
    ("BIRDLENSE_CONTRIBUTOR_PASSWORD", "general.contributor_password"),
    ("BIRDLENSE_MQTT_PASSWORD", "mqtt.password"),
    ("BIRDLENSE_GO2RTC_PASSWORD", "video.go2rtc_password"),
    ("BIRDLENSE_OPENWEATHER_API_KEY", "secrets.openweather_api_key"),
    ("BIRDLENSE_EBIRD_API_KEY", "secrets.ebird_api_key"),
    ("BIRDLENSE_XENO_CANTO_API_KEY", "secrets.xeno_canto_api_key"),
    ("BIRDLENSE_MCP_TOKEN", "mcp.token"),
    ("BIRDLENSE_VAPID_PRIVATE_KEY", "web_push.vapid_private_key"),
    ("BIRDLENSE_REDIS_URL", "performance.redis_url"),
)


def apply_secret_env_overrides(merged: dict[str, Any]) -> None:
    """Mutate ``merged`` in place: set keys from env when variable is non-empty."""
    for env_key, cfg_path in _SECRET_ENV_MAPPINGS:
        raw = os.environ.get(env_key)
        if raw is None:
            continue
        val = str(raw).strip()
        if not val:
            continue
        _set_nested(merged, cfg_path, val)
