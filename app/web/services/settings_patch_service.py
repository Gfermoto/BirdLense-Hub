"""Нормализация и применение PATCH /api/ui/settings (#293)."""
from __future__ import annotations

import copy

from app_config.app_config import app_config
from services.cache import cache_delete_prefix, reset_redis_client
from services.http_response_cache import bust_response_caches


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
    if isinstance(out.get('performance'), dict):
        out['performance'].pop('redis_url_effective_masked', None)

    if 'video' in out and 'cameras' in out['video']:
        cameras = out['video']['cameras'] or []
        out['video']['cameras'] = [
            c for c in cameras
            if isinstance(c, dict) and (c.get('stream_name') or '').strip()
        ]

    if access_role == 'contributor' and contributor_tier_configured:
        out = app_config.strip_contributor_admin_only_updates(out)
    out = app_config.filter_sensitive_placeholders(out)

    if isinstance(out.get('secrets'), dict):
        out['secrets'].pop('zip', None)
    if isinstance(app_config.config.get('secrets'), dict):
        app_config.config['secrets'].pop('zip', None)

    return out


def apply_settings_patch_and_refresh_caches(normalized_updates: dict) -> dict:
    """Смержить в live config, save, сброс кэшей. Возвращает payload для ответа API."""
    app_config.config = app_config.merge_dicts(
        app_config.config, normalized_updates,
    )
    app_config.save()

    bust_response_caches()
    cache_delete_prefix('ebird_region_comparison:')
    reset_redis_client()

    return app_config.prepare_settings_for_api(app_config.config)


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
