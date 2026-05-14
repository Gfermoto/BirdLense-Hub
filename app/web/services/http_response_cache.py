"""Инвалидация TTL-кэша JSON-ответов (UI + processor + system)."""

from services.cache import cache_delete_prefix

# Префиксы ключей services.cache (основной UI + справочники)
_RESPONSE_CACHE_PREFIXES = (
    "timeline:",
    "unknowns:",
    "overview:",
    "detection_frames:",
    "species_list:",
    "species_summary:",
    "species_observed:",
    "species_track_regen:",
    "migration_cal:",
    "component_status:",
    "bird_families:",
    "species_summary:",
    "xeno_canto:",
)

# Тяжёлые system/storage (диск, графики) — отдельная инвалидация
_SYSTEM_RESPONSE_PREFIXES = (
    "storage_stats:",
    "system_metrics:",
    "system_visitors:",
    "system_metrics_hist:",  # legacy typo key
    "system_metrics_history:",
    "system_activity:",
)


def bust_response_caches() -> None:
    """Сбросить TTL-кэш тяжёлых UI-ответов (таймлайн, виды, unknowns, …)."""
    for prefix in _RESPONSE_CACHE_PREFIXES:
        cache_delete_prefix(prefix)


def bust_system_response_caches() -> None:
    """Сбросить кэш system-виджетов: диск, метрики, посетители, активность."""
    for prefix in _SYSTEM_RESPONSE_PREFIXES:
        cache_delete_prefix(prefix)


def bust_all_api_caches() -> None:
    """Полный сброс кэшей ответов (например после крупного обслуживания)."""
    bust_response_caches()
    bust_system_response_caches()
