"""Данные для GET /api/ui/species*, bird_families (#293).

Реализация в ``services/species_catalog/``; shim —
``services/species_catalog_api_service.py`` (#344).
"""

from __future__ import annotations

import logging

from sqlalchemy import distinct, func
from sqlalchemy.orm import joinedload, object_session

from app_config.app_config import app_config
from models import Species, SpeciesTaxon, SpeciesVisit, VideoSpecies
from services.species_catalog.allowlist import (
    allowlist_scientific_name_for_display_name,
    catalog_classifier_meta,
    load_catalog_allowlist_names,
    load_catalog_allowlist_norm_keys,
    scientific_name_from_canonical_mapping,
    species_matches_allowlist,
    species_name_match_norm_keys,
)
from services.species_catalog.vocabulary import get_species_vocabulary_snapshot
from util import load_species_canonical_mapping
from services.species_catalog.canon import normalize_catalog_display_name, parse_scientific_and_common
from services.species_catalog.registry import species_card_needs_full_metadata_refresh
from services.species_data_quality_service import species_ids_to_exclude_from_bird_catalog
from services.species_regional_scope import compute_regional_scope_species_ids
from species_constants import GENERIC_BIRD_SPECIES, GENERIC_RODENT_SPECIES

CatalogScope = str  # "allowlist" | "project" | "observed" | "all"

logger = logging.getLogger(__name__)


_PLACEHOLDER_DESCRIPTIONS = {
    GENERIC_BIRD_SPECIES: (
        "Bird detected by the camera before species classification. "
        "Use review or manual correction to assign a specific species."
    ),
    GENERIC_RODENT_SPECIES: "Rodent detected by the camera. Use review to assign a specific species when known.",
}


def _normalize_catalog_scope(scope: str | None) -> CatalogScope:
    raw = (scope or "project").strip().lower()
    if raw in ("allowlist", "project", "observed", "all"):
        return raw
    return "project"


def _allowlist_row_score(row) -> tuple:
    sp = row.Species
    complete = 0 if species_card_needs_full_metadata_refresh(sp) else 1
    return (complete, int(row.count or 0), 1 if sp.active else 0, -int(sp.id))


def _dedupe_allowlist_species_rows(
    species_list: list,
    *,
    allow_keys: frozenset[str],
    mapping: dict[str, str],
) -> list:
    """One SQLite row per allowlist class (526), not per duplicate legacy name."""
    best_by_key: dict[str, object] = {}
    for row in species_list:
        sp = row.Species
        match_keys = species_name_match_norm_keys(sp.name or "", mapping) & allow_keys
        if not match_keys:
            continue
        canon_key = min(match_keys)
        prev = best_by_key.get(canon_key)
        if prev is None or _allowlist_row_score(row) > _allowlist_row_score(prev):
            best_by_key[canon_key] = row
    return sorted(best_by_key.values(), key=lambda r: (r.Species.name or "").lower())


def _species_has_catalog_audio(sp) -> bool:
    src = (sp.metadata_source or "").strip().lower()
    url = (sp.metadata_source_url or "").strip().lower()
    if "xeno" in src or "xeno-canto" in url:
        return True
    return False


def _ensure_placeholder_catalog_species(session) -> None:
    """Bird/Rodent are visible catalog taxa, even before classifier/manual labels refine them."""
    birds_parent = session.query(Species).filter(Species.name == "Birds").first()
    parent_id = birds_parent.id if birds_parent else None
    changed = False
    for name in (GENERIC_BIRD_SPECIES, GENERIC_RODENT_SPECIES):
        sp = session.query(Species).filter(Species.name == name).first()
        if sp is None:
            sp = Species(
                name=name,
                parent_id=parent_id,
                active=True,
                description=_PLACEHOLDER_DESCRIPTIONS[name],
            )
            session.add(sp)
            changed = True
            continue
        if not sp.active:
            sp.active = True
            changed = True
        if parent_id and not sp.parent_id:
            sp.parent_id = parent_id
            changed = True
        if not (sp.description or "").strip():
            sp.description = _PLACEHOLDER_DESCRIPTIONS[name]
            changed = True
    if changed:
        session.flush()


