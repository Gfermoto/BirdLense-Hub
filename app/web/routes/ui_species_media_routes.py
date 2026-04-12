"""Xeno-canto, summary, прокси species-image, tuning targets (#198)."""

from urllib.parse import quote

from flask import Response, request

from auth import contributor_or_admin_access
from models import Species, db
from services.cache import cache_delete, cache_delete_prefix, cache_get, cache_set
from services.http_response_cache import bust_response_caches
from services.species_image_proxy_service import run_species_image_proxy
from services.species_summary_service import build_species_summary
from services.species_tuning_targets_service import (
    apply_tuning_target_toggle,
    build_tuning_targets_payload,
)
from services.xeno_canto_service import fetch_recordings, _search_term_from_species_name
from species_metadata import refresh_species_metadata_from_sources
from util import settings_check_access


def register_ui_species_media_routes(app):
    @app.route("/api/ui/species/<int:species_id>/xeno-canto", methods=["GET"])
    def get_species_xeno_canto(species_id):
        xck = f"xeno_canto:{species_id}"
        hit, xc = cache_get(xck)
        if hit:
            return xc, 200
        species = db.session.get(Species, species_id)
        if not species:
            return {"error": "Species not found"}, 404
        recordings = fetch_recordings(species.name, limit=5)
        term = _search_term_from_species_name(species.name) or species.name
        search_url = f"https://xeno-canto.org/explore?query={quote(term)}" if term else None
        body = {
            "recordings": recordings,
            "species_name": species.name,
            "xeno_canto_search_url": search_url,
        }
        cache_set(xck, body, 600)
        return body, 200

    @app.route("/api/ui/species/<int:species_id>/summary", methods=["GET"])
    def get_species_summary(species_id):
        sck = f"species_summary:{species_id}"
        hit, sc = cache_get(sck)
        if hit:
            return sc
        species = db.session.get(Species, species_id)
        if not species:
            return {"error": "Species not found"}, 404

        children = Species.query.filter_by(parent_id=species_id).all()
        all_species_ids = [species.id] + [c.id for c in children]

        out = build_species_summary(db.session, species, children, all_species_ids)
        cache_set(sck, out, 30)
        return out

    @app.route("/api/ui/species/<int:species_id>/refresh-metadata", methods=["POST"])
    def refresh_species_card_metadata(species_id):
        """Перезапрос фото/описания/источника для одной карточки (Wikipedia → iNaturalist)."""
        if not settings_check_access():
            return {"error": "Password required"}, 403
        species = db.session.get(Species, species_id)
        if not species:
            return {"error": "Species not found"}, 404
        try:
            refresh_species_metadata_from_sources(species)
            db.session.commit()
            cache_delete(f"species_summary:{species_id}")
            cache_delete_prefix("species_list:v3:")
            bust_response_caches()
            return {
                "ok": True,
                "species_id": species_id,
                "name": species.name,
                "image_url": species.image_url,
                "description": species.description,
                "metadata_source": species.metadata_source,
                "metadata_source_url": species.metadata_source_url,
            }, 200
        except Exception as e:
            db.session.rollback()
            app.logger.exception("refresh_species_card_metadata failed: %s", e)
            return {"error": "Failed to refresh species metadata"}, 500

    @app.route("/api/ui/species-image", methods=["GET"])
    def proxy_species_image():
        raw = (request.args.get("url") or "").strip()
        result = run_species_image_proxy(raw, app.logger)
        if isinstance(result, Response):
            return result
        body, status = result
        return body, status

    @app.route("/api/ui/species/tuning-targets", methods=["GET"])
    def get_tuning_targets():
        if not contributor_or_admin_access():
            return {"error": "Password required"}, 403
        return build_tuning_targets_payload(db.session), 200

    @app.route("/api/ui/species/<int:species_id>/tuning-target", methods=["POST"])
    def set_species_tuning_target(species_id: int):
        if not contributor_or_admin_access():
            return {"error": "Password required"}, 403
        payload = request.json or {}
        enabled = bool(payload.get("enabled"))
        out = apply_tuning_target_toggle(db.session, species_id, enabled)
        if out.get("error"):
            return out, 404
        bust_response_caches()
        return out, 200
