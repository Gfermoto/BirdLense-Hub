"""Domain-level integrity metrics for recording, visits, review-only rows and species registry."""

from __future__ import annotations

import json
import logging
import os
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

import data_paths
from app_config.app_config import app_config
from models import ActivityLog, Species, SpeciesUnresolvedName, Video, VideoSpecies, db
from services.species_data_quality_service import find_duplicate_name_groups
from services.species_visit_maintenance_service import (
    _collect_large_gap_visit_splits,
    _collect_orphaned_visits,
    _collect_species_sync_actions,
)
from species_constants import GENERIC_BIRD_SPECIES

logger = logging.getLogger(__name__)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _norm_path(path: str | None) -> str:
    raw = str(path or "").strip().replace("\\", "/")
    while raw.startswith("./"):
        raw = raw[2:]
    return raw.rstrip("/")


def _clip_duplicate_gap_seconds() -> int:
    raw = app_config.get("processor.min_seconds_between_recordings")
    try:
        cooldown = int(float(raw or 0))
    except (TypeError, ValueError):
        cooldown = 0
    if cooldown > 0:
        return max(5, cooldown)
    try:
        visit_timeout = int(app_config.get("detection.dedup_window_seconds") or 60)
    except (TypeError, ValueError):
        visit_timeout = 60
    return max(15, min(visit_timeout, 120))


def _large_gap_seconds() -> int:
    try:
        visit_timeout = int(app_config.get("detection.dedup_window_seconds") or 60)
    except (TypeError, ValueError):
        visit_timeout = 60
    return max(300, visit_timeout * 4)


def _duplicate_video_groups_count() -> int:
    return int(
        db.session.query(Video.video_path, Video.start_time, Video.end_time, Video.processor_version)
        .filter(Video.deleted_at.is_(None))
        .group_by(Video.video_path, Video.start_time, Video.end_time, Video.processor_version)
        .having(db.func.count(Video.id) > 1)
        .count()
    )


def _duplicate_detection_groups_count() -> int:
    return int(
        db.session.query(
            VideoSpecies.video_id,
            VideoSpecies.species_id,
            VideoSpecies.start_time,
            VideoSpecies.end_time,
            VideoSpecies.source,
            VideoSpecies.detection_provider,
            VideoSpecies.track_id,
        )
        .group_by(
            VideoSpecies.video_id,
            VideoSpecies.species_id,
            VideoSpecies.start_time,
            VideoSpecies.end_time,
            VideoSpecies.source,
            VideoSpecies.detection_provider,
            VideoSpecies.track_id,
        )
        .having(db.func.count(VideoSpecies.id) > 1)
        .count()
    )


def _duplicate_clip_candidates(*, recent_hours: int = 24, limit: int = 12) -> list[dict[str, Any]]:
    cutoff = _utc_now() - timedelta(hours=max(1, int(recent_hours or 24)))
    rows = (
        db.session.query(
            VideoSpecies.video_id,
            Video.start_time,
            Video.end_time,
            Species.id,
            Species.name,
        )
        .join(Video, Video.id == VideoSpecies.video_id)
        .join(Species, Species.id == VideoSpecies.species_id)
        .filter(
            VideoSpecies.source == "video",
            VideoSpecies.species_visit_id.isnot(None),
            Video.start_time >= cutoff,
            Species.name != GENERIC_BIRD_SPECIES,
        )
        .order_by(Species.id.asc(), Video.start_time.asc(), Video.id.asc())
        .all()
    )

    deduped: dict[int, list[dict[str, Any]]] = defaultdict(list)
    seen_pairs: set[tuple[int, int]] = set()
    for video_id, start_time, end_time, species_id, species_name in rows:
        key = (int(species_id), int(video_id))
        if key in seen_pairs:
            continue
        seen_pairs.add(key)
        deduped[int(species_id)].append(
            {
                "video_id": int(video_id),
                "species_id": int(species_id),
                "species_name": species_name,
                "start_time": start_time,
                "end_time": end_time,
            }
        )

    out: list[dict[str, Any]] = []
    gap_threshold = timedelta(seconds=_clip_duplicate_gap_seconds())
    for clips in deduped.values():
        prev: dict[str, Any] | None = None
        for clip in clips:
            if prev is None:
                prev = clip
                continue
            gap = clip["start_time"] - prev["end_time"]
            if timedelta(0) <= gap <= gap_threshold:
                out.append(
                    {
                        "species_name": clip["species_name"],
                        "previous_video_id": prev["video_id"],
                        "video_id": clip["video_id"],
                        "gap_seconds": round(gap.total_seconds(), 3),
                        "previous_end_time": prev["end_time"].isoformat() if prev["end_time"] else None,
                        "start_time": clip["start_time"].isoformat() if clip["start_time"] else None,
                    }
                )
                if len(out) >= limit:
                    return out
            prev = clip
    return out


