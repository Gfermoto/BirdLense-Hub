"""Bounded context: species catalog (allowlist, API, reconcile, …).

Фаза B [#344](https://github.com/Gfermoto/BirdLense-Hub/issues/344): модули переносятся
сюда по одному; корневые ``services/species_*.py`` остаются shims до полной миграции импортов.

Корневой пакет реэкспортирует только **allowlist** (лёгкий слой без циклов).
Для API и reconcile импортируйте ``services.species_catalog.api`` и
``services.species_catalog.reconcile`` (или shims ``species_catalog_*_service``).

См. также: ``docs/project/WEB_SERVICES_DOMAIN_MAP.md``.
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
