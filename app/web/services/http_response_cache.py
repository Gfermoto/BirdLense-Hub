"""Инвалидация процессного TTL-кэша JSON-ответов (UI + processor)."""
from services.cache import cache_delete_prefix

# Префиксы ключей services.cache (см. ui_routes.register_routes)
_RESPONSE_CACHE_PREFIXES = (
    'timeline:',
    'unknowns:',
    'overview:',
    'detection_frames:',
    'species_list:',
    'species_observed:',
    'migration_cal:',
    'component_status:',
    'bird_families:',
    'species_summary:',
    'xeno_canto:',
)


def bust_response_caches() -> None:
    for prefix in _RESPONSE_CACHE_PREFIXES:
        cache_delete_prefix(prefix)