def _recent_unresolved_names(limit: int = 10) -> list[dict[str, Any]]:
    rows = (
        SpeciesUnresolvedName.query.order_by(SpeciesUnresolvedName.last_seen_at.desc())
        .limit(max(1, int(limit or 10)))
        .all()
    )
    return [
        {
            "raw_name": row.raw_name,
            "normalized_key": row.normalized_key,
            "source": row.source,
            "reason": row.reason,
            "seen_count": int(row.seen_count or 0),
            "last_seen_at": row.last_seen_at.isoformat() if row.last_seen_at else None,
        }
        for row in rows
    ]


def _recent_review_only_detections(limit: int = 10) -> list[dict[str, Any]]:
    rows = (
        db.session.query(VideoSpecies, Species, Video)
        .join(Species, Species.id == VideoSpecies.species_id)
        .join(Video, Video.id == VideoSpecies.video_id)
        .filter(
            VideoSpecies.source == "video",
            VideoSpecies.species_visit_id.is_(None),
        )
        .order_by(VideoSpecies.created_at.desc(), VideoSpecies.id.desc())
        .limit(max(1, int(limit or 10)))
        .all()
    )
    items: list[dict[str, Any]] = []
    for detection, species, video in rows:
        items.append(
            {
                "detection_id": detection.id,
                "video_id": detection.video_id,
                "species_name": species.name,
                "confidence": float(detection.confidence or 0.0),
                "detection_provider": detection.detection_provider,
                "created_at": detection.created_at.isoformat() if detection.created_at else None,
                "video_path": video.video_path,
            }
        )
    return items


def _thresholds_safe() -> dict[str, Any]:
    try:
        return {
            "clip_duplicate_gap_seconds": _clip_duplicate_gap_seconds(),
            "visit_large_gap_seconds": _large_gap_seconds(),
            "visit_timeout_seconds": int(app_config.get("detection.dedup_window_seconds") or 60),
            "min_seconds_between_recordings": float(app_config.get("processor.min_seconds_between_recordings") or 0),
        }
    except (TypeError, ValueError):
        return {
            "clip_duplicate_gap_seconds": 15,
            "visit_large_gap_seconds": 300,
            "visit_timeout_seconds": 60,
            "min_seconds_between_recordings": 0.0,
        }


def _recent_detection_track_metrics(hours: int = 24) -> dict[str, Any]:
    cutoff = _utc_now() - timedelta(hours=max(1, int(hours or 24)))
    rows = (
        db.session.query(VideoSpecies)
        .filter(
            VideoSpecies.source == "video",
            VideoSpecies.created_at >= cutoff,
        )
        .all()
    )
    total = len(rows)
    with_frames = sum(1 for row in rows if bool(row.frames))
    yolo_provider = sum(1 for row in rows if str(row.detection_provider or "").strip().lower() == "yolo")
    return {
        "video_detections_24h": total,
        "video_detections_with_frames_24h": with_frames,
        "video_detections_with_frames_ratio_24h": (with_frames / total) if total else None,
        "video_detections_primary_yolo_24h": yolo_provider,
        "video_detections_primary_yolo_ratio_24h": (yolo_provider / total) if total else None,
    }


