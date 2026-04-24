"""Shim: реализация в ``services.species_catalog.api`` (#344 фаза B).

Сохраняйте импорты ``from services.species_catalog_api_service import …``.
"""

from __future__ import annotations

from services.species_catalog.api import (
    fetch_bird_families_list,
    fetch_bird_families_list_safe,
    fetch_observed_species_list,
    fetch_species_catalog_list,
    fetch_track_regen_species_options,
)

__all__ = [
    "fetch_bird_families_list",
    "fetch_bird_families_list_safe",
    "fetch_observed_species_list",
    "fetch_species_catalog_list",
    "fetch_track_regen_species_options",
]
