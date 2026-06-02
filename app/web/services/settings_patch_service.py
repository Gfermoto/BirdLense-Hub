"""Нормализация и применение PATCH /api/ui/settings (#293)."""

from __future__ import annotations

import copy

from app_config.app_config import (
    AppConfig,
    app_config,
    validate_merged_config,
    validate_merged_config_semantics,
)
from app_config.config_schema import validate_merged_config_pydantic
from services.cache import cache_delete_prefix, reset_redis_client
from services.ui_password_service import hash_password_fields_in_updates
from services.http_response_cache import bust_response_caches


class SettingsPatchValidationError(ValueError):
    """Settings PATCH would produce an invalid merged config."""

    def __init__(self, issues: list[str]):
        super().__init__("Invalid settings patch")
        self.issues = issues


def normalize_settings_patch_updates(
    updates: dict,
    *,
    access_role: str | None,
    contributor_tier_configured: bool,
) -> dict:
    """
    Подготовить тело PATCH: убрать read-only поля, отфильтровать камеры,
    ограничить оператора, placeholders, secrets.zip.
    """
    out = copy.deepcopy(updates)
    from app_config.trigger_config import fold_motion_settings_patch_into_triggers

    fold_motion_settings_patch_into_triggers(out)
    if isinstance(out.get("performance"), dict):
        out["performance"].pop("redis_url_effective_masked", None)

    if "video" in out and "cameras" in out["video"]:
        cameras = out["video"]["cameras"] or []
        out["video"]["cameras"] = [c for c in cameras if isinstance(c, dict) and (c.get("stream_name") or "").strip()]

    if access_role == "contributor" and contributor_tier_configured:
        out = app_config.strip_contributor_admin_only_updates(out)
    out = app_config.filter_sensitive_placeholders(out)

    if isinstance(out.get("secrets"), dict):
        out["secrets"].pop("zip", None)
    if isinstance(app_config.config.get("secrets"), dict):
        app_config.config["secrets"].pop("zip", None)

    return out


def validate_settings_patch_updates(normalized_updates: dict) -> None:
    """Reject PATCH payloads that would corrupt merged config shape or break semantics."""
    candidate = app_config.merge_dicts(app_config.config, normalized_updates)
    folded = copy.deepcopy(candidate)
    from app_config.trigger_config import fold_legacy_motion_out_of_merged_config

    fold_legacy_motion_out_of_merged_config(folded)
    app_config._enforce_confidence_floors(folded)
    AppConfig._cleanup_legacy_processor_keys(folded)
    issues = validate_merged_config(folded)
    issues.extend(validate_merged_config_semantics(folded))
    issues.extend(validate_merged_config_pydantic(folded))
    if issues:
        raise SettingsPatchValidationError(issues)


def _load_raw_user_config_dict() -> dict:
    import os
    import yaml

    path = app_config.user_config_file
    if not os.path.isfile(path):
        return {}
    try:
        with open(path, encoding="utf-8") as fh:
            return yaml.safe_load(fh) or {}
    except yaml.YAMLError:
        return {}


def apply_settings_patch_and_refresh_caches(normalized_updates: dict) -> dict:
    """Смержить в live config, save, сброс кэшей. Возвращает payload для ответа API."""
    from app_config.config_migrations import deprecated_keys_present

    validate_settings_patch_updates(normalized_updates)
    deprecated = deprecated_keys_present(_load_raw_user_config_dict())
    to_merge = hash_password_fields_in_updates(normalized_updates)
    app_config.config = app_config.merge_dicts(
        app_config.config,
        to_merge,
    )
    from app_config.trigger_config import fold_legacy_motion_out_of_merged_config

    fold_legacy_motion_out_of_merged_config(app_config.config)
    app_config.save()

    bust_response_caches()
    cache_delete_prefix("ebird_region_comparison:")
    reset_redis_client()

    payload = app_config.prepare_settings_for_api(app_config.config)
    if deprecated:
        payload["settings_warnings"] = {"deprecated_keys_present": deprecated}
    return payload


def apply_settings_patch_from_request(
    updates: dict,
    *,
    access_role: str | None,
    contributor_tier_configured: bool,
) -> dict:
    """Нормализация + merge/save/cache — один вызов из роута."""
    normalized = normalize_settings_patch_updates(
        updates,
        access_role=access_role,
        contributor_tier_configured=contributor_tier_configured,
    )
    return apply_settings_patch_and_refresh_caches(normalized)
