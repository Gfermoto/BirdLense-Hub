"""Disk↔DB reconcile: import orphan sessions (startup + scheduled)."""

from __future__ import annotations

import logging
import os
import threading
import time
from typing import TYPE_CHECKING

from app_config.app_config import app_config
from services.system_maintenance_service import run_recordings_scan

if TYPE_CHECKING:
    from flask import Flask

logger = logging.getLogger(__name__)

_scheduler_lock = threading.Lock()
_scheduler_started = False


def _reconcile_enabled() -> bool:
    raw = app_config.get("reconcile.auto_run_enabled")
    if raw is None:
        return True
    if isinstance(raw, bool):
        return raw
    return str(raw).strip().lower() in ("1", "true", "yes", "on")


def _reconcile_interval_hours() -> float:
    try:
        hours = float(app_config.get("reconcile.auto_run_interval_hours") or 24)
    except (TypeError, ValueError):
        hours = 24.0
    return max(1.0, min(168.0, hours))


def _startup_delay_seconds() -> float:
    try:
        delay = float(app_config.get("reconcile.startup_delay_seconds") or 30)
    except (TypeError, ValueError):
        delay = 30.0
    return max(0.0, min(600.0, delay))


def run_disk_db_reconcile(flask_app) -> dict[str, object]:
    """Import disk sessions missing from DB; returns scan summary."""
    with flask_app.app_context():
        body, code = run_recordings_scan(flask_app)
        if code != 200:
            logger.warning("reconcile: scan failed code=%s body=%s", code, body)
            return {"ok": False, **(body if isinstance(body, dict) else {})}
        imported = int((body or {}).get("imported") or 0)
        logger.info(
            "reconcile: imported=%s cleaned_legacy=%s",
            imported,
            (body or {}).get("cleaned_legacy_placeholders"),
        )
        return {"ok": True, **body}


def maybe_run_startup_reconcile(flask_app) -> None:
    if not _reconcile_enabled():
        return
    delay = _startup_delay_seconds()
    if delay > 0:
        time.sleep(delay)
    try:
        run_disk_db_reconcile(flask_app)
    except Exception:
        logger.exception("startup reconcile failed")


def _reconcile_worker(flask_app) -> None:
    disable = os.environ.get("DISABLE_RECONCILE_SCHEDULER", "").strip().lower()
    if disable in ("1", "true", "yes"):
        return
    maybe_run_startup_reconcile(flask_app)
    while True:
        try:
            interval_h = _reconcile_interval_hours()
            time.sleep(interval_h * 3600.0)
            if _reconcile_enabled():
                run_disk_db_reconcile(flask_app)
        except Exception as exc:
            flask_app.logger.warning("reconcile scheduler: %s", exc)


def start_reconcile_scheduler(flask_app) -> None:
    """Startup + periodic disk↔DB sync."""
    global _scheduler_started
    disable = os.environ.get("DISABLE_RECONCILE_SCHEDULER", "").strip().lower()
    if disable in ("1", "true", "yes"):
        return
    with _scheduler_lock:
        if _scheduler_started:
            return
        _scheduler_started = True
    threading.Thread(
        target=_reconcile_worker,
        args=(flask_app,),
        name="reconcile-scheduler",
        daemon=True,
    ).start()
    logger.info(
        "reconcile scheduler started (interval_h=%.1f enabled=%s)",
        _reconcile_interval_hours(),
        _reconcile_enabled(),
    )
