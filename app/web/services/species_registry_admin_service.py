"""HTTP-оркестрация admin API species-registry (тонкие роуты, #293)."""

from __future__ import annotations

import csv
import io
import logging
import threading
from typing import TYPE_CHECKING

from flask import Response

import routes.ui_system_jobs_state as job_state
from app_config.app_config import app_config
from models import Species, db
from services.http_response_cache import (
    bust_response_caches,
    bust_system_response_caches,
)
from services.species_registry_service import (
    backfill_species_taxa,
    catalog_cards_coverage_snapshot,
    ensure_allowlist_species_materialized,
    ensure_species_registry_seeded,
    enrich_species_metadata_with_status,
    repair_catalog_cards,
    species_registry_health,
    unresolved_species_report,
)
from services.species_tuning_targets_service import get_tuning_target_ids
from services.system_metrics_sampler_service import catalog_cards_schedule_state
from util import bust_feeder_species_filter_cache

if TYPE_CHECKING:
    from flask import Flask

_log = logging.getLogger(__name__)


def _bust_registry_caches() -> None:
    bust_response_caches()
    bust_system_response_caches()
    bust_feeder_species_filter_cache()


def seed_species_registry() -> tuple[dict, int]:
    try:
        stats = ensure_species_registry_seeded()
        _bust_registry_caches()
        return {"ok": True, **stats}, 200
    except Exception as e:
        db.session.rollback()
        _log.exception("Seed species registry failed: %s", e)
        return {"error": str(e)}, 500


def run_species_registry_backfill(payload: dict) -> tuple[dict, int]:
    try:
        dry_run = bool(payload.get("dry_run", True))
        limit = payload.get("limit")
        if limit is not None:
            try:
                limit = int(limit)
            except (ValueError, TypeError):
                return {"error": "limit must be int"}, 400
        stats = backfill_species_taxa(dry_run=dry_run, limit=limit)
        if not dry_run:
            _bust_registry_caches()
        return {"ok": True, **stats}, 200
    except Exception as e:
        db.session.rollback()
        _log.exception("Species registry backfill failed: %s", e)
        return {"error": str(e)}, 500


def get_unresolved_species_report(limit: int) -> tuple[dict, int]:
    try:
        items = unresolved_species_report(limit=limit)
        return {"items": items, "count": len(items)}, 200
    except Exception as e:
        _log.exception("Unresolved species report failed: %s", e)
        return {"error": str(e)}, 500


def parse_unresolved_limit(raw: str | None) -> int:
    if raw is None:
        return 100
    try:
        return int(raw)
    except (ValueError, TypeError):
        return 100


def start_metadata_enrichment(flask_app: Flask, payload: dict) -> tuple[dict, int]:
    with job_state._species_metadata_lock:
        if job_state._species_metadata_status.get("status") == "running":
            return {
                "error": "Enrichment already running",
                "status": job_state._species_metadata_status,
            }, 409
        try:
            limit = int(payload.get("limit", 300))
        except (ValueError, TypeError):
            return {"error": "limit must be int"}, 400
        retry_failed_only = bool(payload.get("retry_failed_only", False))
        job_state._species_metadata_status.update(
            {
                "status": "running",
                "result": None,
                "error": None,
                "progress": {
                    "limit": limit,
                    "retry_failed_only": retry_failed_only,
                },
            }
        )

        def _run() -> None:
            try:
                with flask_app.app_context():
                    stats = enrich_species_metadata_with_status(
                        limit=limit,
                        dry_run=False,
                        retry_failed_only=retry_failed_only,
                    )
                with job_state._species_metadata_lock:
                    job_state._species_metadata_status.update(
                        {
                            "status": "done",
                            "result": stats,
                            "error": None,
                        }
                    )
            except Exception as e:
                with job_state._species_metadata_lock:
                    job_state._species_metadata_status.update(
                        {
                            "status": "error",
                            "result": None,
                            "error": str(e),
                        }
                    )

        threading.Thread(target=_run, daemon=True).start()
        return {
            "message": "Species metadata enrichment started",
            "status": job_state._species_metadata_status,
        }, 202


def species_metadata_enrichment_status_body() -> dict:
    with job_state._species_metadata_lock:
        return dict(job_state._species_metadata_status)


def get_species_registry_health_body() -> tuple[dict, int]:
    try:
        return species_registry_health(), 200
    except Exception as e:
        _log.exception("Species registry health failed: %s", e)
        return {"error": str(e)}, 500


def materialize_allowlist_species(payload: dict) -> tuple[dict, int]:
    dry_run = bool(payload.get("dry_run", False))
    fill_metadata = bool(payload.get("fill_metadata", True))
    try:
        limit = int(payload.get("limit", 5000))
    except (TypeError, ValueError):
        return {"error": "limit must be int"}, 400
    try:
        body = ensure_allowlist_species_materialized(
            app_config.get,
            fill_metadata=fill_metadata,
            dry_run=dry_run,
            limit=limit,
        )
        _bust_registry_caches()
        return body, 200
    except Exception as e:
        db.session.rollback()
        _log.exception("Materialize allowlist failed: %s", e)
        return {"error": str(e)}, 500


