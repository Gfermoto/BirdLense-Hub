"""Bird Directory «regional» scope: eBird region top + BirdNET-heard species."""
from __future__ import annotations

import logging
import time

from app_config.app_config import app_config

from models import Species, VideoSpecies, db
from services.ebird_region_service import (
    _build_region_code,
    ebird_common_to_birdlense_name,
    get_region_top_species,
)

logger = logging.getLogger(__name__)

# Cache eBird top list per (region, api key suffix) to avoid HTTP on every /species hit.
_TOP_CACHE: dict[tuple[str, str], tuple[float, list[str]]] = {}
_TOP_TTL_SEC = 1800.0


def _cached_region_top_common_names(api_key: str, region_code: str) -> list[str]:
    now = time.monotonic()
    key_suffix = api_key[-12:] if len(api_key) >= 12 else api_key
    key = (region_code, key_suffix)
    ent = _TOP_CACHE.get(key)
    if ent is not None and (now - ent[0]) < _TOP_TTL_SEC:
        return ent[1]
    try:
        top = get_region_top_species(api_key, region_code)
    except Exception as e:
        logger.warning('regional scope: eBird top fetch failed: %s', e)
        top = []
    _TOP_CACHE[key] = (now, top)
    return top


def compute_regional_scope_species_ids() -> set[int]:
    """IDs in (eBird regional top-20 mapped to Species.name) ∪ (any BirdNET MQTT detection).

    eBird uses the same region as Migration / region comparison (``ebird.*`` config).
    BirdNET: ``VideoSpecies.detection_provider == 'birdnet_mqtt'``.
    """
    ids: set[int] = set()

    birdnet_rows = (
        db.session.query(VideoSpecies.species_id)
        .filter(VideoSpecies.detection_provider == 'birdnet_mqtt')
        .distinct()
        .all()
    )
    for (sid,) in birdnet_rows:
        if sid is not None:
            ids.add(int(sid))

    api_key = (app_config.get('secrets.ebird_api_key') or '').strip()
    if api_key:
        region_code = _build_region_code()
        top = _cached_region_top_common_names(api_key, region_code)
        for com in top:
            mapped = ebird_common_to_birdlense_name((com or '').strip())
            if not mapped:
                continue
            row = db.session.query(Species.id).filter_by(name=mapped).first()
            if row:
                ids.add(int(row[0]))

    return ids
