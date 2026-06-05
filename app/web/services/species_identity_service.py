"""Species identity resolution for ingest/regen without metadata side effects."""

from __future__ import annotations

from typing import Optional

from app_config.app_config import app_config
from models import Species, SpeciesAlias, SpeciesVisit, VideoSpecies
from services.species_catalog.vocabulary import get_species_vocabulary_snapshot
from services.species_registry_service import resolve_species_name
from species_constants import CATALOG_RODENT_SPECIES, GENERIC_BIRD_SPECIES
from services.species_catalog.canon import normalize_catalog_display_name
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

    def _species_has_observed_activity(self, species_id: int) -> bool:
        if VideoSpecies.query.filter_by(species_id=species_id).first():
            return True
        if SpeciesVisit.query.filter_by(species_id=species_id).first():
            return True
        return False

    def ingest_blocked(
        self,
        display_name: str,
        raw_normalized: str,
        taxon_common_name: str | None,
        *,
        species_id: int | None = None,
    ) -> bool:
        canonical_candidates = {
            str(display_name or "").strip().lower(),
            str(raw_normalized or "").strip().lower(),
            str(taxon_common_name or "").strip().lower(),
        }
        if GENERIC_BIRD_SPECIES.strip().lower() in canonical_candidates:
            return False
        if CATALOG_RODENT_SPECIES.strip().lower() in canonical_candidates:
            return False
        if species_id is not None and self._species_has_observed_activity(int(species_id)):
            return False
        if not bool(app_config.get("species.catalog_strict_ingest")):
            return False
        vocab = get_species_vocabulary_snapshot()
        if vocab.allows_ingest_name(display_name, raw_normalized, taxon_common_name):
            return False
        for candidate in (display_name, raw_normalized, taxon_common_name):
            if candidate and resolve_species_name(str(candidate).strip(), source="ingest_gate").found:
                return False
        return True

    @staticmethod
    def _norm_alias_key(name: str) -> str:
        s = str(name or "").strip().lower()
        s = s.replace("_", " ").replace("-", " ")
        return " ".join(s.split())

    def _attach_aliases_to_taxon(
        self,
        *,
        taxon_id: int | None,
        canonical_name: str,
        aliases: list[str] | None,
        source: str,
    ) -> int:
        if not taxon_id:
            return 0
        created = 0
        canonical_key = self._norm_alias_key(canonical_name)
        for raw in aliases or []:
            alias = str(raw or "").strip()
            if not alias:
                continue
            alias_key = self._norm_alias_key(alias)
            if not alias_key or alias_key == canonical_key:
                continue
            row = SpeciesAlias.query.filter_by(alias_key=alias_key).first()
            if row:
                if int(row.taxon_id) != int(taxon_id):
                    self.logger.warning(
                        'Alias collision skipped: "%s" -> taxon_id=%s (wanted=%s, source=%s)',
                        alias,
                        row.taxon_id,
                        taxon_id,
                        source,
                    )
                continue
            self.db.session.add(
                SpeciesAlias(
                    alias=alias[:255],
                    alias_key=alias_key,
                    taxon_id=int(taxon_id),
                )
            )
            created += 1
        return created

    def resolve_or_create_species(
        self,
        name: str,
        *,
        source: str = "ingest",
        audit_aliases: list[str] | None = None,
        audit_scientific_names: list[str] | None = None,
    ) -> Optional[Species]:
        if not name or not isinstance(name, str):
            return None
        normalized = name.strip()
        if not normalized:
            return None
        if normalized.lower() in {"bird", "unknown", "unknown bird", "generic bird"}:
            normalized = GENERIC_BIRD_SPECIES
        resolution = resolve_species_name(normalized, source=source)
        taxon = resolution.taxon if resolution.found else None
        taxon_common = taxon.common_name if taxon else None
        mapping = load_species_canonical_mapping()
        raw_canonical = taxon_common if taxon else normalized
        canonical_name = normalize_catalog_display_name(raw_canonical, mapping)

        species = Species.query.filter_by(name=canonical_name).first()
        if species:
            if canonical_name in (GENERIC_BIRD_SPECIES, CATALOG_RODENT_SPECIES):
                species.active = True
                birds_parent = Species.query.filter_by(name="Birds").first()
                if birds_parent and not species.parent_id:
                    species.parent_id = birds_parent.id
                if not (species.description or "").strip():
                    species.description = (
                        "Bird detected by the camera before species classification. "
                        "Use review or manual correction to assign a specific species."
                        if canonical_name == GENERIC_BIRD_SPECIES
                        else "Rodent detected by the camera. Use review to assign a specific species when known."
                    )
            current_common = species.taxon.common_name if species.taxon else None
            if self.ingest_blocked(
                species.name or "",
                normalized,
                current_common,
                species_id=int(species.id),
            ):
                return self.get_or_create_unknown_species()
            if resolution.found and taxon and species.taxon_id != taxon.id:
                species.taxon_id = taxon.id
            taxon_id = species.taxon_id or (taxon.id if taxon else None)
            alias_count = self._attach_aliases_to_taxon(
                taxon_id=taxon_id,
                canonical_name=species.name,
                aliases=[*(audit_aliases or []), *(audit_scientific_names or [])],
                source=source,
            )
            if alias_count:
                self.logger.info(
                    'Attached %s source alias(es) to "%s" (source=%s)',
                    alias_count,
                    species.name,
                    source,
                )
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
            active=canonical_name in (GENERIC_BIRD_SPECIES, CATALOG_RODENT_SPECIES),
            taxon_id=taxon.id if taxon else None,
        )
        if species.active and not (species.description or "").strip():
            species.description = (
                "Bird detected by the camera before species classification. "
                "Use review or manual correction to assign a specific species."
                if canonical_name == GENERIC_BIRD_SPECIES
                else "Rodent detected by the camera. Use review to assign a specific species when known."
            )
        self.db.session.add(species)
        self.db.session.flush()
        alias_count = self._attach_aliases_to_taxon(
            taxon_id=species.taxon_id,
            canonical_name=species.name,
            aliases=[*(audit_aliases or []), *(audit_scientific_names or [])],
            source=source,
        )
        self.logger.info(
            'Created species "%s" (parent_id=%s, resolver_method=%s, attached_aliases=%s)',
            canonical_name,
            parent_id,
            resolution.method,
            alias_count,
        )
        return species
