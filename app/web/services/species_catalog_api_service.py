"""Данные для GET /api/ui/species*, bird_families (#293)."""
from __future__ import annotations

import logging

from sqlalchemy import distinct, func

from models import Species, SpeciesVisit, VideoSpecies
from services.species_data_quality_service import species_ids_to_exclude_from_bird_catalog
from services.species_regional_scope import compute_regional_scope_species_ids

logger = logging.getLogger(__name__)


def fetch_species_catalog_list(session, *, exclude_suspects: bool) -> list[dict]:
    query = (
        session.query(
            Species,
            func.coalesce(func.sum(SpeciesVisit.max_simultaneous), 0).label('count'),
        )
        .outerjoin(SpeciesVisit)
        .group_by(Species.id)
        .order_by(Species.name.asc())
    )
    species_list = query.all()
    if exclude_suspects:
        bad_ids = species_ids_to_exclude_from_bird_catalog(session)
        species_list = [s for s in species_list if s.Species.id not in bad_ids]
    regional_scope_ids = compute_regional_scope_species_ids()
    return [
        {
            'id': row.Species.id,
            'name': row.Species.name,
            'parent_id': row.Species.parent_id,
            'created_at': row.Species.created_at.isoformat(),
            'image_url': row.Species.image_url,
            'description': row.Species.description,
            'metadata_source': row.Species.metadata_source,
            'metadata_source_url': row.Species.metadata_source_url,
            'active': row.Species.active,
            'regional_scope': row.Species.id in regional_scope_ids,
            'count': row.count,
        }
        for row in species_list
    ]


def fetch_observed_species_list(session) -> list[dict]:
    subq = (
        session.query(
            SpeciesVisit.species_id,
            func.coalesce(func.sum(SpeciesVisit.max_simultaneous), 0).label('count'),
        )
        .group_by(SpeciesVisit.species_id)
        .having(func.coalesce(func.sum(SpeciesVisit.max_simultaneous), 0) > 0)
        .subquery()
    )
    rows = (
        session.query(Species, subq.c.count)
        .join(subq, Species.id == subq.c.species_id)
        .order_by(Species.name.asc())
        .all()
    )
    return [{'id': s.id, 'name': s.name, 'count': int(cnt)} for s, cnt in rows]


def fetch_track_regen_species_options(session) -> list[dict]:
    subq = (
        session.query(
            VideoSpecies.species_id,
            func.count(distinct(VideoSpecies.video_id)).label('video_count'),
        )
        .group_by(VideoSpecies.species_id)
        .subquery()
    )
    rows = (
        session.query(Species, subq.c.video_count)
        .join(subq, Species.id == subq.c.species_id)
        .order_by(Species.name.asc())
        .all()
    )
    return [{'id': s.id, 'name': s.name, 'count': int(vc)} for s, vc in rows]


def fetch_bird_families_list(session) -> list[dict] | None:
    """Список семейств под «Birds» или None, если категория не найдена."""
    birds_category = session.query(Species).filter_by(name='Birds').first()
    if not birds_category:
        return None
    families = session.query(Species).filter_by(parent_id=birds_category.id).all()
    return [{'id': family.id, 'name': family.name} for family in families]


def fetch_bird_families_list_safe(session) -> tuple[list[dict] | None, str | None]:
    """(payload, None) или (None, error_message) при неожиданной ошибке БД."""
    try:
        return fetch_bird_families_list(session), None
    except Exception:
        logger.exception('Error fetching bird families')
        return None, 'Failed to fetch bird families'