def _append_project_placeholders(session, species_list: list, catalog_scope: str) -> list:
    if catalog_scope not in ("project", "all"):
        return species_list
    seen = {int(row.Species.id) for row in species_list}
    placeholders = (
        session.query(
            Species,
            func.coalesce(func.sum(SpeciesVisit.max_simultaneous), 0).label("count"),
        )
        .outerjoin(SpeciesVisit)
        .filter(Species.name.in_([GENERIC_BIRD_SPECIES, GENERIC_RODENT_SPECIES]))
        .group_by(Species.id)
        .order_by(Species.name.asc())
        .all()
    )
    for row in placeholders:
        if int(row.Species.id) not in seen:
            species_list.append(row)
            seen.add(int(row.Species.id))
    return species_list


def _species_row_dict(
    row,
    *,
    regional_scope_ids: set[int],
    mapping: dict | None = None,
    allow_keys: frozenset[str] | None = None,
) -> dict:
    sp = row.Species
    mapping = mapping or load_species_canonical_mapping()
    raw_name = sp.name or ""
    display_name = normalize_catalog_display_name(raw_name, mapping) or raw_name
    scientific_name, _common = parse_scientific_and_common(raw_name)
    if not scientific_name:
        taxon = getattr(sp, "taxon", None)
        if taxon is None and getattr(sp, "taxon_id", None):
            sess = object_session(sp)
            if sess is not None:
                taxon = sess.get(SpeciesTaxon, sp.taxon_id)
        if taxon is not None:
            scientific_name = (taxon.scientific_name or "").strip() or None
    if not scientific_name:
        scientific_name = allowlist_scientific_name_for_display_name(display_name, app_config.get)
    if not scientific_name:
        scientific_name = scientific_name_from_canonical_mapping(display_name, mapping)
    classifier_predictable = species_matches_allowlist(raw_name, allow_keys, mapping) if allow_keys else True
    return {
        "id": sp.id,
        "name": display_name,
        "db_name": raw_name,
        "scientific_name": scientific_name,
        "classifier_predictable": classifier_predictable,
        "parent_id": sp.parent_id,
        "created_at": sp.created_at.isoformat(),
        "image_url": sp.image_url,
        "description": sp.description,
        "metadata_source": sp.metadata_source,
        "metadata_source_url": sp.metadata_source_url,
        "active": sp.active,
        "regional_scope": sp.id in regional_scope_ids,
        "count": int(row.count or 0),
        "catalog_card_incomplete": species_card_needs_full_metadata_refresh(sp),
        "catalog_has_audio": _species_has_catalog_audio(sp),
    }


def fetch_species_catalog_list(
    session,
    *,
    exclude_suspects: bool,
    scope: str | None = "allowlist",
    missing_audio: bool = False,
    catalog_incomplete: bool = False,
) -> list[dict]:
    catalog_scope = _normalize_catalog_scope(scope)
    _ensure_placeholder_catalog_species(session)
    query = (
        session.query(
            Species,
            func.coalesce(func.sum(SpeciesVisit.max_simultaneous), 0).label("count"),
        )
        .options(joinedload(Species.taxon))
        .outerjoin(SpeciesVisit)
        .group_by(Species.id)
        .order_by(Species.name.asc())
    )
    species_list = query.all()
    if exclude_suspects:
        bad_ids = species_ids_to_exclude_from_bird_catalog(session)
        species_list = [s for s in species_list if s.Species.id not in bad_ids]

    allow_keys = load_catalog_allowlist_norm_keys(app_config.get)
    mapping = load_species_canonical_mapping()
    vocab = get_species_vocabulary_snapshot()
    if catalog_scope == "allowlist" and allow_keys:
        species_list = [s for s in species_list if species_matches_allowlist(s.Species.name, allow_keys, mapping)]
        species_list = _dedupe_allowlist_species_rows(species_list, allow_keys=allow_keys, mapping=mapping)
    elif catalog_scope == "project":
        project_keys = vocab.project_norm_keys
        species_list = [
            s
            for s in species_list
            if int(s.count or 0) > 0 or species_matches_allowlist(s.Species.name, project_keys, mapping)
        ]
        species_list = _dedupe_allowlist_species_rows(
            species_list,
            allow_keys=project_keys,
            mapping=mapping,
        )
    elif catalog_scope == "observed":
        species_list = [s for s in species_list if int(s.count or 0) > 0]
        if allow_keys:
            species_list = [s for s in species_list if species_matches_allowlist(s.Species.name, allow_keys, mapping)]
            species_list = _dedupe_allowlist_species_rows(species_list, allow_keys=allow_keys, mapping=mapping)

    species_list = _append_project_placeholders(session, species_list, catalog_scope)

    regional_scope_ids = compute_regional_scope_species_ids()
    rows = [
        _species_row_dict(
            row,
            regional_scope_ids=regional_scope_ids,
            mapping=mapping,
            allow_keys=allow_keys,
        )
        for row in species_list
    ]
    if catalog_scope != "all":
        for item in rows:
            item["catalog_scope"] = catalog_scope
    if missing_audio:
        rows = [r for r in rows if not r.get("catalog_has_audio")]
    if catalog_incomplete:
        rows = [r for r in rows if r.get("catalog_card_incomplete")]
    return rows


