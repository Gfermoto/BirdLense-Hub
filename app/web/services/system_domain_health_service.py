"""Domain-level integrity metrics for recording, visits, review-only rows and species registry."""

from __future__ import annotations

import json
import logging
import os
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any
import math

import data_paths
from app_config.app_config import app_config
from models import (
    ActivityLog,
    DetectorHealthEvent,
    SessionRuntimeMetrics,
    Species,
    SpeciesUnresolvedName,
    SpeciesVisit,
    Video,
    VideoSpecies,
    db,
)
from services.species_data_quality_service import find_duplicate_name_groups
from services.system_operational_status import strict_quality_ratio_ok
from services.species_visit_maintenance_service import (
    _collect_large_gap_visit_splits,
    _collect_orphaned_visits,
    _collect_species_sync_actions,
)
from species_constants import GENERIC_BIRD_SPECIES

logger = logging.getLogger(__name__)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _safe_div(n: float, d: float) -> float | None:
    if d <= 0.0:
        return None
    return float(n / d)


def _percentile(values: list[float], p: float) -> float | None:
    if not values:
        return None
    vals = sorted(float(v) for v in values)
    if p <= 0:
        return vals[0]
    if p >= 100:
        return vals[-1]
    idx = (len(vals) - 1) * (p / 100.0)
    lo = int(math.floor(idx))
    hi = int(math.ceil(idx))
    if lo == hi:
        return vals[lo]
    return vals[lo] * (hi - idx) + vals[hi] * (idx - lo)


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


def _parse_track_frames(raw: Any) -> list[dict[str, Any]]:
    if not raw:
        return []
    try:
        parsed = json.loads(str(raw))
    except (TypeError, ValueError, json.JSONDecodeError):
        return []
    if not isinstance(parsed, list):
        return []
    return [frame for frame in parsed if isinstance(frame, dict)]


def _frame_center_diag(frame: dict[str, Any]) -> tuple[float, float, float, float] | None:
    bbox = frame.get("bbox")
    if not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
        return None
    try:
        x1, y1, x2, y2 = [float(v) for v in bbox]
    except (TypeError, ValueError):
        return None
    w = max(0.0, x2 - x1)
    h = max(0.0, y2 - y1)
    diag = math.sqrt((w * w) + (h * h))
    return ((x1 + x2) / 2.0, (y1 + y2) / 2.0, max(diag, 1.0), 1.0)


def _track_row_quality(row: VideoSpecies, *, gap_sec: float = 0.8) -> dict[str, Any]:
    frames = _parse_track_frames(getattr(row, "frames", None))
    if not frames:
        return {
            "frame_count": 0,
            "gap_count": 0,
            "avg_jitter": 0.0,
            "stability_score": 0.35,
        }

    gap_count = 0
    jitter_sum = 0.0
    jitter_steps = 0
    prev_t: float | None = None
    prev_center: tuple[float, float, float] | None = None
    for idx, frame in enumerate(frames):
        t_raw = frame.get("t")
        t_curr: float | None = None
        try:
            t_curr = float(t_raw) if t_raw is not None else float(idx)
        except (TypeError, ValueError):
            t_curr = float(idx)

        center_raw = _frame_center_diag(frame)
        center_curr = (center_raw[0], center_raw[1], center_raw[2]) if center_raw is not None else None

        if prev_t is not None and (t_curr - prev_t) > float(gap_sec):
            gap_count += 1
        if prev_center is not None and center_curr is not None:
            dx = center_curr[0] - prev_center[0]
            dy = center_curr[1] - prev_center[1]
            disp = math.sqrt((dx * dx) + (dy * dy))
            norm = min(1.0, disp / max(prev_center[2], 1.0))
            jitter_sum += norm
            jitter_steps += 1

        prev_t = t_curr
        prev_center = center_curr

    avg_jitter = (jitter_sum / jitter_steps) if jitter_steps > 0 else 0.0
    frame_count = len(frames)
    score = 1.0
    score -= min(0.5, float(gap_count) * 0.2)
    score -= min(0.35, float(avg_jitter) * 0.7)
    if frame_count <= 1:
        score -= 0.35
    elif frame_count >= 6:
        score += 0.05
    score = max(0.0, min(1.0, score))
    return {
        "frame_count": frame_count,
        "gap_count": int(gap_count),
        "avg_jitter": float(round(avg_jitter, 4)),
        "stability_score": float(round(score, 4)),
    }


