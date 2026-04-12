"""DB bootstrap inside app.app_context: schema, seed, registry, maintenance."""

from __future__ import annotations

import logging
import os
import threading

from flask import Flask
from flask_migrate import upgrade

from models import Species, db
from services.legacy_import_cleanup_service import cleanup_legacy_import_placeholders
from seed.seed import seed
from services.species_registry_service import (
    backfill_species_taxa,
    enrich_species_metadata_with_status,
    ensure_species_registry_seeded,
    repair_recently_reset_species_metadata,
)

_log = logging.getLogger(__name__)


def _env_truthy(name: str, default: str = "0") -> bool:
    return (os.environ.get(name, default) or default).strip().lower() in (
        "1",
        "true",
        "yes",
    )


def apply_schema_migrations_and_seed(migrations_dir: str) -> None:
    """Run create_all, Alembic upgrade, and base seed."""
    db.create_all()
    upgrade(directory=migrations_dir)
    seed()


def bootstrap_species_registry() -> None:
    """Seed species registry; optional startup backfill via env flag."""
    try:
        seed_stats = ensure_species_registry_seeded()
        _log.info(
            "species_registry seed: taxa_created=%s aliases_created=%s",
            seed_stats.get("taxa_created", 0),
            seed_stats.get("aliases_created", 0),
        )
        if _env_truthy("BIRDLENSE_STARTUP_BACKFILL_SPECIES_TAXA"):
            bf_stats = backfill_species_taxa(dry_run=False)
            _log.info(
                "species_registry backfill: processed=%s matched=%s unresolved=%s",
                bf_stats.get("processed", 0),
                bf_stats.get("matched", 0),
                bf_stats.get("unresolved", 0),
            )
        else:
            _log.info(
                "species_registry backfill skipped "
                "(set BIRDLENSE_STARTUP_BACKFILL_SPECIES_TAXA=1 or POST "
                "/api/ui/system/species-registry/backfill)",
            )
    except Exception as e:
        db.session.rollback()
        _log.warning("species_registry init skipped: %s", e)


def bootstrap_legacy_import_cleanup() -> None:
    """Optional legacy import placeholder cleanup when env flag is set."""
    try:
        if _env_truthy("BIRDLENSE_STARTUP_CLEANUP_LEGACY_IMPORT"):
            cleaned_rows, cleaned_visits = cleanup_legacy_import_placeholders()
            if cleaned_rows or cleaned_visits:
                db.session.commit()
                _log.info(
                    "legacy import cleanup: detections_removed=%s visits_removed=%s",
                    cleaned_rows,
                    cleaned_visits,
                )
        else:
            _log.info(
                "legacy import cleanup on startup skipped "
                "(set BIRDLENSE_STARTUP_CLEANUP_LEGACY_IMPORT=1; scan import "
                "still cleans)",
            )
    except Exception as e:
        db.session.rollback()
        _log.warning("legacy import cleanup skipped: %s", e)


def bootstrap_species_metadata_repair(app: Flask) -> None:
    """Background repair for species rows missing image but having description."""
    try:
        reset_victims = Species.query.filter(
            Species.image_url.is_(None),
            Species.description.isnot(None),
        ).count()
        repair_on_start = _env_truthy("BIRDLENSE_STARTUP_REPAIR_SPECIES_METADATA")
        if reset_victims and not app.config.get("TESTING") and repair_on_start:

            def _repair_reset_victims():
                with app.app_context():
                    try:
                        stats = repair_recently_reset_species_metadata(
                            limit=reset_victims,
                            dry_run=False,
                        )
                        _log.info(
                            "species_metadata_repair: processed=%s repaired=%s failed=%s",
                            stats.get("processed", 0),
                            stats.get("repaired", 0),
                            stats.get("failed", 0),
                        )
                    except Exception as repair_err:
                        db.session.rollback()
                        _log.warning(
                            "species_metadata_repair skipped: %s",
                            repair_err,
                        )

            threading.Thread(target=_repair_reset_victims, daemon=True).start()
        elif reset_victims and not app.config.get("TESTING") and not repair_on_start:
            _log.info(
                "species metadata repair on startup skipped "
                "(%s rows eligible; set "
                "BIRDLENSE_STARTUP_REPAIR_SPECIES_METADATA=1)",
                reset_victims,
            )
    except Exception as e:
        db.session.rollback()
        _log.warning("species metadata repair setup skipped: %s", e)


def bootstrap_species_metadata_enrich(app: Flask) -> None:
    """Опциональный фоновый enrich (SPECIES_METADATA_ENRICH_ON_START)."""
    try:
        raw = os.environ.get("SPECIES_METADATA_ENRICH_ON_START", "0").strip()
        enrich_on_start = raw.lower() in ("1", "true", "yes")
        if not app.config.get("TESTING") and enrich_on_start:
            marker = "/tmp/.birdlense_species_metadata_enrich_started"
            if not os.path.exists(marker):
                try:
                    open(marker, "a").close()
                except OSError:
                    pass

                def _background_enrich():
                    with app.app_context():
                        log = logging.getLogger(__name__)
                        try:
                            stats = enrich_species_metadata_with_status(
                                limit=300,
                                dry_run=False,
                                retry_failed_only=False,
                            )
                            log.info(
                                "species_metadata_enrich pass1: processed=%s updated=%s failed=%s",
                                stats.get("processed", 0),
                                stats.get("updated", 0),
                                stats.get("failed", 0),
                            )
                            retry_stats = enrich_species_metadata_with_status(
                                limit=300,
                                dry_run=False,
                                retry_failed_only=True,
                            )
                            log.info(
                                "species_metadata_enrich retry: processed=%s updated=%s failed=%s",
                                retry_stats.get("processed", 0),
                                retry_stats.get("updated", 0),
                                retry_stats.get("failed", 0),
                            )
                        except Exception as enrich_err:
                            log.warning(
                                "species_metadata_enrich skipped: %s",
                                enrich_err,
                            )

                threading.Thread(
                    target=_background_enrich,
                    daemon=True,
                ).start()
    except Exception as e:
        _log.warning("species_metadata_enrich setup failed: %s", e)
