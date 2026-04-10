"""Удаление синтетических legacy Unknown из старого disk-import (#265)."""
from __future__ import annotations

from models import Species, SpeciesVisit, VideoSpecies, db

IMPORT_SPECIES_NAME = 'Unknown'


def is_legacy_import_placeholder(vs: VideoSpecies) -> bool:
    species = getattr(vs, 'species', None)
    species_name = getattr(species, 'name', None)
    frames = (getattr(vs, 'frames', None) or '').strip()
    return (
        getattr(vs, 'detection_provider', None) == 'legacy'
        and species_name == IMPORT_SPECIES_NAME
        and float(getattr(vs, 'confidence', 0) or 0) <= 0
        and getattr(vs, 'source', None) == 'video'
        and not bool(getattr(vs, 'manually_corrected', False))
        and getattr(vs, 'track_id', None) is None
        and not frames
        and float(getattr(vs, 'start_time', 0) or 0) == 0
        and float(getattr(vs, 'end_time', 0) or 0) == 30
    )


def cleanup_legacy_import_placeholders() -> tuple[int, int]:
    """Удалить placeholder-строки; вернуть (удалено VS, удалено визитов)."""
    rows = (
        db.session.query(VideoSpecies)
        .join(Species)
        .filter(
            VideoSpecies.detection_provider == 'legacy',
            Species.name == IMPORT_SPECIES_NAME,
        )
        .all()
    )
    placeholder_rows = [vs for vs in rows if is_legacy_import_placeholder(vs)]
    if not placeholder_rows:
        return 0, 0

    visit_ids = {vs.species_visit_id for vs in placeholder_rows if vs.species_visit_id}
    for vs in placeholder_rows:
        db.session.delete(vs)
    db.session.flush()

    cleaned_visits = 0
    for visit_id in visit_ids:
        other = VideoSpecies.query.filter(
            VideoSpecies.species_visit_id == visit_id,
        ).first()
        if other:
            continue
        visit = db.session.get(SpeciesVisit, visit_id)
        if visit:
            db.session.delete(visit)
            cleaned_visits += 1

    return len(placeholder_rows), cleaned_visits
