"""Список видов, observed, track-regen, bird_families (#198)."""

from flask import request

from models import db
from services.cache import cache_get, cache_set
from services.species_catalog_api_service import (
    fetch_bird_families_list_safe,
    fetch_observed_species_list,
    fetch_species_catalog_list,
    fetch_species_catalog_meta,
    fetch_track_regen_species_options,
)

from routes.ui_route_constants import (
    CACHE_BIRD_FAMILIES_SEC,
    CACHE_SPECIES_LIST_SEC,
    CACHE_SPECIES_OBSERVED_SEC,
    CACHE_SPECIES_TRACK_REGEN_SEC,
)


def register_ui_species_catalog_routes(app):
    @app.route("/api/ui/species", methods=["GET"])
    def get_all_species():
        exclude_suspects = request.args.get("exclude_suspects", "").strip().lower() in ("1", "true", "yes")
        scope = (request.args.get("scope") or "project").strip().lower()
        include_meta = request.args.get("meta", "").strip().lower() in ("1", "true", "yes")
        cache_key = f"species_list:v4:ex{1 if exclude_suspects else 0}:sc{scope}"
        hit, scached = cache_get(cache_key)
        if hit and not include_meta:
            return scached
        result = fetch_species_catalog_list(
            db.session,
            exclude_suspects=exclude_suspects,
            scope=scope,
        )
        if include_meta:
            meta = fetch_species_catalog_meta(db.session, exclude_suspects=exclude_suspects)
            payload = {"items": result, "meta": meta}
            cache_set(cache_key, result, CACHE_SPECIES_LIST_SEC)
            return payload
        cache_set(cache_key, result, CACHE_SPECIES_LIST_SEC)
        return result

    @app.route("/api/ui/species/observed", methods=["GET"])
    def get_observed_species():
        hit, oc = cache_get("species_observed:v1")
        if hit:
            return oc
        out = fetch_observed_species_list(db.session)
        cache_set("species_observed:v1", out, CACHE_SPECIES_OBSERVED_SEC)
        return out

    @app.route("/api/ui/species/track-regen-options", methods=["GET"])
    def get_species_track_regen_options():
        hit, oc = cache_get("species_track_regen:v1")
        if hit:
            return oc
        out = fetch_track_regen_species_options(db.session)
        cache_set("species_track_regen:v1", out, CACHE_SPECIES_TRACK_REGEN_SEC)
        return out

    @app.route("/api/ui/bird_families", methods=["GET"])
    def get_bird_families():
        hit, fc = cache_get("bird_families:v1")
        if hit:
            return fc
        payload, err = fetch_bird_families_list_safe(db.session)
        if err:
            return {"error": err}, 500
        if payload is None:
            return {"error": "Birds category not found"}, 404
        cache_set("bird_families:v1", payload, CACHE_BIRD_FAMILIES_SEC)
        return payload