def _recent_track_quality_metrics(hours: int = 24) -> dict[str, Any]:
    cutoff = _utc_now() - timedelta(hours=max(1, int(hours or 24)))
    return _track_quality_metrics_between(cutoff)


def _track_quality_metrics_between(
    start_ts: datetime,
    end_ts: datetime | None = None,
    *,
    limit: int = 4000,
) -> dict[str, Any]:
    q = db.session.query(VideoSpecies).filter(
        VideoSpecies.source == "video",
        VideoSpecies.track_id.isnot(None),
        VideoSpecies.created_at >= start_ts,
    )
    if end_ts is not None:
        q = q.filter(VideoSpecies.created_at < end_ts)
    rows = q.order_by(VideoSpecies.created_at.desc(), VideoSpecies.id.desc()).limit(max(1, int(limit or 4000))).all()

    total = len(rows)
    with_frames = 0
    fragmented = 0
    with_gaps = 0
    low_stability = 0
    scores: list[float] = []
    jitter_values: list[float] = []
    unstable_examples: list[dict[str, Any]] = []

    for row in rows:
        quality = _track_row_quality(row)
        frame_count = int(quality["frame_count"])
        gap_count = int(quality["gap_count"])
        avg_jitter = float(quality["avg_jitter"])
        score = float(quality["stability_score"])
        if frame_count > 0:
            with_frames += 1
        if frame_count <= 1 or gap_count > 0:
            fragmented += 1
        if gap_count > 0:
            with_gaps += 1
        if score < 0.55:
            low_stability += 1
        if frame_count > 0:
            scores.append(score)
            jitter_values.append(avg_jitter)
        unstable_examples.append(
            {
                "detection_id": int(row.id),
                "video_id": int(row.video_id),
                "track_id": (int(row.track_id) if row.track_id is not None else None),
                "detection_provider": row.detection_provider,
                "frame_count": frame_count,
                "gap_count": gap_count,
                "avg_jitter": avg_jitter,
                "stability_score": score,
            }
        )

    scores_sorted = sorted(scores)
    p50 = None
    if scores_sorted:
        mid = (len(scores_sorted) - 1) // 2
        p50 = float(scores_sorted[mid])
    top_unstable = sorted(
        unstable_examples,
        key=lambda item: (
            float(item.get("stability_score") or 0.0),
            -int(item.get("gap_count") or 0),
            int(item.get("frame_count") or 0),
        ),
    )[:8]

    return {
        "metrics": {
            "track_rows_with_id_24h": int(total),
            "track_rows_with_frame_series_24h": int(with_frames),
            "track_rows_fragmented_24h": int(fragmented),
            "track_rows_fragmented_ratio_24h": ((fragmented / total) if total else None),
            "track_rows_with_gaps_24h": int(with_gaps),
            "track_rows_with_gaps_ratio_24h": ((with_gaps / total) if total else None),
            "track_avg_jitter_24h": (round(sum(jitter_values) / len(jitter_values), 4) if jitter_values else None),
            "track_stability_score_avg_24h": (round(sum(scores) / len(scores), 4) if scores else None),
            "track_stability_score_p50_24h": p50,
            "track_stability_low_count_24h": int(low_stability),
            "track_stability_low_ratio_24h": ((low_stability / total) if total else None),
        },
        "samples": {
            "track_unstable_examples_24h": top_unstable,
        },
    }


