"""Слияние строк Species: перенос FK и удаление источника."""
from __future__ import annotations

from typing import Any

from models import Species, SpeciesVisit, VideoSpecies, db


def _copy_missing_metadata(source: Species, target: Species) -> None:
    if (
        not (target.description or '').strip()
        and (source.description or '').strip()
    ):
        target.description = source.description
    if not (target.image_url or '').strip() and (source.image_url or '').strip():
        target.image_url = source.image_url
    if (
        not (target.metadata_source or '').strip()
        and (source.metadata_source or '').strip()
    ):
        target.metadata_source = source.metadata_source
    if (
        not (target.metadata_source_url or '').strip()
        and (source.metadata_source_url or '').strip()
    ):
        target.metadata_source_url = source.metadata_source_url
    if not target.metadata_updated_at and source.metadata_updated_at:
        target.metadata_updated_at = source.metadata_updated_at
    if not target.taxon_id and source.taxon_id:
        target.taxon_id = source.taxon_id


def merge_species_into(source_id: int, target_id: int) -> dict[str, Any]:
    """Перенести ссылки с source_id на target_id и удалить Species-источник.

    Без commit; при необходимости flush снаружи.
    """
    if source_id == target_id:
        return {'skipped': True, 'reason': 'same id'}
    source = db.session.get(Species, source_id)
    target = db.session.get(Species, target_id)
    if not source or not target:
        return {
            'error': 'species not found',
            'source_id': source_id,
            'target_id': target_id,
        }

    _copy_missing_metadata(source, target)

    n_vs = VideoSpecies.query.filter_by(species_id=source_id).update(
        {'species_id': target_id}, synchronize_session=False,
    )
    n_sv = SpeciesVisit.query.filter_by(species_id=source_id).update(
        {'species_id': target_id}, synchronize_session=False,
    )
    n_ch = Species.query.filter_by(parent_id=source_id).update(
        {'parent_id': target_id}, synchronize_session=False,
    )
    db.session.delete(source)
    db.session.flush()
    return {
        'source_id': source_id,
        'target_id': target_id,
        'video_species_updated': int(n_vs or 0),
        'species_visits_updated': int(n_sv or 0),
        'children_reparented': int(n_ch or 0),
    }
