"""Disk↔DB reconcile: import orphan sessions, purge stale disk/DB (startup + scheduled)."""

from __future__ import annotations

import logging
import os
import threading
import time
from typing import TYPE_CHECKING

from app_config.app_config import app_config
from services.recording_orphan_inventory import summarize_orphan_recording_files
from services.recording_orphan_purge_service import apply_orphan_recording_purge
from services.system_diagnostics_service import apply_broken_video_rows_purge
from services.system_maintenance_service import run_recordings_scan

if TYPE_CHECKING:
    from flask import Flask

logger = logging.getLogger(__name__)

_scheduler_lock = threading.Lock()
_scheduler_started = False


def _cfg_bool(key: str, default: bool = True) -> bool:
    raw = app_config.get(key)
    if raw is None:
        return default
    if isinstance(raw, bool):
        return raw
    return str(raw).strip().lower() in ("1", "true", "yes", "on")


def _cfg_int(key: str, default: int, *, lo: int, hi: int) -> int:
    try:
        val = int(app_config.get(key) if app_config.get(key) is not None else default)
    except (TypeError, ValueError):
        val = default
    return max(lo, min(hi, val))


def _reconcile_enabled() -> bool:
    return _cfg_bool("reconcile.auto_run_enabled", True)


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


def _purge_orphan_disk_enabled() -> bool:
    return _cfg_bool("reconcile.purge_orphan_disk_enabled", True)


def _purge_broken_db_enabled() -> bool:
    return _cfg_bool("reconcile.purge_broken_db_rows_enabled", True)


def run_disk_db_reconcile(flask_app) -> dict[str, object]:
    """Import disk sessions missing from DB; purge stale orphans per policy."""
    with flask_app.app_context():
        orphan_before = summarize_orphan_recording_files()

        body, code = run_recordings_scan(flask_app)
        if code != 200:
            logger.warning("reconcile: scan failed code=%s body=%s", code, body)
            return {"ok": False, **(body if isinstance(body, dict) else {})}

        imported = int((body or {}).get("imported") or 0)
        purge_disk: dict[str, object] = {"deleted_count": 0, "freed_bytes": 0}
        if _purge_orphan_disk_enabled():
            limit = _cfg_int("reconcile.purge_orphan_disk_limit", 500, lo=1, hi=5000)
            try:
                purge_disk = apply_orphan_recording_purge(limit=limit)
            except Exception:
                logger.exception("reconcile: orphan disk purge failed")
                purge_disk = {"deleted_count": 0, "freed_bytes": 0, "error": "purge_failed"}

        purge_db: dict[str, object] = {"deleted_count": 0}
        if _purge_broken_db_enabled():
            limit = _cfg_int("reconcile.purge_broken_db_rows_limit", 100, lo=1, hi=5000)
            try:
                purge_db = apply_broken_video_rows_purge(limit=limit)
            except Exception:
                logger.exception("reconcile: broken db row purge failed")
                purge_db = {"deleted_count": 0, "error": "purge_failed"}

        orphan_after = summarize_orphan_recording_files()
        logger.info(
            "reconcile: imported=%s disk_purged=%s db_purged=%s orphan_gb_before=%.3f orphan_gb_after=%.3f",
            imported,
            purge_disk.get("deleted_count"),
            purge_db.get("deleted_count"),
            int(orphan_before.get("orphan_bytes") or 0) / (1024**3),
            int(orphan_after.get("orphan_bytes") or 0) / (1024**3),
        )
        return {
            "ok": True,
            **body,
            "orphan_before": orphan_before,
            "orphan_after": orphan_after,
            "purge_orphan_disk": purge_disk,
            "purge_broken_db_rows": purge_db,
        }


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
        "reconcile scheduler started (interval_h=%.1f enabled=%s purge_disk=%s purge_db=%s)",
        _reconcile_interval_hours(),
        _reconcile_enabled(),
        _purge_orphan_disk_enabled(),
        _purge_broken_db_enabled(),
    )
