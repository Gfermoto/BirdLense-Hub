"""Species identity resolution for ingest/regen without metadata side effects."""

from __future__ import annotations

from typing import Optional

from app_config.app_config import app_config
from models import Species
from services.species_catalog_allowlist_service import (
    load_catalog_allowlist_norm_keys,
    species_matches_allowlist,
)
from services.species_registry_service import resolve_species_name
from species_constants import GENERIC_BIRD_SPECIES
from util import get_parent_name_for_species, load_species_canonical_mapping


class SpeciesIdentityService:
    """Resolve raw detector labels into persisted ``Species`` rows."""

    def __init__(self, db, logger):
        self.db = db
        self.logger = logger

    def get_or_create_unknown_species(self) -> Optional[Species]:
        existing = Species.query.filter_by(name="Unknown").first()
        if existing:
            return existing
        birds = Species.query.filter_by(name="Birds").first()
        parent_id = birds.id if birds else None
        row = Species(name="Unknown", parent_id=parent_id, active=False)
        self.db.session.add(row)
        self.db.session.flush()
        self.logger.info('Created species "Unknown" for blocked/off-allowlist ingest')
        return row

    def ingest_blocked(
        self,
        display_name: str,
        raw_normalized: str,
        taxon_common_name: str | None,
    ) -> bool:
        canonical_candidates = {
            str(display_name or "").strip().lower(),
            str(raw_normalized or "").strip().lower(),
            str(taxon_common_name or "").strip().lower(),
        }
        if GENERIC_BIRD_SPECIES.strip().lower() in canonical_candidates:
            return False
        if not bool(app_config.get("species.catalog_strict_ingest")):
            return False
        allow = load_catalog_allowlist_norm_keys(app_config.get)
        if allow is None:
            self.logger.warning(
                "Strict catalog ingest is enabled but allowlist is unavailable; "
                'blocking species "%s" until allowlist is restored.',
                display_name or raw_normalized or taxon_common_name or "unknown",
            )
            return True
        mapping = load_species_canonical_mapping()
        ok_display = species_matches_allowlist(display_name or "", allow, mapping)
        ok_raw = species_matches_allowlist(raw_normalized or "", allow, mapping)
        return not (ok_display or ok_raw)

    def resolve_or_create_species(self, name: str, *, source: str = "ingest") -> Optional[Species]:
        if not name or not isinstance(name, str):
            return None
        normalized = name.strip()
        if not normalized:
            return None
        if normalized.lower() in {"bird", "unknown"}:
            normalized = GENERIC_BIRD_SPECIES
        resolution = resolve_species_name(normalized, source=source)
        taxon = resolution.taxon if resolution.found else None
        taxon_common = taxon.common_name if taxon else None
        canonical_name = taxon_common if taxon else normalized

        species = Species.query.filter_by(name=canonical_name).first()
        if species:
            current_common = species.taxon.common_name if species.taxon else None
            if self.ingest_blocked(species.name or "", normalized, current_common):
                return self.get_or_create_unknown_species()
            if resolution.found and taxon and species.taxon_id != taxon.id:
                species.taxon_id = taxon.id
            return species

        if self.ingest_blocked(canonical_name, normalized, taxon_common):
            return self.get_or_create_unknown_species()

        birds = Species.query.filter_by(name="Birds").first()
        parent_id = birds.id if birds else None
        parent_name = get_parent_name_for_species(canonical_name)
        if parent_name:
            parent_species = Species.query.filter_by(name=parent_name).first()
            if parent_species:
                parent_id = parent_species.id
        species = Species(
            name=canonical_name,
            parent_id=parent_id,
            active=False,
            taxon_id=taxon.id if taxon else None,
        )
        self.db.session.add(species)
        self.db.session.flush()
        self.logger.info(
            'Created species "%s" (parent_id=%s, resolver_method=%s)',
            canonical_name,
            parent_id,
            resolution.method,
        )
        return species