def _recent_trigger_camera_metrics(hours: int = 24, limit: int = 1000) -> dict[str, Any]:
    cutoff = _utc_now() - timedelta(hours=max(1, int(hours or 24)))
    rows = (
        db.session.query(ActivityLog)
        .filter(
            ActivityLog.type == "decision_trace",
            ActivityLog.created_at >= cutoff,
        )
        .order_by(ActivityLog.id.desc())
        .limit(max(1, int(limit or 1000)))
        .all()
    )
    triggered_camera_counts: dict[str, int] = defaultdict(int)
    active_trigger_counts: dict[str, int] = defaultdict(int)
    session_extended_by_frigate_only_sum = 0
    scanned = 0
    for row in rows:
        try:
            payload = json.loads(row.data or "{}")
        except Exception:
            continue
        rc = payload.get("recording_context") or {}
        rs = rc.get("runtime_signals") or {}
        cam = str(rc.get("triggered_camera") or "none")
        triggered_camera_counts[cam] += 1
        for trg in rc.get("active_triggers") or []:
            active_trigger_counts[str(trg)] += 1
        try:
            session_extended_by_frigate_only_sum += int(rs.get("session_extended_by_frigate_only") or 0)
        except (TypeError, ValueError):
            pass
        scanned += 1
    return {
        "decision_trace_rows_24h": scanned,
        "session_extended_by_frigate_only_sum_24h": session_extended_by_frigate_only_sum,
        "triggered_camera_counts_24h": dict(sorted(triggered_camera_counts.items())),
        "active_trigger_counts_24h": dict(sorted(active_trigger_counts.items())),
    }


def _recent_runtime_backend_metrics(hours: int = 24, limit: int = 1000) -> dict[str, Any]:
    cutoff = _utc_now() - timedelta(hours=max(1, int(hours or 24)))
    rows = (
        db.session.query(ActivityLog)
        .filter(
            ActivityLog.type == "decision_trace",
            ActivityLog.created_at >= cutoff,
        )
        .order_by(ActivityLog.id.desc())
        .limit(max(1, int(limit or 1000)))
        .all()
    )
    binary_backend_counts: dict[str, int] = defaultdict(int)
    classifier_backend_counts: dict[str, int] = defaultdict(int)
    inference_device_counts: dict[str, int] = defaultdict(int)
    video_encoding_counts: dict[str, int] = defaultdict(int)
    capture_backend_counts: dict[str, int] = defaultdict(int)
    reid_device_counts: dict[str, int] = defaultdict(int)
    reid_model_counts: dict[str, int] = defaultdict(int)
    timeline: list[tuple[datetime | None, str]] = []
    scanned = 0
    for row in rows:
        try:
            payload = json.loads(row.data or "{}")
        except Exception:
            continue
        scanned += 1
        pf = payload.get("pipeline_fingerprint") or {}
        binary_backend = str(((pf.get("binary_model") or {}).get("inference_backend")) or "unknown").strip().lower()
        classifier_backend = (
            str(((pf.get("classifier_model") or {}).get("inference_backend")) or "unknown").strip().lower()
        )
        binary_backend_counts[binary_backend] += 1
        classifier_backend_counts[classifier_backend] += 1
        policy = (payload.get("recording_context") or {}).get("policy_snapshot") or {}
        inference_device = str(policy.get("inference_device") or "unknown").strip().lower()
        video_encoding = str(policy.get("video_encoding") or "unknown").strip().lower()
        capture_backend = str(policy.get("video_capture_backend") or "unknown").strip().lower()
        reid_device = str(policy.get("reid_device") or "unknown").strip().lower()
        if video_encoding and video_encoding != "unknown":
            timeline.append((row.created_at, video_encoding))
        inference_device_counts[inference_device] += 1
        video_encoding_counts[video_encoding] += 1
        capture_backend_counts[capture_backend] += 1
        reid_device_counts[reid_device] += 1
        for track in payload.get("persisted_tracks") or []:
            model = str((track or {}).get("reid_model") or "").strip()
            if model:
                reid_model_counts[model] += 1
    transitions = 0
    prev: str | None = None
    for _, encoding in sorted(timeline, key=lambda item: item[0] or datetime.min.replace(tzinfo=timezone.utc)):
        if prev is None:
            prev = encoding
            continue
        if encoding != prev:
            transitions += 1
            prev = encoding
    return {
        "decision_trace_rows_runtime_backend_24h": scanned,
        "binary_backend_counts_24h": dict(sorted(binary_backend_counts.items())),
        "classifier_backend_counts_24h": dict(sorted(classifier_backend_counts.items())),
        "inference_device_counts_24h": dict(sorted(inference_device_counts.items())),
        "video_encoding_counts_24h": dict(sorted(video_encoding_counts.items())),
        "capture_backend_counts_24h": dict(sorted(capture_backend_counts.items())),
        "reid_device_counts_24h": dict(sorted(reid_device_counts.items())),
        "reid_model_counts_24h": dict(sorted(reid_model_counts.items())),
        "video_encoding_transitions_24h": int(transitions),
    }


