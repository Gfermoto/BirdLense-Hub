"""YOLO detector live health for System dashboard (SOTA-05 / #496)."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import text

from models import db
from services.system_config_audit_service import _load_processor_runtime_snapshot


def _gauges_from_snapshot(snap: dict | None) -> dict[str, Any]:
    if not snap:
        return {}
    gauges = snap.get("gauges")
    return dict(gauges) if isinstance(gauges, dict) else {}


def _recent_blind_from_db(*, hours: int = 24) -> tuple[bool, float]:
    rows = db.session.execute(
        text(
            """
            SELECT yolo_blind_confirmed, payload_json
            FROM session_runtime_metrics
            WHERE datetime(created_at) >= datetime('now', :window)
            ORDER BY id DESC
            LIMIT 50
            """
        ),
        {"window": f"-{max(1, hours)} hours"},
    ).mappings()
    for row in rows:
        if int(row.get("yolo_blind_confirmed") or 0) == 1:
            score = 0.0
            try:
                payload = json.loads(str(row.get("payload_json") or "{}"))
                score = float(payload.get("yolo_blind_score") or 0.0)
            except (TypeError, ValueError, json.JSONDecodeError):
                pass
            return True, score
    return False, 0.0


def _evaluate_detector_health(
    gauges: dict[str, Any],
    *,
    recent_blind_confirmed: bool,
    recent_blind_score: float,
    blind_score_threshold: float,
) -> dict[str, Any]:
    status = str(gauges.get("yolo_blind_status") or "healthy")
    alert = int(gauges.get("yolo_blind_alert") or 0)
    phase = str(gauges.get("yolo_blind_phase_live") or "none")
    reasons: list[str] = []
    if recent_blind_confirmed or alert == 1 or status == "blind":
        status = "blind"
        reasons.append("live_alert_or_confirmed_blind")
    elif status == "degraded" or phase == "suspected":
        status = "degraded"
        reasons.append("blind_suspected_or_frigate_only_without_yolo")
    if recent_blind_score >= blind_score_threshold:
        reasons.append(f"session_blind_score>={blind_score_threshold}")
    return {
        "status": status,
        "yolo_blind_alert": bool(alert),
        "yolo_blind_phase": phase,
        "yolo_frames_with_tracks_session": int(gauges.get("yolo_frames_with_tracks_session") or 0),
        "session_extended_by_frigate_only": int(
            gauges.get("session_extended_by_frigate_only_session") or 0
        ),
        "stream_probe_width": gauges.get("stream_probe_width"),
        "stream_probe_height": gauges.get("stream_probe_height"),
        "stream_probe_fps": gauges.get("stream_probe_fps"),
        "reasons": reasons,
    }


def build_yolo_detector_health_payload(*, hours: int = 24) -> dict[str, Any]:
    """Merge processor runtime gauges with recent session blind signals."""
    snap = _load_processor_runtime_snapshot()
    gauges = _gauges_from_snapshot(snap)
    recent_blind, recent_score = _recent_blind_from_db(hours=hours)

    try:
        from app_config.app_config import app_config

        threshold = float(app_config.get("detection.yolo_blind_score_threshold") or 0.7)
    except Exception:
        threshold = 0.7

    health = _evaluate_detector_health(
        gauges,
        recent_blind_confirmed=recent_blind,
        recent_blind_score=recent_score,
        blind_score_threshold=threshold,
    )

    counters = snap.get("counters") if isinstance(snap, dict) and isinstance(snap.get("counters"), dict) else {}
    updated_at = None
    if isinstance(snap, dict):
        updated_at = snap.get("updated_at") or snap.get("flushed_at")

    return {
        "window_hours": max(1, min(int(hours), 168)),
        "updated_at": updated_at,
        "processor_snapshot_present": bool(snap),
        "gauges": {
            "yolo_blind_alert": gauges.get("yolo_blind_alert"),
            "yolo_blind_status": gauges.get("yolo_blind_status"),
            "yolo_blind_phase_live": gauges.get("yolo_blind_phase_live"),
            "yolo_frames_with_tracks_session": gauges.get("yolo_frames_with_tracks_session"),
            "session_extended_by_frigate_only_session": gauges.get(
                "session_extended_by_frigate_only_session"
            ),
            "yolo_blind_frigate_only_seconds": gauges.get("yolo_blind_frigate_only_seconds"),
            "stream_probe_width": gauges.get("stream_probe_width"),
            "stream_probe_height": gauges.get("stream_probe_height"),
            "stream_probe_fps": gauges.get("stream_probe_fps"),
            "last_runtime_profile": gauges.get("last_runtime_profile"),
        },
        "counters": {
            "slow_frame_processor_detect_total": counters.get("slow_frame_processor_detect_total"),
            "recording_capture_none_frame_total": counters.get("recording_capture_none_frame_total"),
        },
        "health": health,
        "config_hints": {
            "binary_imgsz": _safe_config_get("processor.binary_imgsz"),
            "inference_backend": _safe_config_get("processor.inference_backend"),
            "inference_device": _safe_config_get("processor.inference_device"),
            "min_confidence_binary": _safe_config_get("processor.min_confidence_binary"),
            "lores_wh": _safe_config_get("video.lores_wh"),
        },
        "runbook_path": "docs/ru/yolo-blind-runbook.ru.md",
    }


def _safe_config_get(key: str) -> Any:
    try:
        from app_config.app_config import app_config

        return app_config.get(key)
    except Exception:
        return None

