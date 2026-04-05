"""Список видов, observed, track-regen, bird_families (#198)."""

from flask import request
from sqlalchemy import distinct, func

from models import Species, SpeciesVisit, VideoSpecies, db
from services.cache import cache_get, cache_set
from services.species_data_quality_service import species_ids_to_exclude_from_bird_catalog
from services.species_regional_scope import compute_regional_scope_species_ids

from routes.ui_route_constants import (
    CACHE_BIRD_FAMILIES_SEC,
    CACHE_SPECIES_LIST_SEC,
    CACHE_SPECIES_OBSERVED_SEC,
    CACHE_SPECIES_TRACK_REGEN_SEC,
)


def register_ui_species_catalog_routes(app):
    @app.route('/api/ui/species', methods=['GET'])
    def get_all_species():
        exclude_suspects = request.args.get(
            'exclude_suspects', '').strip().lower() in ('1', 'true', 'yes')
        cache_key = f'species_list:v3:ex{1 if exclude_suspects else 0}'
        hit, scached = cache_get(cache_key)
        if hit:
            return scached
        query = db.session.query(
            Species,
            func.coalesce(func.sum(SpeciesVisit.max_simultaneous),
                          0).label('count')
        ).outerjoin(SpeciesVisit)

        species_list = query.group_by(
            Species.id).order_by(Species.name.asc()).all()

        if exclude_suspects:
            bad_ids = species_ids_to_exclude_from_bird_catalog(db.session)
            species_list = [s for s in species_list if s.Species.id not in bad_ids]

        regional_scope_ids = compute_regional_scope_species_ids()

        result = [
            {
                'id': species.Species.id,
                'name': species.Species.name,
                'parent_id': species.Species.parent_id,
                'created_at': species.Species.created_at.isoformat(),
                'image_url': species.Species.image_url,
                'description': species.Species.description,
                'metadata_source': species.Species.metadata_source,
                'metadata_source_url': species.Species.metadata_source_url,
                'active': species.Species.active,
                'regional_scope': species.Species.id in regional_scope_ids,
                'count': species.count,
            }
            for species in species_list
        ]
        cache_set(cache_key, result, CACHE_SPECIES_LIST_SEC)
        return result

    @app.route('/api/ui/species/observed', methods=['GET'])
    def get_observed_species():
        hit, oc = cache_get('species_observed:v1')
        if hit:
            return oc
        subq = db.session.query(
            SpeciesVisit.species_id,
            func.coalesce(func.sum(SpeciesVisit.max_simultaneous), 0).label('count')
        ).group_by(SpeciesVisit.species_id).having(
            func.coalesce(func.sum(SpeciesVisit.max_simultaneous), 0) > 0
        ).subquery()
        rows = db.session.query(Species, subq.c.count).join(
            subq, Species.id == subq.c.species_id
        ).order_by(Species.name.asc()).all()
        out = [{'id': s.id, 'name': s.name, 'count': int(cnt)} for s, cnt in rows]
        cache_set('species_observed:v1', out, CACHE_SPECIES_OBSERVED_SEC)
        return out

    @app.route('/api/ui/species/track-regen-options', methods=['GET'])
    def get_species_track_regen_options():
        hit, oc = cache_get('species_track_regen:v1')
        if hit:
            return oc
        subq = (
            db.session.query(
                VideoSpecies.species_id,
                func.count(distinct(VideoSpecies.video_id)).label('video_count'),
            )
            .group_by(VideoSpecies.species_id)
            .subquery()
        )
        rows = (
            db.session.query(Species, subq.c.video_count)
            .join(subq, Species.id == subq.c.species_id)
            .order_by(Species.name.asc())
            .all()
        )
        out = [{'id': s.id, 'name': s.name, 'count': int(vc)} for s, vc in rows]
        cache_set('species_track_regen:v1', out, CACHE_SPECIES_TRACK_REGEN_SEC)
        return out

    @app.route('/api/ui/bird_families', methods=['GET'])
    def get_bird_families():
        hit, fc = cache_get('bird_families:v1')
        if hit:
            return fc
        try:
            birds_category = Species.query.filter_by(name="Birds").first()
            if not birds_category:
                return {'error': 'Birds category not found'}, 404

            families = Species.query.filter_by(
                parent_id=birds_category.id).all()
            payload = [{
                'id': family.id,
                'name': family.name,
            } for family in families]
            cache_set('bird_families:v1', payload, CACHE_BIRD_FAMILIES_SEC)
            return payload

        except Exception as e:
            app.logger.error(f"Error fetching bird families: {str(e)}")
            return {"error": "Failed to fetch bird families"}, 500