def _build_reliability_alerts(
    *,
    ingest_gate_reason_metrics: dict[str, Any],
    runtime_backend_metrics: dict[str, Any],
) -> dict[str, Any]:
    reason_counts = ingest_gate_reason_metrics.get("ingest_gate_reason_code_counts_24h") or {}
    rec_file_missing = int(reason_counts.get("REC_FILE_MISSING") or 0)
    rec_file_unplayable = int(reason_counts.get("REC_FILE_UNPLAYABLE") or 0)
    artifact_failures = rec_file_missing + rec_file_unplayable
    unknown_ingest = int(ingest_gate_reason_metrics.get("ingest_gate_unknown_reason_rows_24h") or 0)
    transitions = int(runtime_backend_metrics.get("video_encoding_transitions_24h") or 0)
    return {
        "thresholds": {
            "recording_artifact_failures_24h_max": 0,
            "video_encoding_transitions_24h_warn": 4,
            "unknown_ingest_gate_rows_24h_warn": 0,
        },
        "metrics": {
            "recording_artifact_failures_24h": int(artifact_failures),
            "recording_file_missing_24h": int(rec_file_missing),
            "recording_file_unplayable_24h": int(rec_file_unplayable),
            "video_encoding_transitions_24h": int(transitions),
            "unknown_ingest_gate_rows_24h": int(unknown_ingest),
        },
        "alerts": {
            "recording_artifact_failures": bool(artifact_failures > 0),
            "video_encoding_flapping": bool(transitions >= 4),
            "unknown_ingest_gate_reasons": bool(unknown_ingest > 0),
        },
    }