def _track_quality_regression_metrics(hours: int = 24) -> dict[str, Any]:
    cutoff = _utc_now() - timedelta(hours=max(1, int(hours or 24)))
    prev_start = cutoff - timedelta(hours=max(1, int(hours or 24)))
    current = _track_quality_metrics_between(cutoff)
    previous = _track_quality_metrics_between(prev_start, cutoff)
    cm = current.get("metrics") or {}
    pm = previous.get("metrics") or {}

    def _delta(key: str) -> float | None:
        cur = cm.get(key)
        prv = pm.get(key)
        if cur is None or prv is None:
            return None
        try:
            return round(float(cur) - float(prv), 4)
        except (TypeError, ValueError):
            return None

    sample_cur = int(cm.get("track_rows_with_id_24h") or 0)
    sample_prev = int(pm.get("track_rows_with_id_24h") or 0)
    stability_delta = _delta("track_stability_score_avg_24h")
    fragmented_delta = _delta("track_rows_fragmented_ratio_24h")
    gaps_delta = _delta("track_rows_with_gaps_ratio_24h")
    regression_reasons: list[str] = []
    if sample_cur >= 30 and sample_prev >= 30 and stability_delta is not None and stability_delta <= -0.05:
        regression_reasons.append("stability_drop")
    if sample_cur >= 30 and sample_prev >= 30 and fragmented_delta is not None and fragmented_delta >= 0.05:
        regression_reasons.append("fragmentation_rise")
    if sample_cur >= 30 and sample_prev >= 30 and gaps_delta is not None and gaps_delta >= 0.05:
        regression_reasons.append("gap_rise")

    return {
        "metrics": {
            "track_stability_score_delta_prev_24h": stability_delta,
            "track_fragmented_ratio_delta_prev_24h": fragmented_delta,
            "track_gaps_ratio_delta_prev_24h": gaps_delta,
            "track_quality_regression_24h": bool(regression_reasons),
        },
        "samples": {
            "track_quality_regression_24h": {
                "current_sample": sample_cur,
                "previous_sample": sample_prev,
                "stability_delta": stability_delta,
                "fragmented_delta": fragmented_delta,
                "gaps_delta": gaps_delta,
                "reasons": regression_reasons,
            },
        },
    }


