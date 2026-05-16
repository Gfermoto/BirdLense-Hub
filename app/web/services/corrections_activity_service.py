"""Нормализация источника/scope, лог species_correction, список recent (#293)."""

from __future__ import annotations

import json
import logging
from typing import Any

from models import ActivityLog
from util import ensure_utc

logger = logging.getLogger(__name__)


def normalize_correction_source(value: Any) -> str:
    src = (value or "").strip().lower()
    if src in ("unknowns", "video"):
        return src
    return "other"


def normalize_apply_scope(value: Any, *, default: str = "single_track") -> str:
    scope = (value or "").strip().lower()
    if scope in ("single_track", "whole_visit", "legacy_fanout"):
        return scope
    return default


def write_correction_activity(
    session,
    *,
    action: str,
    source: str,
    detection_id: int,
    from_species_name=None,
    to_species_name=None,
    updated_count=None,
    apply_scope=None,
    reason=None,
    video_id=None,
    track_id=None,
    species_visit_id=None,
    from_species_id=None,
    to_species_id=None,
) -> None:
    payload = {
        "action": action,
        "source": source,
        "detection_id": detection_id,
        "from_species_name": from_species_name,
        "to_species_name": to_species_name,
        "updated_count": updated_count,
        "apply_scope": apply_scope,
        "reason": reason,
        "video_id": video_id,
        "track_id": track_id,
        "species_visit_id": species_visit_id,
        "from_species_id": from_species_id,
        "to_species_id": to_species_id,
    }
    try:
        log = ActivityLog(
            type="species_correction",
            data=json.dumps(payload, ensure_ascii=False),
        )
        session.add(log)
        session.commit()
    except Exception:
        session.rollback()
        logger.exception("Failed to write species_correction activity log")


def fetch_recent_species_corrections(session, limit: int) -> list[dict]:
    limit = min(max(limit, 1), 100)
    rows = (
        session.query(ActivityLog)
        .filter_by(type="species_correction")
        .order_by(ActivityLog.created_at.desc())
        .limit(limit)
        .all()
    )
    out: list[dict] = []
    for row in rows:
        parsed: dict = {}
        if row.data:
            try:
                parsed = json.loads(row.data)
            except (json.JSONDecodeError, TypeError, ValueError) as exc:
                parsed = {}
                logger.debug(
                    "species_correction history payload unreadable id=%s: %s",
                    getattr(row, "id", None),
                    exc,
                )
        out.append(
            {
                "id": row.id,
                "created_at": ensure_utc(row.created_at).isoformat() if row.created_at else None,
                "action": parsed.get("action") or "correct_species",
                "source": parsed.get("source") or "other",
                "detection_id": parsed.get("detection_id"),
                "from_species_name": parsed.get("from_species_name"),
                "to_species_name": parsed.get("to_species_name"),
                "updated_count": parsed.get("updated_count"),
                "apply_scope": parsed.get("apply_scope") or "legacy_fanout",
                "reason": parsed.get("reason"),
                "video_id": parsed.get("video_id"),
                "track_id": parsed.get("track_id"),
                "species_visit_id": parsed.get("species_visit_id"),
            }
        )
    return out
