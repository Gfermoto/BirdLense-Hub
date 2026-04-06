"""eBird regional top: shared between processor and web (no services.* dependency).

HTTP fetch, in-memory cache, region code from config, species name mapping via app_config.
"""
from __future__ import annotations

import logging
import time
from collections import Counter

import httpx

from app_config.app_config import app_config

logger = logging.getLogger(__name__)

# Маппинг полных названий регионов на коды eBird (единый источник; web re-export в ebird_util)
REGION_NAME_TO_CODE = {
    'moscow oblast': 'MOS',
    'moscow': 'MO',
    'московская область': 'MOS',
    'москва': 'MO',
}

EBIRD_API_BASE = 'https://api.ebird.org/v2'
TOP_N = 20
BACK_DAYS = 30
MAX_OBSERVATIONS = 5000

# Shared cache: Bird Directory, mapping suggestions, processor auto-confidence.
_REGION_TOP_CACHE: dict[tuple[str, str], tuple[float, list[str]]] = {}
_REGION_TOP_TTL_SEC = 1800.0


def _build_region_code() -> str:
    """Build eBird region code from config: country or country-state."""
    country = (app_config.get('ebird.country') or '').strip().upper() or 'US'
    state_raw = (app_config.get('ebird.state') or '').strip()
    if not state_raw:
        return country
    state_lower = state_raw.lower().strip()
    state = REGION_NAME_TO_CODE.get(state_lower) or state_raw.upper()[:3]
    return f'{country}-{state}'


def _fetch_region_observations(api_key: str, region_code: str) -> list[dict]:
    """Fetch recent observations from eBird API. Returns list of obs dicts."""
    url = f'{EBIRD_API_BASE}/data/obs/{region_code}/recent'
    params = {'back': BACK_DAYS, 'maxResults': MAX_OBSERVATIONS}
    headers = {'X-eBirdApiToken': api_key}
    try:
        with httpx.Client(timeout=15.0) as client:
            r = client.get(url, params=params, headers=headers)
            r.raise_for_status()
            return r.json() or []
    except httpx.HTTPStatusError as e:
        txt = e.response.text[:200]
        logger.warning('eBird API error %s: %s', e.response.status_code, txt)
        raise ValueError(f'eBird API: {e.response.status_code}') from e
    except Exception as e:
        logger.warning('eBird fetch failed: %s', e)
        raise


def get_region_top_species(api_key: str, region_code: str) -> list[str]:
    """Get top N species by observation count in region. Returns common names."""
    obs = _fetch_region_observations(api_key, region_code)
    if not obs:
        return []
    counter = Counter()
    for o in obs:
        com = (o.get('comName') or '').strip()
        if com:
            counter[com] += 1
    return [name for name, _ in counter.most_common(TOP_N)]


def get_region_top_species_cached(api_key: str, region_code: str) -> list[str]:
    """Same as get_region_top_species but cached ~30 min per region and key suffix."""
    now = time.monotonic()
    key_suffix = api_key[-12:] if len(api_key) >= 12 else api_key
    key = (region_code, key_suffix)
    ent = _REGION_TOP_CACHE.get(key)
    if ent is not None and (now - ent[0]) < _REGION_TOP_TTL_SEC:
        return ent[1]
    try:
        top = get_region_top_species(api_key, region_code)
    except Exception as e:
        logger.warning('eBird regional top fetch failed: %s', e)
        top = []
    _REGION_TOP_CACHE[key] = (now, top)
    return top


def _ebird_to_birdlense(name: str) -> str:
    """Map eBird common name to BirdLense canonical (ebird + detection species_mapping)."""
    ebird_map = app_config.get('ebird.species_mapping') or {}
    if name in ebird_map:
        return ebird_map[name]
    detection_map = app_config.get('detection.species_mapping') or {}
    return detection_map.get(name, name)


def ebird_common_to_birdlense_name(name: str) -> str:
    """Public alias for species matching (Bird Directory, filters, processor)."""
    return _ebird_to_birdlense(name)
