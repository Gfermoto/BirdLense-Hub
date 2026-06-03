"""Фоновый запуск retention по расписанию (cascade + max_gb + days)."""

from __future__ import annotations

import logging
import os
import threading
import time

from app_config.app_config import app_config

logger = logging.getLogger(__name__)

_scheduler_lock = threading.Lock()
_scheduler_started = False


def _retention_auto_enabled(cfg) -> bool:
    raw = cfg.get("retention.auto_run_enabled")
    if raw is None:
        return True
    if isinstance(raw, bool):
        return raw
    return str(raw).strip().lower() in ("1", "true", "yes", "on")


def _retention_interval_hours(cfg) -> float:
    try:
        hours = float(cfg.get("retention.auto_run_interval_hours") or 6)
    except (TypeError, ValueError):
        hours = 6.0
    return max(1.0, min(168.0, hours))


def maybe_run_scheduled_retention(flask_app) -> None:
    """Apply retention when due; no-op if disabled or mode=disabled."""
    cfg = app_config.config or {}
    if not _retention_auto_enabled(cfg):
        return
    mode = str(cfg.get("retention.mode") or "cascade").strip().lower()
    if mode == "disabled":
        return
    days = cfg.get("retention.days")
    max_gb = cfg.get("retention.max_gb")
    if not days and not max_gb:
        return

    from services.retention_service import run_retention

    with flask_app.app_context():
        deleted, freed = run_retention(dry_run=False, mode=mode)
        if deleted or freed:
            logger.info(
                "scheduled retention: deleted=%s freed_mb=%.1f mode=%s",
                deleted,
                freed / (1024 * 1024),
                mode,
            )


def _retention_scheduler_worker(flask_app) -> None:
    disable = os.environ.get("DISABLE_RETENTION_SCHEDULER", "").strip().lower()
    if disable in ("1", "true", "yes"):
        return
    while True:
        try:
            interval_h = _retention_interval_hours(app_config.config or {})
            maybe_run_scheduled_retention(flask_app)
        except Exception as exc:
            flask_app.logger.warning("retention scheduler: %s", exc)
        time.sleep(_retention_interval_hours(app_config.config or {}) * 3600.0)


def start_retention_scheduler(flask_app) -> None:
    """Start daemon retention loop once per process."""
    global _scheduler_started
    disable = os.environ.get("DISABLE_RETENTION_SCHEDULER", "").strip().lower()
    if disable in ("1", "true", "yes"):
        return
    with _scheduler_lock:
        if _scheduler_started:
            return
        _scheduler_started = True
    threading.Thread(
        target=_retention_scheduler_worker,
        args=(flask_app,),
        name="retention-scheduler",
        daemon=True,
    ).start()
    logger.info(
        "retention scheduler started (interval_h=%.1f enabled=%s)",
        _retention_interval_hours(app_config.config or {}),
        _retention_auto_enabled(app_config.config or {}),
    )
