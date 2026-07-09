"""Ответы для config-audit, логов, activity, старт регерации треков (#293)."""

from __future__ import annotations

import logging
import threading
from typing import TYPE_CHECKING, Any

from app_config.app_config import app_config
from models import Video, db
from services.processor_logs_service import (
    clamp_processor_log_line_count,
    read_processor_log_tail,
)
from services.system_activity_service import (
    SystemActivityMonthError,
    fetch_system_activity_daily_uptime,
    parse_system_activity_month,
)
from services.system_config_audit_service import build_system_config_audit_payload
from services.system_track_regen_worker import run_regenerate_tracks_worker

import routes.ui_system_jobs_state as job_state

if TYPE_CHECKING:
    from flask import Flask

_log = logging.getLogger(__name__)


def build_config_audit_payload() -> tuple[dict, int]:
    payload = build_system_config_audit_payload(
        user_config_file=app_config.user_config_file,
        default_config_file=app_config.default_config_file,
        app_config_get=app_config.get,
    )
    return payload, 200


def processor_logs_tail_http_response(lines_raw: Any) -> tuple[Any, int]:
    lines = clamp_processor_log_line_count(lines_raw)
    try:
        return read_processor_log_tail(lines), 200
    except OSError:
        _log.exception("Get processor logs failed")
        return {"error": "Failed to read logs", "lines": []}, 500


def compute_system_activity_uptime(session: Any, month: str) -> tuple[Any, int]:
    try:
        start_date, end_date = parse_system_activity_month(month)
    except SystemActivityMonthError as exc:
        return {"error": str(exc)}, 400
    out = fetch_system_activity_daily_uptime(session, start_date, end_date)
    return out, 200


def start_single_video_track_regeneration(
    flask_app: Flask,
    video_id: int,
    body: dict | None,
) -> tuple[dict, int]:
    video = db.session.get(Video, video_id)
    if not video:
        return {"error": "Video not found"}, 404
    data = body or {}
    force = bool(data.get("force", False))
    with job_state._regenerate_tracks_lock:
        if job_state._regenerate_tracks_status["status"] == "running":
            return {
                "error": "Track regeneration already in progress",
                "status": job_state._regenerate_tracks_status,
            }, 409
        job_state._regenerate_tracks_cancel_requested = False
        job_state._regenerate_tracks_status = {
            "status": "running",
            "result": None,
            "error": None,
            "progress": {
                "processed": 0,
                "total": 1,
                "generated": 0,
                "failed": 0,
                "skipped": 0,
                "current_video": video.video_path,
                "current_video_id": video_id,
                "active_request_video_id": video_id,
                "phase": "queued",
            },
        }
    threading.Thread(
        target=run_regenerate_tracks_worker,
        args=(flask_app, force, None, None, None, [video_id], []),
        daemon=True,
    ).start()
    return {
        "message": "Track regeneration started for this video.",
        "started": True,
        "video_id": video_id,
    }, 202
