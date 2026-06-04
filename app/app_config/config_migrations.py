"""Versioned user_config migrations (SOTA-03 / #494)."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Bump when adding a new migration tranche; persisted in user_config._meta.schema_version.
USER_CONFIG_SCHEMA_VERSION = 2

_META_KEY = "_meta"


def _meta(user_config: dict[str, Any]) -> dict[str, Any]:
    raw = user_config.get(_META_KEY)
    if isinstance(raw, dict):
        return raw
    meta: dict[str, Any] = {}
    user_config[_META_KEY] = meta
    return meta


def current_schema_version(user_config: dict[str, Any]) -> int:
    try:
        return int(_meta(user_config).get("schema_version") or 0)
    except (TypeError, ValueError):
        return 0


def flatten_config_keys(cfg: dict[str, Any], prefix: str = "") -> set[str]:
    """Dot paths for leaf keys (same shape as config-audit)."""
    keys: set[str] = set()
    if not isinstance(cfg, dict):
        return keys
    for key, value in cfg.items():
        if key == _META_KEY:
            continue
        path = f"{prefix}.{key}" if prefix else str(key)
        if isinstance(value, dict):
            keys.update(flatten_config_keys(value, path))
        else:
            keys.add(path)
    return keys


def deprecated_keys_present(user_config: dict[str, Any]) -> list[str]:
    from app_config.deprecated_keys import DEPRECATED_USER_CONFIG_KEYS

    user_keys = flatten_config_keys(user_config)
    return sorted(k for k in DEPRECATED_USER_CONFIG_KEYS if k in user_keys)


def run_user_config_migrations(user_config: dict[str, Any]) -> bool:
    """
    Apply idempotent legacy migrations and bump ``_meta.schema_version``.

    Returns True if user_config was modified (caller should persist).
    """
    if not isinstance(user_config, dict):
        return False

    from app_config.app_config import (
        migrate_legacy_homeassistant_from_weather,
        migrate_legacy_scales_source,
        migrate_legacy_trigger_topics,
        migrate_processor_classifier_best_eu_path,
    )
    from app_config.trigger_config import migrate_legacy_motion_block

    changed = False
    for fn in (
        migrate_legacy_scales_source,
        migrate_legacy_trigger_topics,
        migrate_legacy_homeassistant_from_weather,
        migrate_processor_classifier_best_eu_path,
        migrate_legacy_motion_block,
    ):
        try:
            if fn(user_config):
                changed = True
        except Exception as exc:
            logger.warning("user_config migration %s failed: %s", fn.__name__, exc)

    meta = _meta(user_config)
    version = current_schema_version(user_config)
    if version < 2:
        from app_config.track_first_migrations import migrate_track_first_contract

        try:
            if migrate_track_first_contract(user_config):
                changed = True
        except Exception as exc:
            logger.warning("user_config migration migrate_track_first_contract failed: %s", exc)

    if version < USER_CONFIG_SCHEMA_VERSION:
        meta["schema_version"] = USER_CONFIG_SCHEMA_VERSION
        changed = True
    return changed
