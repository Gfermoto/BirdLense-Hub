"""Фоновый сбор системных метрик и автозапуск repair catalog cards (#293)."""

from __future__ import annotations

import os
import threading
from datetime import datetime, timedelta, timezone

import routes.ui_system_jobs_state as job_state
from app_config.app_config import app_config
from models import SystemResourceSample, db
from services.species_registry_service import (
    catalog_cards_coverage_snapshot,
    repair_catalog_cards,
)
from services.system_live_metrics_service import collect_live_system_metrics
from services.system_metrics_constants import (
    SYSTEM_METRICS_RETENTION_HOURS,
    SYSTEM_METRICS_SAMPLE_INTERVAL_SEC,
    env_bounded_int,
)
from sqlalchemy import delete

CATALOG_REPAIR_AUTORUN_ENABLED = os.environ.get(
    "BIRDLENSE_CATALOG_REPAIR_AUTORUN",
    "1",
).strip().lower() in ("1", "true", "yes")
CATALOG_REPAIR_INTERVAL_MIN = env_bounded_int(
    "BIRDLENSE_CATALOG_REPAIR_INTERVAL_MIN",
    180,
    min_v=15,
    max_v=1440,
)
CATALOG_REPAIR_LIMIT = env_bounded_int(
    "BIRDLENSE_CATALOG_REPAIR_LIMIT",
    150,
    min_v=20,
    max_v=6000,
)


def record_system_resource_sample(flask_app) -> None:
    """Persist one SystemResourceSample row and prune old samples."""
    m = collect_live_system_metrics(flask_app)
    now = datetime.now(timezone.utc)
    gpu = m["gpu_percent"]
    row = SystemResourceSample(
        recorded_at=now,
        cpu_percent=float(m["cpu"]["percent"]),
        memory_percent=float(m["memory"]["percent"]),
        disk_percent=float(m["disk"]["percent"]),
        gpu_percent=float(gpu) if gpu is not None else None,
    )
    db.session.add(row)
    cutoff = now - timedelta(hours=SYSTEM_METRICS_RETENTION_HOURS)
    db.session.execute(
        delete(SystemResourceSample).where(
            SystemResourceSample.recorded_at < cutoff,
        )
    )
    db.session.commit()


def maybe_run_catalog_cards_repair(flask_app) -> None:
    """Run periodic catalog card repair when due (updates job_state status)."""
    if not CATALOG_REPAIR_AUTORUN_ENABLED:
        return
    now_ts = datetime.now(timezone.utc).timestamp()
    next_ts = job_state._catalog_cards_next_run_ts
    if next_ts and now_ts < next_ts:
        return
    with job_state._catalog_cards_lock:
        if job_state._catalog_cards_status.get("status") == "running":
            return
        job_state._catalog_cards_status.update(
            {
                "status": "running",
                "result": None,
                "error": None,
                "progress": {
                    "auto": True,
                    "limit": CATALOG_REPAIR_LIMIT,
                    "coverage_before": catalog_cards_coverage_snapshot(
                        app_config.get,
                    ),
                },
            }
        )
    try:
        with job_state._catalog_cards_lock:
            rotate = int(job_state._catalog_repair_priority_rotate)
        result = repair_catalog_cards(
            app_config.get,
            dry_run=False,
            limit=CATALOG_REPAIR_LIMIT,
            priority_rotate=rotate,
        )
        coverage_after = catalog_cards_coverage_snapshot(app_config.get)
        with job_state._catalog_cards_lock:
            job_state._catalog_repair_priority_rotate = (rotate + CATALOG_REPAIR_LIMIT) % 1_000_003
            job_state._catalog_cards_status.update(
                {
                    "status": "done",
                    "result": {
                        **result,
                        "auto": True,
                        "coverage_after": coverage_after,
                    },
                    "error": None,
                }
            )
    except Exception as e:
        db.session.rollback()
        with job_state._catalog_cards_lock:
            job_state._catalog_cards_status.update(
                {
                    "status": "error",
                    "result": None,
                    "error": str(e),
                }
            )
    finally:
        job_state._catalog_cards_next_run_ts = now_ts + (CATALOG_REPAIR_INTERVAL_MIN * 60)


def catalog_cards_schedule_state() -> dict:
    """Autorun schedule snapshot for species-registry status API."""
    now_ts = datetime.now(timezone.utc).timestamp()
    next_in = 0
    if job_state._catalog_cards_next_run_ts > now_ts:
        next_in = int(job_state._catalog_cards_next_run_ts - now_ts)
    with job_state._catalog_cards_lock:
        rotate = int(job_state._catalog_repair_priority_rotate)
    return {
        "autorun_enabled": CATALOG_REPAIR_AUTORUN_ENABLED,
        "interval_min": CATALOG_REPAIR_INTERVAL_MIN,
        "limit": CATALOG_REPAIR_LIMIT,
        "next_run_in_sec": next_in,
        "priority_rotate": rotate,
    }


def _system_metrics_sampler_worker(flask_app):
    """Daemon loop: sample metrics and maybe repair catalog cards."""
    import time

    while True:
        try:
            with flask_app.app_context():
                record_system_resource_sample(flask_app)
                maybe_run_catalog_cards_repair(flask_app)
        except Exception as e:
            flask_app.logger.warning("system metrics sampler: %s", e)
            try:
                db.session.rollback()
            except Exception as rb_exc:
                flask_app.logger.debug(
                    "system metrics sampler rollback failed: %s",
                    rb_exc,
                    exc_info=True,
                )
        time.sleep(SYSTEM_METRICS_SAMPLE_INTERVAL_SEC)


def start_system_metrics_sampler(flask_app) -> None:
    """Start background sampler thread once per process (unless disabled)."""
    disable = (
        os.environ.get(
            "DISABLE_SYSTEM_METRICS_SAMPLER",
            "",
        )
        .strip()
        .lower()
    )
    if disable in ("1", "true", "yes"):
        return
    with job_state._sampler_lock:
        if job_state._sampler_started:
            return
        job_state._sampler_started = True
    threading.Thread(
        target=_system_metrics_sampler_worker,
        args=(flask_app,),
        name="system-metrics-sampler",
        daemon=True,
    ).start()
