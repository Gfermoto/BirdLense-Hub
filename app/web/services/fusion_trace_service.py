"""Fusion decision trace из ActivityLog для UI (#272)."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from sqlalchemy import desc

from models import ActivityLog, Video, db


def _normalize_path(p: str) -> str:
    s = (p or "").strip().replace("\\", "/")
    while s.startswith("./"):
        s = s[2:]
    return s.rstrip("/")


def paths_match_recording(trace_path: str, video_path: str) -> bool:
    """Сопоставить путь из трассы и Video.video_path (суффикс / полное совпадение)."""
    a, b = _normalize_path(trace_path), _normalize_path(video_path)
    if not a or not b:
        return False
    if a == b:
        return True
    if a.endswith(b) or b.endswith(a):
        return True
    return False


def _persisted_track_rows(trace: dict[str, Any]) -> list[Any]:
    """Строки, попавшие в клип (video_detections): persisted_tracks или legacy accepted_tracks."""
    rows = trace.get("persisted_tracks")
    if rows is None:
        rows = trace.get("accepted_tracks")
    if not isinstance(rows, list):
        return []
    return rows


def _parse_log_data(raw: str | None) -> dict[str, Any] | None:
    if not raw:
        return None
    try:
        out = json.loads(raw)
    except (TypeError, ValueError):
        return None
    return out if isinstance(out, dict) else None


def find_decision_trace_for_video(video: Video) -> tuple[dict[str, Any] | None, datetime | None]:
    """
    Последняя запись decision_trace для ролика: сначала по video_id в payload,
    иначе по video_path (старые логи).
    """
    rows = (
        db.session.query(ActivityLog)
        .filter(ActivityLog.type == "decision_trace")
        .order_by(desc(ActivityLog.created_at))
        .limit(1000)
        .all()
    )
    vid = int(video.id)
    for row in rows:
        payload = _parse_log_data(row.data)
        if not payload:
            continue
        pvid = payload.get("video_id")
        if pvid is not None:
            try:
                if int(pvid) == vid:
                    return payload, row.created_at
            except (TypeError, ValueError):
                continue
    for row in rows:
        payload = _parse_log_data(row.data)
        if not payload:
            continue
        if paths_match_recording(str(payload.get("video_path") or ""), str(video.video_path or "")):
            return payload, row.created_at
    return None, None


def _fmt_num(v: Any, *, nd: int = 3) -> str:
    try:
        x = float(v)
    except (TypeError, ValueError):
        return str(v) if v is not None else ""
    if abs(x - round(x)) < 1e-9:
        return str(int(round(x)))
    return f"{x:.{nd}f}".rstrip("0").rstrip(".")


def build_track_step_rows(track: dict[str, Any]) -> list[dict[str, Any]]:
    """Плоский список шагов для одного трека (ключи для i18n в UI)."""
    steps: list[dict[str, Any]] = []

    def block(stage: str, items: list[tuple[str, Any]]):
        lines: list[dict[str, str]] = []
        for key, val in items:
            if val is None or val == "":
                continue
            lines.append({"field": key, "value": str(val)})
        if lines:
            steps.append({"stage": stage, "lines": lines})

    block(
        "detector",
        [
            ("detector_label", track.get("detector_label")),
            ("detector_confidence", _fmt_num(track.get("detector_confidence"))),
            ("detector_event_count", track.get("detector_event_count")),
        ],
    )
    block(
        "classifier",
        [
            ("classifier_species_name", track.get("classifier_species_name")),
            ("classifier_confidence", _fmt_num(track.get("classifier_confidence"))),
            ("classifier_event_count", track.get("classifier_event_count")),
            ("classifier_vote_share", _fmt_num(track.get("classifier_vote_share"))),
            ("classifier_threshold", _fmt_num(track.get("classifier_threshold"))),
        ],
    )
    block(
        "scores",
        [
            ("best_frame_score", _fmt_num(track.get("best_frame_score"))),
            ("key_frame_count", track.get("key_frame_count")),
            ("trust_band", track.get("trust_band")),
            ("decision_kind", track.get("decision_kind")),
            ("decision_reason", track.get("decision_reason")),
            ("evidence_state", track.get("evidence_state")),
            ("reject_reason_code", track.get("reject_reason_code")),
        ],
    )
    block(
        "audio",
        [
            ("audio_evidence", track.get("audio_evidence")),
            ("audio_support_count", track.get("audio_support_count")),
            ("audio_support_species", track.get("audio_support_species")),
            ("audio_conflict_species", track.get("audio_conflict_species")),
            ("audio_conflict_score", _fmt_num(track.get("audio_conflict_score"))),
            ("birdnet_prior", _fmt_num(track.get("_birdnet_prior"))),
        ],
    )
    block(
        "fusion",
        [
            ("fusion_used", track.get("_fusion_used")),
            ("fusion_score", _fmt_num(track.get("_fusion_score"))),
            ("multi_camera_count", track.get("_multi_camera_count")),
            ("multi_camera_support", track.get("_multi_camera_support")),
            ("frigate_standalone", track.get("frigate_standalone")),
            ("frigate_merge_suppressed", track.get("frigate_merge_suppressed")),
        ],
    )
    block(
        "outcome",
        [
            ("persisted_to_clip", track.get("persisted_to_clip")),
            ("species_name", track.get("species_name")),
            ("confidence", _fmt_num(track.get("confidence"))),
            ("accepted", track.get("accepted")),
            ("track_id", track.get("track_id")),
        ],
    )
    return steps


def build_fusion_trace_api_payload(video_id: int) -> tuple[dict[str, Any], int]:
    """Тело GET /videos/:id/fusion-trace и HTTP-код."""
    video = db.session.get(Video, video_id)
    if not video:
        return {"error": "Video not found"}, 404

    trace, log_at = find_decision_trace_for_video(video)
    if not trace:
        return {
            "available": False,
            "video_id": video_id,
            "video_path": video.video_path,
            "message": "no_decision_trace",
        }, 200

    persisted = _persisted_track_rows(trace)
    rejected = trace.get("rejected_tracks") or []
    tracks_out: list[dict[str, Any]] = []
    for row in persisted:
        if isinstance(row, dict):
            tracks_out.append(
                {
                    "bucket": "persisted",
                    "track_id": row.get("track_id"),
                    "species_name": row.get("species_name"),
                    "steps": build_track_step_rows(row),
                }
            )
    for row in rejected:
        if isinstance(row, dict):
            tracks_out.append(
                {
                    "bucket": "rejected",
                    "track_id": row.get("track_id"),
                    "species_name": row.get("species_name"),
                    "steps": build_track_step_rows(row),
                }
            )

    return {
        "available": True,
        "video_id": video_id,
        "video_path": video.video_path,
        "log_created_at": log_at.isoformat() if log_at else None,
        "trace": trace,
        "tracks": tracks_out,
    }, 200
