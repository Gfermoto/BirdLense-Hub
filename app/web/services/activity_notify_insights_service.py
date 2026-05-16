"""Срезы ActivityLog: уведомления, ingest gate, suppress (#265)."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone

from models import ActivityLog, db

_log = logging.getLogger(__name__)


def activity_log_payload(row) -> dict | None:
    try:
        return row.data if isinstance(row.data, dict) else (json.loads(row.data) if row.data else {})
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        _log.debug(
            "activity_log_payload unreadable row id=%s: %s",
            getattr(row, "id", None),
            exc,
        )
        return {}


def notify_preview_rows_24h():
    now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
    preview_since = now_utc - timedelta(hours=24)
    return (
        db.session.query(ActivityLog)
        .filter(ActivityLog.type == "notify_preview", ActivityLog.created_at >= preview_since)
        .all()
    )


def notify_preview_generated_rows_24h():
    now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
    preview_since = now_utc - timedelta(hours=24)
    return (
        db.session.query(ActivityLog)
        .filter(
            ActivityLog.type == "notify_preview_generated",
            ActivityLog.created_at >= preview_since,
        )
        .all()
    )


def notify_preview_by_source_24h():
    preview_rows = notify_preview_rows_24h()
    preview_by_source = {
        "best_frame": 0,
        "bbox_crop": 0,
        "full_frame": 0,
        "none": 0,
        "unknown": 0,
    }
    for row in preview_rows:
        payload = activity_log_payload(row)
        src = str((payload or {}).get("preview_source") or "unknown")
        if src not in preview_by_source:
            src = "unknown"
        preview_by_source[src] += 1
    return preview_by_source


def notify_preview_generated_by_source_24h():
    preview_rows = notify_preview_generated_rows_24h()
    preview_by_source = {
        "best_frame": 0,
        "bbox_crop": 0,
        "full_frame": 0,
        "none": 0,
        "unknown": 0,
    }
    for row in preview_rows:
        payload = activity_log_payload(row)
        src = str((payload or {}).get("preview_source") or "unknown")
        if src not in preview_by_source:
            src = "unknown"
        preview_by_source[src] += 1
    return preview_by_source


def notify_fallback_by_reason_24h():
    preview_rows = notify_preview_rows_24h()
    by_reason = {
        "none": 0,
        "no_preview": 0,
        "no_preview_context": 0,
        "decode_failed": 0,
        "telegram_photo_failed": 0,
        "notifications_disabled": 0,
        "telegram_not_configured": 0,
        "config_disabled": 0,
        "unsafe_path": 0,
        "read_failed": 0,
        "telegram_text_failed": 0,
        "unexpected_error": 0,
        "unknown": 0,
    }
    for row in preview_rows:
        payload = activity_log_payload(row)
        reason = str((payload or {}).get("fallback_reason") or "none")
        if reason not in by_reason:
            reason = "unknown"
        by_reason[reason] += 1
    return by_reason


def notify_delivery_24h():
    preview_rows = notify_preview_rows_24h()
    by_delivery = {
        "photo": 0,
        "text": 0,
        "text_fallback": 0,
        "failed": 0,
        "skipped": 0,
        "unknown": 0,
    }
    for row in preview_rows:
        payload = activity_log_payload(row)
        delivery = str((payload or {}).get("telegram_delivery") or "unknown")
        if delivery not in by_delivery:
            delivery = "unknown"
        by_delivery[delivery] += 1
    return by_delivery


def activity_rows_since(activity_type: str, *, hours: int = 24):
    now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
    since = now_utc - timedelta(hours=max(1, int(hours or 24)))
    return (
        db.session.query(ActivityLog).filter(ActivityLog.type == activity_type, ActivityLog.created_at >= since).all()
    )


def ingest_gate_reason_counts_24h() -> dict[str, int]:
    rows = activity_rows_since("ingest_gate", hours=24)
    counts: dict[str, int] = {}
    for row in rows:
        payload = activity_log_payload(row)
        reason = str((payload or {}).get("reason") or "unknown")
        counts[reason] = counts.get(reason, 0) + 1
    return counts


def notify_suppressed_reason_counts_24h() -> dict[str, int]:
    rows = activity_rows_since("notify_suppressed", hours=24)
    counts: dict[str, int] = {}
    for row in rows:
        payload = activity_log_payload(row)
        reason = str((payload or {}).get("suppress_reason") or "unknown")
        counts[reason] = counts.get(reason, 0) + 1
    return counts