def _recent_event_lifecycle_metrics(
    hours: int = 24,
    *,
    limit: int = 1000,
) -> dict[str, Any]:
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
    windows = 0
    detected = 0
    entered = 0
    rejected_only = 0
    no_tracks = 0
    persisted_total = 0
    rejected_total = 0
    top_reject_reasons: dict[str, int] = defaultdict(int)
    for row in rows:
        try:
            payload = json.loads(row.data or "{}")
        except Exception:
            continue
        if not isinstance(payload, dict):
            continue
        windows += 1
        persisted_rows = payload.get("persisted_tracks")
        if not isinstance(persisted_rows, list):
            persisted_rows = payload.get("accepted_tracks")
        if not isinstance(persisted_rows, list):
            persisted_rows = []
        rejected_rows = payload.get("rejected_tracks")
        if not isinstance(rejected_rows, list):
            rejected_rows = []

        p_count = len(persisted_rows)
        r_count = len(rejected_rows)
        total_rows = p_count + r_count
        if total_rows > 0:
            detected += 1
        if p_count > 0:
            entered += 1
        elif r_count > 0:
            rejected_only += 1
        else:
            no_tracks += 1
        persisted_total += p_count
        rejected_total += r_count

        for rr in rejected_rows:
            if not isinstance(rr, dict):
                continue
            reason = str(rr.get("reject_reason_code") or rr.get("decision_reason") or "UNKNOWN").strip().upper()
            if reason:
                top_reject_reasons[reason] += 1

    return {
        "metrics": {
            "lifecycle_windows_24h": windows,
            "lifecycle_detected_windows_24h": detected,
            "lifecycle_entered_windows_24h": entered,
            "lifecycle_rejected_only_windows_24h": rejected_only,
            "lifecycle_no_tracks_windows_24h": no_tracks,
            "lifecycle_detect_rate_24h": (detected / windows) if windows else None,
            "lifecycle_enter_rate_24h": (entered / windows) if windows else None,
            "lifecycle_rejected_only_rate_24h": ((rejected_only / windows) if windows else None),
            "lifecycle_avg_persisted_tracks_per_window_24h": (round(persisted_total / windows, 3) if windows else None),
            "lifecycle_avg_rejected_tracks_per_window_24h": (round(rejected_total / windows, 3) if windows else None),
        },
        "samples": {
            "lifecycle_outcome_counts_24h": {
                "entered": entered,
                "rejected_only": rejected_only,
                "no_tracks": no_tracks,
            },
            "lifecycle_top_reject_reasons_24h": dict(
                sorted(
                    top_reject_reasons.items(),
                    key=lambda x: (-x[1], x[0]),
                )[:10]
            ),
        },
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


def _recent_runtime_session_slo_metrics(
    hours: int = 24,
    *,
    limit: int = 4000,
) -> dict[str, Any]:
    cutoff = _utc_now() - timedelta(hours=max(1, int(hours or 24)))
    rows = (
        db.session.query(SessionRuntimeMetrics)
        .filter(SessionRuntimeMetrics.created_at >= cutoff)
        .order_by(SessionRuntimeMetrics.created_at.desc(), SessionRuntimeMetrics.id.desc())
        .limit(max(1, int(limit or 4000)))
        .all()
    )
    total = len(rows)
    fps_values: list[float] = []
    skipped_ratios: list[float] = []
    latency_values: list[float] = []
    by_camera: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "sessions": 0,
            "fps_values": [],
            "skipped_ratios": [],
            "latency_values": [],
            "video_file_not_ok": 0,
        }
    )
    for row in rows:
        camera = str(row.camera_id or "unknown").strip() or "unknown"
        cam = by_camera[camera]
        cam["sessions"] += 1
        duration_s = float(row.duration_s or 0.0)
        yolo_frames_ran = int(row.yolo_frames_ran or 0)
        frames_seen = int(row.frames_seen or 0)
        if duration_s > 0.0:
            fps = float(yolo_frames_ran) / duration_s
            fps_values.append(fps)
            cam["fps_values"].append(fps)
        if frames_seen > 0:
            skipped = max(0, frames_seen - yolo_frames_ran)
            ratio = skipped / float(frames_seen)
            skipped_ratios.append(ratio)
            cam["skipped_ratios"].append(ratio)
        if not bool(row.video_file_ok):
            cam["video_file_not_ok"] += 1
        payload = {}
        try:
            payload = json.loads(row.payload_json or "{}")
        except Exception:
            payload = {}
        if isinstance(payload, dict):
            raw_latency = payload.get("pipeline_latency_ms")
            if raw_latency is None:
                raw_latency = payload.get("pipeline_p95_ms")
            if raw_latency is None:
                raw_latency = payload.get("frame_processing_ms")
            if raw_latency is None:
                raw_latency = payload.get("avg_pipeline_latency_ms")
            try:
                if raw_latency is not None:
                    val = float(raw_latency)
                    if val >= 0:
                        latency_values.append(val)
                        cam["latency_values"].append(val)
            except (TypeError, ValueError):
                pass

    detector_events = db.session.query(DetectorHealthEvent).filter(DetectorHealthEvent.created_at >= cutoff).all()
    reconnect_events = 0
    backpressure_events = 0
    for evt in detector_events:
        et = str(evt.event_type or "").strip().lower()
        if "reconnect" in et:
            reconnect_events += 1
        if "backpressure" in et or "queue" in et:
            backpressure_events += 1

    per_camera: list[dict[str, Any]] = []
    for camera, data in by_camera.items():
        sessions = int(data["sessions"] or 0)
        fps_avg = _safe_div(sum(data["fps_values"]), float(len(data["fps_values"])))
        skipped_avg = _safe_div(
            sum(data["skipped_ratios"]),
            float(len(data["skipped_ratios"])),
        )
        latency_p95 = _percentile(data["latency_values"], 95.0)
        fps_ok = (fps_avg is None) or (fps_avg >= 7.0)
        skip_ok = (skipped_avg is None) or (skipped_avg <= 0.05)
        lat_ok = (latency_p95 is None) or (latency_p95 <= 2500.0)
        file_ok = int(data["video_file_not_ok"] or 0) == 0
        status = "ok" if fps_ok and skip_ok and lat_ok and file_ok else "warn"
        per_camera.append(
            {
                "camera": camera,
                "sessions_24h": sessions,
                "sustained_fps_avg_24h": (round(float(fps_avg), 3) if fps_avg is not None else None),
                "skipped_ratio_avg_24h": (round(float(skipped_avg), 4) if skipped_avg is not None else None),
                "pipeline_latency_p95_ms_24h": (round(float(latency_p95), 3) if latency_p95 is not None else None),
                "video_file_not_ok_24h": int(data["video_file_not_ok"] or 0),
                "status": status,
            }
        )
    per_camera = sorted(
        per_camera,
        key=lambda item: (
            item.get("status") != "warn",
            -(item.get("sessions_24h") or 0),
            item.get("camera") or "",
        ),
    )

    return {
        "metrics": {
            "runtime_sessions_24h": int(total),
            "runtime_sustained_fps_avg_24h": (round(sum(fps_values) / len(fps_values), 3) if fps_values else None),
            "runtime_sustained_fps_p50_24h": _percentile(fps_values, 50.0),
            "runtime_skipped_ratio_avg_24h": (
                round(sum(skipped_ratios) / len(skipped_ratios), 4) if skipped_ratios else None
            ),
            "runtime_pipeline_latency_p95_ms_24h": _percentile(latency_values, 95.0),
            "runtime_reconnect_events_24h": int(reconnect_events),
            "runtime_backpressure_events_24h": int(backpressure_events),
        },
        "samples": {
            "runtime_slo_per_camera_24h": per_camera[:20],
        },
    }