def fetch_species_catalog_meta(session, *, exclude_suspects: bool) -> dict:
    """Counts for UI: allowlist (classifier) vs full SQLite catalog."""
    total_db = session.query(func.count(Species.id)).scalar() or 0
    allowlist_names = load_catalog_allowlist_names(app_config.get)
    allowlist_total = len(allowlist_names) if allowlist_names else 0
    listed = fetch_species_catalog_list(session, exclude_suspects=exclude_suspects, scope="allowlist")
    incomplete = sum(1 for row in listed if row.get("catalog_card_incomplete"))
    vocab = get_species_vocabulary_snapshot()
    project_listed = fetch_species_catalog_list(
        session,
        exclude_suspects=exclude_suspects,
        scope="project",
    )
    meta = {
        "db_species_total": int(total_db),
        "allowlist_total": int(allowlist_total),
        "listed_allowlist": len(listed),
        "allowlist_incomplete": incomplete,
        "project_vocabulary_total": len(vocab.project_norm_keys),
        "listed_project": len(project_listed),
        "arbitration_vocabulary_total": len(vocab.arbitration_norm_keys),
    }
    meta.update(catalog_classifier_meta(app_config.get))
    try:
        from services.species_catalog.registry import catalog_cards_coverage_snapshot

        cov = catalog_cards_coverage_snapshot(app_config.get)
        meta["catalog_cards"] = {
            "complete_cards": cov.get("complete_cards"),
            "allowlist_total": cov.get("allowlist_total"),
            "completion_percent": cov.get("completion_percent"),
            "missing_image_lines": cov.get("missing_image_lines"),
            "audio_probed_sample": cov.get("audio_probed_sample"),
            "audio_with_source_sample": cov.get("audio_with_source_sample"),
            "audio_coverage_percent_sample": cov.get("audio_coverage_percent_sample"),
        }
        meta["catalog_with_audio"] = sum(1 for row in listed if row.get("catalog_has_audio"))
        meta["catalog_missing_audio"] = max(0, len(listed) - meta["catalog_with_audio"])
    except Exception:
        logger.debug("catalog_cards snapshot for meta failed", exc_info=True)
    return meta


def fetch_observed_species_list(session) -> list[dict]:
    subq = (
        session.query(
            SpeciesVisit.species_id,
            func.coalesce(func.sum(SpeciesVisit.max_simultaneous), 0).label("count"),
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
    return [{"id": s.id, "name": s.name, "count": int(cnt)} for s, cnt in rows]


def fetch_track_regen_species_options(session) -> list[dict]:
    subq = (
        session.query(
            VideoSpecies.species_id,
            func.count(distinct(VideoSpecies.video_id)).label("video_count"),
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
    return [{"id": s.id, "name": s.name, "count": int(vc)} for s, vc in rows]


def fetch_bird_families_list(session) -> list[dict] | None:
    """Список семейств под «Birds» или None, если категория не найдена."""
    birds_category = session.query(Species).filter_by(name="Birds").first()
    if not birds_category:
        return None
    families = session.query(Species).filter_by(parent_id=birds_category.id).all()
    return [{"id": family.id, "name": family.name} for family in families]


def fetch_bird_families_list_safe(session) -> tuple[list[dict] | None, str | None]:
    """(payload, None) или (None, error_message) при неожиданной ошибке БД."""
    try:
        return fetch_bird_families_list(session), None
    except Exception:
        logger.exception("Error fetching bird families")
        return None, "Failed to fetch bird families"


__all__ = [
    "fetch_bird_families_list",
    "fetch_bird_families_list_safe",
    "fetch_observed_species_list",
    "fetch_species_catalog_list",
    "fetch_species_catalog_meta",
    "fetch_track_regen_species_options",
]
