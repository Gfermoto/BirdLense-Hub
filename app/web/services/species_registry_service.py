"""Shim: реализация в ``services.species_catalog.registry`` (#344 фаза C).

Сохраняйте импорты ``from services.species_registry_service import …``.
"""

from __future__ import annotations

from services.species_catalog.registry import (
    SpeciesResolution,
    _rotate_need_slice,
    backfill_species_taxa,
    catalog_cards_coverage_snapshot,
    enrich_species_card_metadata,
    enrich_species_metadata,
    enrich_species_metadata_with_status,
    ensure_allowlist_species_materialized,
    ensure_species_registry_seeded,
    load_catalog_allowlist_names,
    realign_species_images_from_allowlist_science,
    repair_catalog_cards,
    repair_recently_reset_species_metadata,
    resolve_species_name,
    species_name_match_norm_keys,
    species_registry_health,
    unresolved_species_report,
)

__all__ = [
    "SpeciesResolution",
    "_rotate_need_slice",
    "backfill_species_taxa",
    "catalog_cards_coverage_snapshot",
    "enrich_species_card_metadata",
    "enrich_species_metadata",
    "enrich_species_metadata_with_status",
    "ensure_allowlist_species_materialized",
    "ensure_species_registry_seeded",
    "load_catalog_allowlist_names",
    "realign_species_images_from_allowlist_science",
    "repair_catalog_cards",
    "repair_recently_reset_species_metadata",
    "resolve_species_name",
    "species_name_match_norm_keys",
    "species_registry_health",
    "unresolved_species_report",
]