def _build_slo_dashboard(
    *,
    metrics: dict[str, Any],
    samples: dict[str, Any],
    reliability_alerts: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    fps_avg = metrics.get("runtime_sustained_fps_avg_24h")
    skipped_avg = metrics.get("runtime_skipped_ratio_avg_24h")
    latency_p95 = metrics.get("runtime_pipeline_latency_p95_ms_24h")
    reconnect_events = int(metrics.get("runtime_reconnect_events_24h") or 0)
    backpressure_events = int(metrics.get("runtime_backpressure_events_24h") or 0)
    per_camera = samples.get("runtime_slo_per_camera_24h") or []
    per_camera_warn = sum(1 for row in per_camera if str((row or {}).get("status") or "") == "warn")
    alerts = (reliability_alerts.get("alerts") or {}) if isinstance(reliability_alerts, dict) else {}
    alerting_rules = [
        {
            "id": "sustained_fps_floor",
            "severity": "critical",
            "metric": "runtime_sustained_fps_avg_24h",
            "operator": ">=",
            "threshold": 7.0,
            "value": fps_avg,
            "breach": (fps_avg is not None and float(fps_avg) < 7.0),
            "runbook": "docs/runbooks/runtime-slo-stability.md#sustained-fps-floor",
        },
        {
            "id": "skipped_ratio_ceiling",
            "severity": "warning",
            "metric": "runtime_skipped_ratio_avg_24h",
            "operator": "<=",
            "threshold": 0.05,
            "value": skipped_avg,
            "breach": (skipped_avg is not None and float(skipped_avg) > 0.05),
            "runbook": "docs/runbooks/runtime-slo-stability.md#skipped-ratio",
        },
        {
            "id": "pipeline_latency_p95",
            "severity": "warning",
            "metric": "runtime_pipeline_latency_p95_ms_24h",
            "operator": "<=",
            "threshold": 2500.0,
            "value": latency_p95,
            "breach": (latency_p95 is not None and float(latency_p95) > 2500.0),
            "runbook": "docs/runbooks/runtime-slo-stability.md#pipeline-latency-p95",
        },
        {
            "id": "reconnect_resilience",
            "severity": "warning",
            "metric": "runtime_reconnect_events_24h",
            "operator": "<=",
            "threshold": 25,
            "value": reconnect_events,
            "breach": reconnect_events > 25,
            "runbook": "docs/runbooks/runtime-slo-stability.md#reconnect-resilience",
        },
        {
            "id": "backpressure_control",
            "severity": "warning",
            "metric": "runtime_backpressure_events_24h",
            "operator": "<=",
            "threshold": 25,
            "value": backpressure_events,
            "breach": backpressure_events > 25,
            "runbook": "docs/runbooks/runtime-slo-stability.md#backpressure-control",
        },
    ]
    breaches = [rule["id"] for rule in alerting_rules if rule.get("breach")]
    if bool(alerts.get("data_stagnation")):
        breaches.append("data_stagnation")
    if bool(alerts.get("recording_artifact_failures")):
        breaches.append("recording_artifact_failures")
    dashboard = {
        "schema": "runtime_slo_dashboard@v1",
        "targets": {
            "sustained_fps_min": 7.0,
            "skipped_ratio_max": 0.05,
            "pipeline_latency_p95_ms_max": 2500.0,
        },
        "snapshot": {
            "runtime_sessions_24h": int(metrics.get("runtime_sessions_24h") or 0),
            "sustained_fps_avg_24h": fps_avg,
            "skipped_ratio_avg_24h": skipped_avg,
            "pipeline_latency_p95_ms_24h": latency_p95,
            "reconnect_events_24h": reconnect_events,
            "backpressure_events_24h": backpressure_events,
            "per_camera_warn_count_24h": int(per_camera_warn),
        },
        "status": {
            "ok": len(breaches) == 0,
            "breaches": breaches,
        },
    }
    return dashboard, alerting_rules


def _build_reliability_alerts(
    *,
    ingest_gate_reason_metrics: dict[str, Any],
    runtime_backend_metrics: dict[str, Any],
    stagnation_metrics: dict[str, Any],
) -> dict[str, Any]:
    reason_counts = ingest_gate_reason_metrics.get("ingest_gate_reason_code_counts_24h") or {}
    rec_file_missing = int(reason_counts.get("REC_FILE_MISSING") or 0)
    rec_file_unplayable = int(reason_counts.get("REC_FILE_UNPLAYABLE") or 0)
    artifact_failures = rec_file_missing + rec_file_unplayable
    unknown_ingest = int(ingest_gate_reason_metrics.get("ingest_gate_unknown_reason_rows_24h") or 0)
    transitions = int(runtime_backend_metrics.get("video_encoding_transitions_24h") or 0)
    sessions_5m = int(stagnation_metrics.get("recording_sessions_5m") or 0)
    persisted_5m = int(stagnation_metrics.get("post_fusion_persisted_sum_5m") or 0)
    visits_5m = int(stagnation_metrics.get("species_visits_5m") or 0)
    stagnation_alert = sessions_5m > 0 and persisted_5m == 0 and visits_5m == 0
    return {
        "thresholds": {
            "recording_artifact_failures_24h_max": 0,
            "video_encoding_transitions_24h_warn": 4,
            "unknown_ingest_gate_rows_24h_warn": 0,
            "data_stagnation_window_minutes_critical": 5,
        },
        "metrics": {
            "recording_artifact_failures_24h": int(artifact_failures),
            "recording_file_missing_24h": int(rec_file_missing),
            "recording_file_unplayable_24h": int(rec_file_unplayable),
            "video_encoding_transitions_24h": int(transitions),
            "unknown_ingest_gate_rows_24h": int(unknown_ingest),
            "recording_sessions_5m": sessions_5m,
            "post_fusion_persisted_sum_5m": persisted_5m,
            "species_visits_5m": visits_5m,
        },
        "alerts": {
            "recording_artifact_failures": bool(artifact_failures > 0),
            "video_encoding_flapping": bool(transitions >= 4),
            "unknown_ingest_gate_reasons": bool(unknown_ingest > 0),
            "data_stagnation": bool(stagnation_alert),
        },
    }


def _recent_data_stagnation_metrics(minutes: int = 5) -> dict[str, int]:
    window = max(1, int(minutes or 5))
    cutoff = _utc_now() - timedelta(minutes=window)
    rows = (
        db.session.query(ActivityLog)
        .filter(
            ActivityLog.type == "recording_session_summary",
            ActivityLog.created_at >= cutoff,
        )
        .order_by(ActivityLog.id.desc())
        .limit(500)
        .all()
    )
    sessions = 0
    persisted_sum = 0
    for row in rows:
        try:
            payload = json.loads(row.data or "{}")
        except Exception:
            continue
        if not isinstance(payload, dict):
            continue
        if not bool(payload.get("video_file_ok", False)):
            continue
        sessions += 1
        try:
            persisted_sum += int(payload.get("post_fusion_persisted") or 0)
        except (TypeError, ValueError):
            continue
    visits = db.session.query(SpeciesVisit).filter(SpeciesVisit.start_time >= cutoff).count()
    return {
        "recording_sessions_5m": int(sessions),
        "post_fusion_persisted_sum_5m": int(persisted_sum),
        "species_visits_5m": int(visits or 0),
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

    recording_context = payload.get("recording_context") if isinstance(payload.get("recording_context"), dict) else {}
    runtime_signals = (
        recording_context.get("runtime_signals") if isinstance(recording_context.get("runtime_signals"), dict) else {}
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


def _build_strict_quality_block(
    *,
    duplicate_video_groups: int,
    duplicate_detection_groups: int,
    duplicate_clip_candidates: list,
    species_sync_actions: list,
    detection_track_metrics: dict[str, Any],
) -> dict[str, bool]:
    total_24h = int(detection_track_metrics.get("video_detections_24h") or 0)
    frames_ratio = detection_track_metrics.get("video_detections_with_frames_ratio_24h")
    yolo_ratio = detection_track_metrics.get("video_detections_primary_yolo_ratio_24h")
    frames_ok = strict_quality_ratio_ok(frames_ratio, sample_count=total_24h, threshold=0.9)
    yolo_ok = strict_quality_ratio_ok(yolo_ratio, sample_count=total_24h, threshold=0.8)
    dup_video_ok = duplicate_video_groups == 0
    dup_det_ok = duplicate_detection_groups == 0
    dup_clip_ok = len(duplicate_clip_candidates) == 0
    visit_ok = len(species_sync_actions) == 0
    return {
        "duplicate_video_groups_ok": dup_video_ok,
        "duplicate_detection_groups_ok": dup_det_ok,
        "duplicate_clip_candidates_ok": dup_clip_ok,
        "visit_species_mismatches_ok": visit_ok,
        "video_detections_with_frames_ratio_ok": frames_ok,
        "video_detections_primary_yolo_ratio_ok": yolo_ok,
        "strict_quality_ready": (dup_video_ok and dup_det_ok and dup_clip_ok and visit_ok and frames_ok and yolo_ok),
    }


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
        track_quality_metrics = _recent_track_quality_metrics()
        track_quality_regression = _track_quality_regression_metrics()
        lifecycle_metrics = _recent_event_lifecycle_metrics()
        trigger_camera_metrics = _recent_trigger_camera_metrics()
        runtime_backend_metrics = _recent_runtime_backend_metrics()
        runtime_slo_metrics = _recent_runtime_session_slo_metrics()
        ingest_gate_reason_metrics = _recent_ingest_gate_reason_metrics()
        parity_diagnostics_metrics = _recent_parity_diagnostics_metrics()
        processor_funnel_metrics = _processor_runtime_funnel_metrics()
        stagnation_metrics = _recent_data_stagnation_metrics(minutes=5)
        reliability_alerts = _build_reliability_alerts(
            ingest_gate_reason_metrics=ingest_gate_reason_metrics,
            runtime_backend_metrics=runtime_backend_metrics,
            stagnation_metrics=stagnation_metrics,
        )
        metric_snapshot = {
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
            **(track_quality_metrics.get("metrics") or {}),
            **(track_quality_regression.get("metrics") or {}),
            **(lifecycle_metrics.get("metrics") or {}),
            **{
                "decision_trace_rows_24h": trigger_camera_metrics["decision_trace_rows_24h"],
                "session_extended_by_frigate_only_sum_24h": trigger_camera_metrics[
                    "session_extended_by_frigate_only_sum_24h"
                ],
                "decision_trace_rows_runtime_backend_24h": runtime_backend_metrics[
                    "decision_trace_rows_runtime_backend_24h"
                ],
                "ingest_gate_rows_24h": ingest_gate_reason_metrics["ingest_gate_rows_24h"],
                "ingest_gate_known_reason_rows_24h": ingest_gate_reason_metrics["ingest_gate_known_reason_rows_24h"],
                "ingest_gate_unknown_reason_rows_24h": ingest_gate_reason_metrics[
                    "ingest_gate_unknown_reason_rows_24h"
                ],
                "parity_frigate_windows_24h": parity_diagnostics_metrics["parity_frigate_windows_24h"],
                "parity_hub_matched_windows_24h": parity_diagnostics_metrics["parity_hub_matched_windows_24h"],
                "parity_mismatched_windows_24h": parity_diagnostics_metrics["parity_mismatched_windows_24h"],
                "parity_mismatch_rate_24h": parity_diagnostics_metrics["parity_mismatch_rate_24h"],
                "parity_hotspot_count_24h": parity_diagnostics_metrics["parity_hotspot_count_24h"],
            },
            **(runtime_slo_metrics.get("metrics") or {}),
            **processor_funnel_metrics,
            **stagnation_metrics,
        }
        sample_snapshot = {
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
            "track_unstable_examples_24h": (track_quality_metrics.get("samples") or {}).get(
                "track_unstable_examples_24h", []
            ),
            "track_quality_regression_24h": (track_quality_regression.get("samples") or {}).get(
                "track_quality_regression_24h", {}
            ),
            "lifecycle_outcome_counts_24h": (lifecycle_metrics.get("samples") or {}).get(
                "lifecycle_outcome_counts_24h", {}
            ),
            "lifecycle_top_reject_reasons_24h": (lifecycle_metrics.get("samples") or {}).get(
                "lifecycle_top_reject_reasons_24h", {}
            ),
            "runtime_slo_per_camera_24h": (runtime_slo_metrics.get("samples") or {}).get(
                "runtime_slo_per_camera_24h", []
            ),
        }
        slo_dashboard, alerting_rules = _build_slo_dashboard(
            metrics=metric_snapshot,
            samples=sample_snapshot,
            reliability_alerts=reliability_alerts,
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
            "metrics": metric_snapshot,
            "samples": sample_snapshot,
            "contracts": contracts_block,
            "reliability_alerts": reliability_alerts,
            "slo_dashboard": slo_dashboard,
            "alerting_rules": alerting_rules,
            "strict_quality": _build_strict_quality_block(
                duplicate_video_groups=duplicate_video_groups,
                duplicate_detection_groups=duplicate_detection_groups,
                duplicate_clip_candidates=duplicate_clip_candidates,
                species_sync_actions=species_sync_actions,
                detection_track_metrics=detection_track_metrics,
            ),
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
                "track_rows_with_id_24h": None,
                "track_rows_with_frame_series_24h": None,
                "track_rows_fragmented_24h": None,
                "track_rows_fragmented_ratio_24h": None,
                "track_rows_with_gaps_24h": None,
                "track_rows_with_gaps_ratio_24h": None,
                "track_avg_jitter_24h": None,
                "track_stability_score_avg_24h": None,
                "track_stability_score_p50_24h": None,
                "track_stability_low_count_24h": None,
                "track_stability_low_ratio_24h": None,
                "track_stability_score_delta_prev_24h": None,
                "track_fragmented_ratio_delta_prev_24h": None,
                "track_gaps_ratio_delta_prev_24h": None,
                "track_quality_regression_24h": None,
                "lifecycle_windows_24h": None,
                "lifecycle_detected_windows_24h": None,
                "lifecycle_entered_windows_24h": None,
                "lifecycle_rejected_only_windows_24h": None,
                "lifecycle_no_tracks_windows_24h": None,
                "lifecycle_detect_rate_24h": None,
                "lifecycle_enter_rate_24h": None,
                "lifecycle_rejected_only_rate_24h": None,
                "lifecycle_avg_persisted_tracks_per_window_24h": None,
                "lifecycle_avg_rejected_tracks_per_window_24h": None,
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
                "runtime_sessions_24h": None,
                "runtime_sustained_fps_avg_24h": None,
                "runtime_sustained_fps_p50_24h": None,
                "runtime_skipped_ratio_avg_24h": None,
                "runtime_pipeline_latency_p95_ms_24h": None,
                "runtime_reconnect_events_24h": None,
                "runtime_backpressure_events_24h": None,
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
                "track_unstable_examples_24h": [],
                "track_quality_regression_24h": {},
                "lifecycle_outcome_counts_24h": {},
                "lifecycle_top_reject_reasons_24h": {},
                "runtime_slo_per_camera_24h": [],
            },
            "contracts": contracts_block,
            "reliability_alerts": {
                "thresholds": {
                    "recording_artifact_failures_24h_max": 0,
                    "video_encoding_transitions_24h_warn": 4,
                    "unknown_ingest_gate_rows_24h_warn": 0,
                    "data_stagnation_window_minutes_critical": 5,
                },
                "metrics": {
                    "recording_artifact_failures_24h": None,
                    "recording_file_missing_24h": None,
                    "recording_file_unplayable_24h": None,
                    "video_encoding_transitions_24h": None,
                    "unknown_ingest_gate_rows_24h": None,
                    "recording_sessions_5m": None,
                    "post_fusion_persisted_sum_5m": None,
                    "species_visits_5m": None,
                },
                "alerts": {
                    "recording_artifact_failures": False,
                    "video_encoding_flapping": False,
                    "unknown_ingest_gate_reasons": False,
                    "data_stagnation": False,
                },
            },
            "slo_dashboard": {
                "schema": "runtime_slo_dashboard@v1",
                "targets": {
                    "sustained_fps_min": 7.0,
                    "skipped_ratio_max": 0.05,
                    "pipeline_latency_p95_ms_max": 2500.0,
                },
                "snapshot": {
                    "runtime_sessions_24h": 0,
                    "sustained_fps_avg_24h": None,
                    "skipped_ratio_avg_24h": None,
                    "pipeline_latency_p95_ms_24h": None,
                    "reconnect_events_24h": None,
                    "backpressure_events_24h": None,
                    "per_camera_warn_count_24h": 0,
                },
                "status": {
                    "ok": False,
                    "breaches": ["snapshot_degraded"],
                },
            },
            "alerting_rules": [],
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
