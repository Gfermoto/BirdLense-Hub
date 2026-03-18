"""eBird API: regional species for comparison with user's feeder."""
import logging
from collections import Counter

import httpx

from app_config.app_config import app_config

from services.ebird_util import REGION_NAME_TO_CODE, common_name_from_species

logger = logging.getLogger(__name__)

EBIRD_API_BASE = 'https://api.ebird.org/v2'
TOP_N = 20
BACK_DAYS = 30
MAX_OBSERVATIONS = 5000


def _build_region_code() -> str:
    """Build eBird region code from config: country or country-state."""
    country = (app_config.get("ebird.country") or "").strip().upper() or "US"
    state_raw = (app_config.get("ebird.state") or "").strip()
    if not state_raw:
        return country
    # Поддержка полных названий: "Moscow Oblast" -> MOS
    state_lower = state_raw.lower().strip()
    state = REGION_NAME_TO_CODE.get(state_lower) or state_raw.upper()[:3]
    return f"{country}-{state}"


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


def _ebird_to_birdlense(name: str) -> str:
    """Map eBird common name to BirdLense canonical (Gray->Grey, etc.)."""
    mapping = app_config.get('ebird.species_mapping') or {}
    return mapping.get(name, name)


def get_region_comparison(user_species_names: list[str]) -> dict | None:
    """Compare user's species with region top.

    Returns dict with regionCode, userCount, regionTopCount, matchCount,
    matchedSpecies, regionTop. Or None if API key missing or error.
    Uses ebird.species_mapping to align eBird names (Gray) with BirdLense (Grey).
    """
    api_key = (app_config.get('secrets.ebird_api_key') or '').strip()
    if not api_key:
        return None

    region_code = _build_region_code()
    user_common = [common_name_from_species(n) for n in user_species_names if n]
    user_common = [n for n in user_common if n and n != 'Bird']
    user_set = {n.lower() for n in user_common}

    try:
        region_top = get_region_top_species(api_key, region_code)
    except Exception:
        return None

    if not region_top:
        return {
            'regionCode': region_code,
            'userCount': len(user_set),
            'regionTopCount': 0,
            'matchCount': 0,
            'matchedSpecies': [],
            'regionTop': [],
        }

    # eBird names -> BirdLense canonical для сопоставления
    region_mapped = [_ebird_to_birdlense(n) for n in region_top]
    region_set = {n.lower() for n in region_mapped}
    matched = [n for n in user_common if n.lower() in region_set]

    return {
        'regionCode': region_code,
        'userCount': len(user_set),
        'regionTopCount': len(region_top),
        'matchCount': len(matched),
        'matchedSpecies': matched,
        'regionTop': region_mapped,  # показываем BirdLense-имена
    }
