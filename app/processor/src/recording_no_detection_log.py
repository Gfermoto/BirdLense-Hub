"""No-detection finalize logging helpers."""

from __future__ import annotations

import logging
from typing import Any


def log_no_detections_after_merge(
    *,
    track_count: int,
    mqtt_event_count: int,
    now_monotonic: float,
    next_warn_monotonic: float,
    warn_interval_seconds: float,
) -> float:
    """Throttle warning logs for empty post-merge detection sessions."""
    msg = (
        "No detections after merge. YOLO tracks: %s, MQTT events in window: %s",
        int(track_count),
        int(mqtt_event_count),
    )
    if now_monotonic >= next_warn_monotonic:
        logging.warning(*msg)
        return now_monotonic + warn_interval_seconds
    logging.debug(*msg)
    return next_warn_monotonic


def _no_detection_reason_code(*, track_count: int, mqtt_event_count: int) -> str:
    if int(track_count) <= 0 and int(mqtt_event_count) > 0:
        return "FUSION_NO_YOLO_NO_FALLBACK"
    if int(track_count) > 0 or int(mqtt_event_count) > 0:
        return "FUSION_NO_ACCEPTED"
    return "UNKNOWN"


def _fusion_no_accepted_reason_code(
    rejected_reason_counts: dict[str, int] | None,
) -> str | None:
    if not isinstance(rejected_reason_counts, dict) or not rejected_reason_counts:
        return None
    counts = {str(k or "").strip().lower(): int(v or 0) for k, v in rejected_reason_counts.items()}
    if counts.get("rejected_static_pinned_track", 0) > 0:
        return "FUSION_NO_ACCEPTED_STATIC_PINNED"
    if counts.get("rejected_short_track", 0) > 0:
        return "FUSION_NO_ACCEPTED_SHORT_TRACK"
    if counts.get("low_confidence", 0) > 0:
        return "FUSION_NO_ACCEPTED_LOW_CONFIDENCE"
    return None


def log_no_detection_activity(
    api: Any,
    *,
    track_count: int,
    mqtt_event_count: int,
    rejected_count: int,
    video_path_for_api: str,
    trigger_source: str | None = None,
    triggered_camera: str | None = None,
    rejected_reason_counts: dict[str, int] | None = None,
) -> None:
    """Write structured ingest_gate activity for empty persisted detections."""
    if not api:
        return
    reason_code = _no_detection_reason_code(
        track_count=int(track_count),
        mqtt_event_count=int(mqtt_event_count),
    )
    if reason_code == "FUSION_NO_ACCEPTED":
        reason_code = _fusion_no_accepted_reason_code(rejected_reason_counts) or reason_code
    if reason_code == "UNKNOWN":
        return
    try:
        api.activity_log(
            type="ingest_gate",
            data={
                "reason": "no_persisted_detections",
                "reason_code": reason_code,
                "stage": "processor_finalize",
                "video_path": video_path_for_api,
                "trigger_source": (str(trigger_source or "").strip().lower() or None),
                "triggered_camera": (str(triggered_camera or "").strip() or None),
                "yolo_track_count": int(track_count),
                "mqtt_event_count": int(mqtt_event_count),
                "rejected_count": int(rejected_count),
                "rejected_reason_counts": dict(rejected_reason_counts or {}),
            },
        )
    except Exception:
        logging.exception("no_detection ingest_gate activity_log failed")
