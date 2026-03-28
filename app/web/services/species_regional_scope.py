"""Bird Directory «regional» scope: eBird region top + BirdNET-heard species."""
from __future__ import annotations

from app_config.app_config import app_config

from models import Species, VideoSpecies, db
from services.ebird_region_service import (
    _build_region_code,
    ebird_common_to_birdlense_name,
    get_region_top_species_cached,
)


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
        top = get_region_top_species_cached(api_key, region_code)
        for com in top:
            mapped = ebird_common_to_birdlense_name((com or '').strip())
            if not mapped:
                continue
            row = db.session.query(Species.id).filter_by(name=mapped).first()
            if row:
                ids.add(int(row[0]))

    return ids
