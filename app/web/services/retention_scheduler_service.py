"""Фоновая проверка retention: удаление только при нарушении days или max_gb."""

from __future__ import annotations

import logging
import os
import threading
import time

from app_config.app_config import app_config

logger = logging.getLogger(__name__)

_scheduler_lock = threading.Lock()
_scheduler_started = False


def _retention_auto_enabled() -> bool:
    raw = app_config.get("retention.auto_run_enabled")
    if raw is None:
        return False
    if isinstance(raw, bool):
        return raw
    return str(raw).strip().lower() in ("1", "true", "yes", "on")


def _retention_interval_hours() -> float:
    try:
        hours = float(app_config.get("retention.auto_run_interval_hours") or 6)
    except (TypeError, ValueError):
        hours = 6.0
    return max(1.0, min(168.0, hours))


def maybe_run_scheduled_retention(flask_app) -> None:
    """Check retention thresholds on interval; trim oldest/expired rows only until policy is met."""
    if not _retention_auto_enabled():
        return
    mode = str(app_config.get("retention.mode") or "cascade").strip().lower()
    if mode == "disabled":
        return
    days = app_config.get("retention.days")
    max_gb = app_config.get("retention.max_gb")
    if not days and not max_gb:
        return

    from services.quota_maintainer import quota_deletion_pending, run_quota_trim

    with flask_app.app_context():
        pending, reason = quota_deletion_pending()
        if not pending:
            logger.info("scheduled retention: skipped, within policy (mode=%s)", mode)
            return

        deleted, freed = run_quota_trim(dry_run=False, policy_scope=reason)
        if deleted or freed:
            logger.info(
                "scheduled retention: reason=%s deleted=%s freed_mb=%.1f mode=%s",
                reason,
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
            interval_h = _retention_interval_hours()
            maybe_run_scheduled_retention(flask_app)
        except Exception as exc:
            flask_app.logger.warning("retention scheduler: %s", exc)
        time.sleep(_retention_interval_hours() * 3600.0)


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
        _retention_interval_hours(),
        _retention_auto_enabled(),
    )
