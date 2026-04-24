"""Создание / обновление строки ActivityLog с эндпоинта процессора."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from models import ActivityLog, db


def upsert_activity_log_from_processor(data: dict, *, logger: logging.Logger) -> tuple[dict, int]:
    """Обработать JSON ``POST /api/processor/activity_log`` (без проверки секрета)."""
    try:
        activity_type = data.get("type")
        raw_data = data.get("data")
        activity_data = json.dumps(raw_data) if raw_data is not None else "{}"
        if len(activity_data) > 65536:
            return {"error": "Activity data too large (max 64 KB)"}, 400
        activity_id = data.get("id")
        if activity_id is not None:
            activity_id = int(activity_id)

        if not activity_type:
            return {"error": 'Field "type" is required'}, 400

        if activity_id is None:
            new_log = ActivityLog(type=activity_type, data=activity_data)
            db.session.add(new_log)
            db.session.commit()
            return {"message": "Activity log created successfully", "id": new_log.id}, 201
        log = db.session.get(ActivityLog, activity_id)
        if not log:
            return {"error": "Activity log with this ID not found"}, 404
        log.type = activity_type
        log.data = activity_data
        log.updated_at = datetime.now(timezone.utc)
        db.session.commit()
        return {"message": "Activity log updated successfully", "id": log.id}, 200
    except Exception as e:
        db.session.rollback()
        logger.exception("activity_log failed: %s", e)
        return {"error": "Internal server error"}, 500


__all__ = ["upsert_activity_log_from_processor"]