def start_repair_catalog_cards(flask_app: Flask, payload: dict) -> tuple[dict, int]:
    with job_state._catalog_cards_lock:
        if job_state._catalog_cards_status.get("status") == "running":
            return {
                "error": "Repair already running",
                "status": job_state._catalog_cards_status,
            }, 409
        try:
            limit = int(payload.get("limit", 6000))
        except (TypeError, ValueError):
            return {"error": "limit must be int"}, 400
        cov_before = catalog_cards_coverage_snapshot(app_config.get)
        job_state._catalog_cards_status.update(
            {
                "status": "running",
                "result": None,
                "error": None,
                "progress": {
                    "limit": limit,
                    "coverage_before": cov_before,
                },
            }
        )

        def _run() -> None:
            try:
                with flask_app.app_context():
                    with job_state._catalog_cards_lock:
                        rotate = int(job_state._catalog_repair_priority_rotate)
                    result = repair_catalog_cards(
                        app_config.get,
                        dry_run=False,
                        limit=limit,
                        priority_rotate=rotate,
                    )
                    cov_after = catalog_cards_coverage_snapshot(app_config.get)
                with job_state._catalog_cards_lock:
                    job_state._catalog_repair_priority_rotate = (rotate + limit) % 1_000_003
                    merged = {**result, "coverage_after": cov_after}
                    job_state._catalog_cards_status.update(
                        {
                            "status": "done",
                            "result": merged,
                            "error": None,
                        }
                    )
            except Exception as e:
                with job_state._catalog_cards_lock:
                    job_state._catalog_cards_status.update(
                        {
                            "status": "error",
                            "result": None,
                            "error": str(e),
                        }
                    )

        threading.Thread(target=_run, daemon=True).start()
        return {
            "message": "Catalog cards repair started",
            "status": job_state._catalog_cards_status,
        }, 202


def repair_catalog_cards_status_snapshot() -> dict:
    with job_state._catalog_cards_lock:
        snap = dict(job_state._catalog_cards_status)
    snap["coverage_now"] = catalog_cards_coverage_snapshot(app_config.get)
    snap["schedule"] = catalog_cards_schedule_state()
    return snap


def species_data_quality_report(duplicate_limit: int) -> tuple[dict, int]:
    from services.species_data_quality_service import (
        build_catalog_polish_report,
        build_data_quality_report,
    )

    dup_limit = max(10, min(duplicate_limit, 500))
    try:
        body = build_data_quality_report(
            db.session,
            duplicate_group_limit=dup_limit,
        )
        body["catalog_polish"] = build_catalog_polish_report(db.session)
        body["coverage_now"] = catalog_cards_coverage_snapshot(app_config.get)
        return body, 200
    except Exception as e:
        _log.exception("Species data quality report failed: %s", e)
        return {"error": str(e)}, 500


def classifier_dataset_alignment_report(
    classifier_limit: int,
    catalog_limit: int,
    dataset_limit: int,
) -> tuple[dict, int]:
    from services.species_dataset_alignment_service import (
        build_classifier_dataset_alignment_report,
    )

    try:
        body = build_classifier_dataset_alignment_report(
            db.session,
            app_config.get,
            classifier_limit=classifier_limit,
            catalog_limit=catalog_limit,
            dataset_limit=dataset_limit,
        )
        return body, 200
    except Exception as e:
        _log.exception("Classifier/dataset alignment report failed: %s", e)
        return {"error": str(e)}, 500


def catalog_coverage_metrics_body() -> tuple[dict, int]:
    from services.species_dataset_alignment_service import (
        build_catalog_coverage_metrics,
    )

    try:
        body = build_catalog_coverage_metrics(db.session, app_config.get)
        return body, 200
    except Exception as e:
        _log.exception("Catalog coverage metrics failed: %s", e)
        return {"error": str(e)}, 500


def export_tuning_targets(fmt: str) -> tuple[dict | Response, int]:
    ids = get_tuning_target_ids()
    rows = Species.query.filter(Species.id.in_(ids)).all() if ids else []
    by_id = {s.id: s for s in rows}
    body_rows = [{"id": sid, "name": by_id[sid].name} for sid in ids if sid in by_id]
    if fmt == "csv":
        buf = io.StringIO()
        wr = csv.writer(buf)
        wr.writerow(["species_id", "species_name"])
        for r in body_rows:
            wr.writerow([r["id"], r["name"]])
        disp = 'attachment; filename="birdlense_tuning_targets.csv"'
        return Response(
            buf.getvalue(),
            mimetype="text/csv",
            headers={"Content-Disposition": disp},
        ), 200
    return {"count": len(body_rows), "targets": body_rows}, 200


def normalize_export_format(raw: str | None) -> str:
    return (raw or "json").strip().lower()
