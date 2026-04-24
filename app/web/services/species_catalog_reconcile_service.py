"""Shim: реализация в ``services.species_catalog.reconcile`` (#344 фаза B).

Сохраняйте импорты ``from services.species_catalog_reconcile_service import reconcile_species_catalog``.
"""

from __future__ import annotations

from services.species_catalog.reconcile import reconcile_species_catalog

__all__ = ["reconcile_species_catalog"]
