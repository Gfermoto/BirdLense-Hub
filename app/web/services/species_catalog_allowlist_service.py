"""Shim: реализация перенесена в ``services.species_catalog.allowlist`` (#344 фаза B).

Сохраняйте существующие импорты ``from services.species_catalog_allowlist_service import …``.
"""

from __future__ import annotations

from services.species_catalog.allowlist import (
    allowlist_scientific_name_for_display_name,
    clear_allowlist_cache,
    ingest_name_matches_allowlist,
    load_catalog_allowlist_names,
    load_catalog_allowlist_norm_keys,
    resolve_allowlist_path,
    species_matches_allowlist,
    species_name_match_norm_keys,
)

__all__ = [
    "allowlist_scientific_name_for_display_name",
    "clear_allowlist_cache",
    "ingest_name_matches_allowlist",
    "load_catalog_allowlist_names",
    "load_catalog_allowlist_norm_keys",
    "resolve_allowlist_path",
    "species_matches_allowlist",
    "species_name_match_norm_keys",
]
