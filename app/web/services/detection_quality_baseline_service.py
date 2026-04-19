"""Baseline-метрики качества детекции/распознавания для Hub."""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Mapping
from datetime import datetime, timedelta, timezone

from models import ActivityLog, Video, VideoSpecies, db

from services.activity_notify_insights_service import activity_log_payload
from services.ml_health_stats_service import ml_health_snapshot


def _utc_now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _coerce_datetime(value) -> datetime | None:
    if isinstance(value, datetime):
        return value.replace(tzinfo=None) if value.tzinfo else value
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.astimezone(timezone.utc).replace(tzinfo=None) if parsed.tzinfo else parsed


def _latest_live_traces_since(cutoff: datetime) -> dict[int, dict]:
    rows = (
        db.session.query(ActivityLog)
        .filter(
            ActivityLog.type == "decision_trace",
            ActivityLog.created_at >= cutoff,
        )
        .order_by(ActivityLog.created_at.desc())
        .all()
    )
    latest: dict[int, dict] = {}
    for row in rows:
        payload = activity_log_payload(row) or {}
        if str((payload.get("recording_context") or {}).get("triggered_by") or "live") == "track_regen":
            continue
        try:
            video_id = int(payload.get("video_id"))
        except (TypeError, ValueError):
            continue
        if video_id in latest:
            continue
        latest[video_id] = payload
    return latest


def _bbox_area_from_frames(frames_json: str | None) -> float | None:
    if not frames_json or not str(frames_json).strip():
        return None
    try:
        frames = json.loads(frames_json)
    except (TypeError, ValueError):
        return None
    if not isinstance(frames, list):
        return None
    best = None
    for frame in frames:
        if not isinstance(frame, dict):
            continue
        bbox = frame.get("bbox")
        if not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
            continue
        try:
            x1, y1, x2, y2 = [float(v) for v in bbox]
        except (TypeError, ValueError):
            continue
        area = max(0.0, x2 - x1) * max(0.0, y2 - y1)
        if best is None or area > best:
            best = area
    return best


def _object_scale(area: float | None) -> str:
    if area is None:
        return "unknown"
    if area < 0.02:
        return "small"
    if area < 0.12:
        return "medium"
    return "large"


def _time_of_day_bucket(start_time: datetime | None) -> str:
    if start_time is None:
        return "unknown"
    return "night" if start_time.hour < 6 or start_time.hour >= 20 else "day"


def _trace_summary_from_payloads(payloads: list[dict]) -> dict:
    clip_count = len(payloads)
    persisted_track_count = 0
    decision_kind_counts: Counter[str] = Counter()
    primary_provider_counts: Counter[str] = Counter()
    low_light_clip_count = 0
    frigate_rescue_clip_count = 0
    yolo_silent_clip_count = 0
    runtime_agg = {
        "frames_seen": 0,
        "yolo_frames_ran": 0,
        "yolo_frames_with_tracks": 0,
        "low_light_blocked_frames": 0,
        "session_extended_by_frigate": 0,
    }

    for payload in payloads:
        persisted = payload.get("persisted_tracks") or payload.get("accepted_tracks") or []
        if not isinstance(persisted, list):
            persisted = []
        persisted_track_count += len(persisted)
        runtime = (payload.get("recording_context") or {}).get("runtime_signals") or {}
        if int(runtime.get("low_light_blocked_frames") or 0) > 0:
            low_light_clip_count += 1
        frigate_rescue = bool(runtime.get("session_extended_by_frigate"))
        yolo_track_found = bool(runtime.get("yolo_track_found"))
        if not yolo_track_found and int(runtime.get("yolo_frames_with_tracks") or 0) > 0:
            yolo_track_found = True
        if not yolo_track_found and persisted:
            yolo_silent_clip_count += 1
        for key in runtime_agg:
            runtime_agg[key] += int(runtime.get(key) or 0)
        for track in persisted:
            kind = str(track.get("decision_kind") or "unknown")
            provider = str(track.get("primary_provider") or "unknown")
            decision_kind_counts[kind] += 1
            primary_provider_counts[provider] += 1
            if bool(track.get("frigate_standalone")) or kind.startswith("frigate_standalone"):
                frigate_rescue = True
        if frigate_rescue:
            frigate_rescue_clip_count += 1

    def _rate(part: int, whole: int) -> float:
        if whole <= 0:
            return 0.0
        return round(float(part) / float(whole), 4)

    return {
        "clip_count": clip_count,
        "persisted_track_count": persisted_track_count,
        "decision_kind_counts": dict(sorted(decision_kind_counts.items())),
        "primary_provider_counts": dict(sorted(primary_provider_counts.items())),
        "low_light_clip_rate": _rate(low_light_clip_count, clip_count),
        "frigate_rescue_clip_rate": _rate(frigate_rescue_clip_count, clip_count),
        "yolo_silent_clip_rate": _rate(yolo_silent_clip_count, clip_count),
        "runtime_signals": runtime_agg,
    }


def _detection_slices_since(cutoff: datetime) -> dict:
    rows = (
        db.session.query(VideoSpecies, Video.start_time)
        .join(Video, Video.id == VideoSpecies.video_id)
        .filter(
            VideoSpecies.source == "video",
            Video.start_time >= cutoff,
        )
        .all()
    )
    time_of_day: Counter[str] = Counter()
    object_scale: Counter[str] = Counter()
    provider: Counter[str] = Counter()
    for vs, video_start in rows:
        time_of_day[_time_of_day_bucket(_coerce_datetime(video_start))] += 1
        object_scale[_object_scale(_bbox_area_from_frames(getattr(vs, "frames", None)))] += 1
        provider[str(getattr(vs, "detection_provider", None) or "unknown")] += 1
    return {
        "time_of_day": dict(sorted(time_of_day.items())),
        "object_scale": dict(sorted(object_scale.items())),
        "provider": dict(sorted(provider.items())),
    }


def build_detection_quality_baseline(
    *,
    days: int = 14,
    now: datetime | None = None,
    runtime_snapshot: Mapping[str, object] | None = None,
) -> dict:
    """Сводка baseline-качества по последним клипам и ручным коррекциям."""
    now_utc = _coerce_datetime(now) or _utc_now_naive()
    window_days = max(1, int(days or 1))
    cutoff = now_utc - timedelta(days=window_days)
    latest_live = _latest_live_traces_since(cutoff)
    payloads = list(latest_live.values())

    return {
        "generated_at": now_utc.replace(tzinfo=timezone.utc).isoformat(),
        "window_days": window_days,
        "trace_summary": _trace_summary_from_payloads(payloads),
        "correction_proxies": ml_health_snapshot(window_days),
        "detection_slices": _detection_slices_since(cutoff),
        "runtime_observability": dict(runtime_snapshot or {}),
    }
