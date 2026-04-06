"""eBird API: regional species for comparison with user's feeder (web cache layer)."""
import hashlib
import logging

from app_config.app_config import app_config

from ebird_region_core import (
    _REGION_TOP_CACHE,
    _build_region_code,
    ebird_common_to_birdlense_name,
    get_region_top_species,
    get_region_top_species_cached,
)
from services.cache import cache_get, cache_set
from services.ebird_util import common_name_from_species

logger = logging.getLogger(__name__)

# Backward compat: tests clear ebird_region_service._REGION_TOP_CACHE
# (same dict as ebird_region_core._REGION_TOP_CACHE)


def get_region_comparison(user_species_names: list[str]) -> dict | None:
    """Compare user's species with region top.

    Returns dict with regionCode, userCount, regionTopCount, matchCount,
    matchedSpecies, regionTop. Or None if API key missing or error.
    Uses detection.species_mapping to align eBird names (Gray) with BirdLense (Grey).
    Result cached 4 hours per (api_key_suffix, region_code, sorted user names).
    """
    api_key = (app_config.get('secrets.ebird_api_key') or '').strip()
    if not api_key:
        return None

    region_code = _build_region_code()
    sorted_names = sorted(n for n in user_species_names if n)
    names_hash = hashlib.sha256('|'.join(sorted_names).encode()).hexdigest()[:32]
    key_suffix = api_key[-12:] if len(api_key) >= 12 else api_key
    cache_key = f'ebird_region_comparison:{key_suffix}:{region_code}:{names_hash}'

    found, cached_result = cache_get(cache_key)
    if found:
        return cached_result

    user_common = [common_name_from_species(n) for n in user_species_names if n]
    user_common = [n for n in user_common if n and n != 'Bird']
    user_set = {n.lower() for n in user_common}

    try:
        region_top = get_region_top_species_cached(api_key, region_code)
    except Exception:
        return None

    if not region_top:
        result = {
            'regionCode': region_code,
            'userCount': len(user_set),
            'regionTopCount': 0,
            'matchCount': 0,
            'matchedSpecies': [],
            'regionTop': [],
        }
        cache_set(cache_key, result, ttl_seconds=14400)
        return result

    region_mapped = [ebird_common_to_birdlense_name(n) for n in region_top]
    region_set = {n.lower() for n in region_mapped}
    matched = [n for n in user_common if n.lower() in region_set]

    result = {
        'regionCode': region_code,
        'userCount': len(user_set),
        'regionTopCount': len(region_top),
        'matchCount': len(matched),
        'matchedSpecies': matched,
        'regionTop': region_mapped,
    }
    cache_set(cache_key, result, ttl_seconds=14400)
    return result


__all__ = [
    '_REGION_TOP_CACHE',
    '_build_region_code',
    'ebird_common_to_birdlense_name',
    'get_region_top_species',
    'get_region_top_species_cached',
    'get_region_comparison',
]