def _parse_payload_time(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _day_night_bucket(ts: datetime | None) -> str:
    if ts is None:
        return "unknown"
    return "day" if 6 <= ts.hour < 18 else "night"


def _normalize_parity_reason_token(value: Any, *, prefix: str = "REJECT_") -> str | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    token = raw.upper().replace("-", "_").replace(" ", "_")
    if token.startswith(
        (
            "REC_",
            "FUSION_",
            "REJECT_",
            "YOLO_",
            "FRIGATE_",
            "MQTT_",
            "GATE_",
            "UNKNOWN_",
        )
    ):
        return token
    return f"{prefix}{token}" if prefix else token


def _parity_reason_from_decision_payload(payload: dict[str, Any], ingest_reason_by_path: dict[str, str]) -> str:
    trace_path = _norm_path(payload.get("video_path"))
    if trace_path:
        mapped = ingest_reason_by_path.get(trace_path)
        if mapped:
            return mapped

    rejected_tracks = payload.get("rejected_tracks")
    if isinstance(rejected_tracks, list) and rejected_tracks:
        reason_counts: dict[str, int] = defaultdict(int)
        for row in rejected_tracks:
            if not isinstance(row, dict):
                continue
            reason = (
                _normalize_parity_reason_token(row.get("reject_reason_code"), prefix="")
                or _normalize_parity_reason_token(row.get("decision_reason"))
                or _normalize_parity_reason_token(row.get("arbitration_reason"))
            )
            if reason:
                reason_counts[reason] += 1
        if reason_counts:
            return sorted(reason_counts.items(), key=lambda x: (-x[1], x[0]))[0][0]

    outcome = payload.get("outcome_summary") if isinstance(payload.get("outcome_summary"), dict) else {}
    rejected_count = int(outcome.get("rejected_track_count") or payload.get("rejected_track_count") or 0)
    if rejected_count > 0:
        return "REJECTED_NO_REASON"

    recording_context = (
        payload.get("recording_context") if isinstance(payload.get("recording_context"), dict) else {}
    )
    runtime_signals = (
        recording_context.get("runtime_signals")
        if isinstance(recording_context.get("runtime_signals"), dict)
        else {}
    )
    if runtime_signals.get("yolo_ran") is False:
        return "YOLO_NOT_RUN"
    if runtime_signals.get("yolo_ran") is True and runtime_signals.get("yolo_track_found") is False:
        return "YOLO_NO_TRACK"

    return "UNKNOWN_NO_PERSIST"


def _recent_parity_diagnostics_metrics(hours: int = 24, limit: int = 5000) -> dict[str, Any]:
    cutoff = _utc_now() - timedelta(hours=max(1, int(hours or 24)))
    decision_rows = (
        db.session.query(ActivityLog)
        .filter(
            ActivityLog.type == "decision_trace",
            ActivityLog.created_at >= cutoff,
        )
        .order_by(ActivityLog.id.desc())
        .limit(max(1, int(limit or 5000)))
        .all()
    )
    ingest_rows = (
        db.session.query(ActivityLog)
        .filter(
            ActivityLog.type == "ingest_gate",
            ActivityLog.created_at >= cutoff,
        )
        .order_by(ActivityLog.id.desc())
        .limit(max(1, int(limit or 5000)))
        .all()
    )

    ingest_reason_by_path: dict[str, str] = {}
    for row in ingest_rows:
        try:
            payload = json.loads(row.data or "{}")
        except Exception:
            continue
        if not isinstance(payload, dict):
            continue
        code = str(payload.get("reason_code") or "").strip().upper() or "UNKNOWN"
        path = _norm_path(payload.get("video_path"))
        if path and path not in ingest_reason_by_path:
            ingest_reason_by_path[path] = code

    total_windows = 0
    matched_windows = 0
    mismatched_windows = 0
    cause_counts: dict[str, int] = defaultdict(int)
    camera_split: dict[str, dict[str, int]] = defaultdict(
        lambda: {
            "windows": 0,
            "matched": 0,
            "mismatched": 0,
            "day_windows": 0,
            "day_mismatched": 0,
            "night_windows": 0,
            "night_mismatched": 0,
            "unknown_windows": 0,
            "unknown_mismatched": 0,
        }
    )
    for row in decision_rows:
        try:
            payload = json.loads(row.data or "{}")
        except Exception:
            continue
        if not isinstance(payload, dict):
            continue
        recording_context = (
            payload.get("recording_context") if isinstance(payload.get("recording_context"), dict) else {}
        )
        active_triggers = recording_context.get("active_triggers")
        active_triggers_l = [
            str(x or "").strip().lower() for x in (active_triggers if isinstance(active_triggers, list) else [])
        ]
        triggered_by = str(recording_context.get("triggered_by") or "").strip().lower()
        is_frigate = triggered_by == "frigate" or any("frigate" == trg for trg in active_triggers_l)
        if not is_frigate:
            continue

        total_windows += 1
        camera = str(recording_context.get("triggered_camera") or "unknown").strip() or "unknown"
        clip_start = _parse_payload_time(payload.get("start_time"))
        bucket = _day_night_bucket(clip_start)
        entry = camera_split[camera]
        entry["windows"] += 1
        entry[f"{bucket}_windows"] += 1

        outcome = payload.get("outcome_summary") if isinstance(payload.get("outcome_summary"), dict) else {}
        persisted_count = int(outcome.get("persisted_track_count") or payload.get("persisted_track_count") or 0)
        if persisted_count > 0:
            matched_windows += 1
            entry["matched"] += 1
            continue

        mismatched_windows += 1
        entry["mismatched"] += 1
        entry[f"{bucket}_mismatched"] += 1
        reason = _parity_reason_from_decision_payload(payload, ingest_reason_by_path)
        cause_counts[reason] += 1

    camera_rows: list[dict[str, Any]] = []
    for camera, item in sorted(camera_split.items(), key=lambda x: (-x[1]["mismatched"], x[0])):
        windows = int(item["windows"] or 0)
        mismatches = int(item["mismatched"] or 0)
        camera_rows.append(
            {
                "camera": camera,
                "windows": windows,
                "matched": int(item["matched"] or 0),
                "mismatched": mismatches,
                "mismatch_rate": (mismatches / windows) if windows else None,
                "day_windows": int(item["day_windows"] or 0),
                "day_mismatched": int(item["day_mismatched"] or 0),
                "night_windows": int(item["night_windows"] or 0),
                "night_mismatched": int(item["night_mismatched"] or 0),
                "unknown_windows": int(item["unknown_windows"] or 0),
                "unknown_mismatched": int(item["unknown_mismatched"] or 0),
            }
        )
    parity_hotspots = [
        row
        for row in camera_rows
        if int(row.get("windows") or 0) >= 10 and float(row.get("mismatch_rate") or 0.0) >= 0.2
    ]
    top_causes = dict(sorted(cause_counts.items(), key=lambda x: (-x[1], x[0]))[:10])
    return {
        "parity_frigate_windows_24h": int(total_windows),
        "parity_hub_matched_windows_24h": int(matched_windows),
        "parity_mismatched_windows_24h": int(mismatched_windows),
        "parity_mismatch_rate_24h": (mismatched_windows / total_windows) if total_windows else None,
        "parity_hotspot_count_24h": len(parity_hotspots),
        "parity_top_mismatch_reasons_24h": top_causes,
        "parity_camera_split_24h": camera_rows[:20],
        "parity_hotspots_24h": parity_hotspots[:10],
    }


def _recent_ingest_gate_reason_metrics(hours: int = 24, limit: int = 2000) -> dict[str, Any]:
    cutoff = _utc_now() - timedelta(hours=max(1, int(hours or 24)))
    rows = (
        db.session.query(ActivityLog)
        .filter(
            ActivityLog.type == "ingest_gate",
            ActivityLog.created_at >= cutoff,
        )
        .order_by(ActivityLog.id.desc())
        .limit(max(1, int(limit or 2000)))
        .all()
    )
    reason_counts: dict[str, int] = defaultdict(int)
    unknown = 0
    scanned = 0
    for row in rows:
        scanned += 1
        try:
            payload = json.loads(row.data or "{}")
        except Exception:
            unknown += 1
            continue
        code = str((payload or {}).get("reason_code") or "").strip().upper()
        if not code:
            unknown += 1
            continue
        reason_counts[code] += 1
    return {
        "ingest_gate_rows_24h": scanned,
        "ingest_gate_known_reason_rows_24h": int(sum(reason_counts.values())),
        "ingest_gate_unknown_reason_rows_24h": int(unknown),
        "ingest_gate_reason_code_counts_24h": dict(sorted(reason_counts.items())),
    }


def _processor_runtime_funnel_metrics() -> dict[str, int]:
    """Counters from processor runtime snapshot (recording funnel)."""
    path = os.path.join(data_paths.data_dir(), "diagnostics", "processor_runtime_stats.json")
    if not os.path.isfile(path):
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            snap = json.load(f)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {}
    counters = snap.get("counters") if isinstance(snap, dict) and isinstance(snap.get("counters"), dict) else {}
    keys = (
        "recording_session_total",
        "recording_persisted_total",
        "recording_clips_deleted_empty_total",
        "recording_frigate_trigger_salvage_total",
    )
    out: dict[str, int] = {}
    for key in keys:
        try:
            out[key] = int(counters.get(key) or 0)
        except (TypeError, ValueError):
            out[key] = 0
    return out


def build_domain_health_payload() -> tuple[dict[str, Any], int]:
    contract = "2026-04-polish-v1"
    contracts_block = {
        "review_only_detection_has_no_visit": True,
        "species_visit_is_derived_from_video_species": True,
        "duplicate_clip_candidates_are_gap_based": True,
    }
    try:
        orphaned_visits = _collect_orphaned_visits(db.session)
        species_sync_actions = _collect_species_sync_actions(db.session)
        duplicate_groups = find_duplicate_name_groups(
            db.session,
            limit_groups=500,
            skip_inactive_empty_groups=False,
        )
        large_gap_plans = _collect_large_gap_visit_splits(db.session, _large_gap_seconds())
        duplicate_clip_candidates = _duplicate_clip_candidates(limit=200)
        review_only_count = (
            db.session.query(VideoSpecies)
            .filter(
                VideoSpecies.source == "video",
                VideoSpecies.species_visit_id.is_(None),
            )
            .count()
        )
        duplicate_video_groups = _duplicate_video_groups_count()
        duplicate_detection_groups = _duplicate_detection_groups_count()
        detection_track_metrics = _recent_detection_track_metrics()
        trigger_camera_metrics = _recent_trigger_camera_metrics()
        runtime_backend_metrics = _recent_runtime_backend_metrics()
        ingest_gate_reason_metrics = _recent_ingest_gate_reason_metrics()
        parity_diagnostics_metrics = _recent_parity_diagnostics_metrics()
        processor_funnel_metrics = _processor_runtime_funnel_metrics()
        reliability_alerts = _build_reliability_alerts(
            ingest_gate_reason_metrics=ingest_gate_reason_metrics,
            runtime_backend_metrics=runtime_backend_metrics,
        )

        payload: dict[str, Any] = {
            "domain_contract_version": contract,
            "thresholds": {
                "clip_duplicate_gap_seconds": _clip_duplicate_gap_seconds(),
                "visit_large_gap_seconds": _large_gap_seconds(),
                "visit_timeout_seconds": int(app_config.get("detection.dedup_window_seconds") or 60),
                "min_seconds_between_recordings": float(
                    app_config.get("processor.min_seconds_between_recordings") or 0
                ),
            },
            "metrics": {
                "orphaned_visits": len(orphaned_visits),
                "visit_species_mismatches": len(species_sync_actions),
                "duplicate_species_name_groups": len(duplicate_groups),
                "large_gap_visits": len(large_gap_plans),
                "review_only_video_detections": int(review_only_count or 0),
                "unresolved_species_names": SpeciesUnresolvedName.query.count(),
                "duplicate_clip_candidates_24h": len(duplicate_clip_candidates),
                "duplicate_video_groups": duplicate_video_groups,
                "duplicate_detection_groups": duplicate_detection_groups,
                **detection_track_metrics,
                **{
                    "decision_trace_rows_24h": trigger_camera_metrics["decision_trace_rows_24h"],
                    "session_extended_by_frigate_only_sum_24h": trigger_camera_metrics[
                        "session_extended_by_frigate_only_sum_24h"
                    ],
                    "decision_trace_rows_runtime_backend_24h": runtime_backend_metrics[
                        "decision_trace_rows_runtime_backend_24h"
                    ],
                    "ingest_gate_rows_24h": ingest_gate_reason_metrics["ingest_gate_rows_24h"],
                    "ingest_gate_known_reason_rows_24h": ingest_gate_reason_metrics[
                        "ingest_gate_known_reason_rows_24h"
                    ],
                    "ingest_gate_unknown_reason_rows_24h": ingest_gate_reason_metrics[
                        "ingest_gate_unknown_reason_rows_24h"
                    ],
                    "parity_frigate_windows_24h": parity_diagnostics_metrics["parity_frigate_windows_24h"],
                    "parity_hub_matched_windows_24h": parity_diagnostics_metrics["parity_hub_matched_windows_24h"],
                    "parity_mismatched_windows_24h": parity_diagnostics_metrics["parity_mismatched_windows_24h"],
                    "parity_mismatch_rate_24h": parity_diagnostics_metrics["parity_mismatch_rate_24h"],
                    "parity_hotspot_count_24h": parity_diagnostics_metrics["parity_hotspot_count_24h"],
                },
                **processor_funnel_metrics,
            },
            "samples": {
                "duplicate_clip_candidates": duplicate_clip_candidates[:12],
                "recent_unresolved_species": _recent_unresolved_names(),
                "recent_review_only_video_detections": _recent_review_only_detections(),
                "triggered_camera_counts_24h": trigger_camera_metrics["triggered_camera_counts_24h"],
                "active_trigger_counts_24h": trigger_camera_metrics["active_trigger_counts_24h"],
                "binary_backend_counts_24h": runtime_backend_metrics["binary_backend_counts_24h"],
                "classifier_backend_counts_24h": runtime_backend_metrics["classifier_backend_counts_24h"],
                "inference_device_counts_24h": runtime_backend_metrics["inference_device_counts_24h"],
                "video_encoding_counts_24h": runtime_backend_metrics["video_encoding_counts_24h"],
                "capture_backend_counts_24h": runtime_backend_metrics["capture_backend_counts_24h"],
                "reid_device_counts_24h": runtime_backend_metrics["reid_device_counts_24h"],
                "reid_model_counts_24h": runtime_backend_metrics["reid_model_counts_24h"],
                "ingest_gate_reason_code_counts_24h": ingest_gate_reason_metrics["ingest_gate_reason_code_counts_24h"],
                "parity_top_mismatch_reasons_24h": parity_diagnostics_metrics["parity_top_mismatch_reasons_24h"],
                "parity_camera_split_24h": parity_diagnostics_metrics["parity_camera_split_24h"],
                "parity_hotspots_24h": parity_diagnostics_metrics["parity_hotspots_24h"],
            },
            "contracts": contracts_block,
            "reliability_alerts": reliability_alerts,
            "strict_quality": {
                "duplicate_video_groups_ok": duplicate_video_groups == 0,
                "duplicate_detection_groups_ok": duplicate_detection_groups == 0,
                "duplicate_clip_candidates_ok": len(duplicate_clip_candidates) == 0,
                "visit_species_mismatches_ok": len(species_sync_actions) == 0,
                "video_detections_with_frames_ratio_ok": (
                    (detection_track_metrics.get("video_detections_with_frames_ratio_24h") or 0.0) >= 0.9
                    if detection_track_metrics.get("video_detections_with_frames_ratio_24h") is not None
                    else False
                ),
                "video_detections_primary_yolo_ratio_ok": (
                    (detection_track_metrics.get("video_detections_primary_yolo_ratio_24h") or 0.0) >= 0.8
                    if detection_track_metrics.get("video_detections_primary_yolo_ratio_24h") is not None
                    else False
                ),
                "strict_quality_ready": (
                    duplicate_video_groups == 0
                    and duplicate_detection_groups == 0
                    and len(duplicate_clip_candidates) == 0
                    and len(species_sync_actions) == 0
                    and (
                        (detection_track_metrics.get("video_detections_with_frames_ratio_24h") or 0.0) >= 0.9
                        if detection_track_metrics.get("video_detections_with_frames_ratio_24h") is not None
                        else False
                    )
                    and (
                        (detection_track_metrics.get("video_detections_primary_yolo_ratio_24h") or 0.0) >= 0.8
                        if detection_track_metrics.get("video_detections_primary_yolo_ratio_24h") is not None
                        else False
                    )
                ),
            },
        }
        return payload, 200
    except Exception as exc:
        logger.exception("domain-health snapshot failed")
        err_type = type(exc).__name__
        return {
            "domain_contract_version": contract,
            "snapshot_degraded": True,
            "snapshot_error_class": err_type,
            "thresholds": _thresholds_safe(),
            "metrics": {
                "orphaned_visits": None,
                "visit_species_mismatches": None,
                "duplicate_species_name_groups": None,
                "large_gap_visits": None,
                "review_only_video_detections": None,
                "unresolved_species_names": None,
                "duplicate_clip_candidates_24h": None,
                "duplicate_video_groups": None,
                "duplicate_detection_groups": None,
                "video_detections_24h": None,
                "video_detections_with_frames_24h": None,
                "video_detections_with_frames_ratio_24h": None,
                "video_detections_primary_yolo_24h": None,
                "video_detections_primary_yolo_ratio_24h": None,
                "decision_trace_rows_24h": None,
                "session_extended_by_frigate_only_sum_24h": None,
                "decision_trace_rows_runtime_backend_24h": None,
                "ingest_gate_rows_24h": None,
                "ingest_gate_known_reason_rows_24h": None,
                "ingest_gate_unknown_reason_rows_24h": None,
                "parity_frigate_windows_24h": None,
                "parity_hub_matched_windows_24h": None,
                "parity_mismatched_windows_24h": None,
                "parity_mismatch_rate_24h": None,
                "parity_hotspot_count_24h": None,
            },
            "samples": {
                "duplicate_clip_candidates": [],
                "recent_unresolved_species": [],
                "recent_review_only_video_detections": [],
                "triggered_camera_counts_24h": {},
                "active_trigger_counts_24h": {},
                "binary_backend_counts_24h": {},
                "classifier_backend_counts_24h": {},
                "inference_device_counts_24h": {},
                "video_encoding_counts_24h": {},
                "capture_backend_counts_24h": {},
                "reid_device_counts_24h": {},
                "reid_model_counts_24h": {},
                "ingest_gate_reason_code_counts_24h": {},
                "parity_top_mismatch_reasons_24h": {},
                "parity_camera_split_24h": [],
                "parity_hotspots_24h": [],
            },
            "contracts": contracts_block,
            "reliability_alerts": {
                "thresholds": {
                    "recording_artifact_failures_24h_max": 0,
                    "video_encoding_transitions_24h_warn": 4,
                    "unknown_ingest_gate_rows_24h_warn": 0,
                },
                "metrics": {
                    "recording_artifact_failures_24h": None,
                    "recording_file_missing_24h": None,
                    "recording_file_unplayable_24h": None,
                    "video_encoding_transitions_24h": None,
                    "unknown_ingest_gate_rows_24h": None,
                },
                "alerts": {
                    "recording_artifact_failures": False,
                    "video_encoding_flapping": False,
                    "unknown_ingest_gate_reasons": False,
                },
            },
            "strict_quality": {
                "duplicate_video_groups_ok": False,
                "duplicate_detection_groups_ok": False,
                "duplicate_clip_candidates_ok": False,
                "visit_species_mismatches_ok": False,
                "video_detections_with_frames_ratio_ok": False,
                "video_detections_primary_yolo_ratio_ok": False,
                "strict_quality_ready": False,
            },
        }, 200
