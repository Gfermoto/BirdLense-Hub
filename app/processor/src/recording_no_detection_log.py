"""No-detection finalize logging helpers."""

from __future__ import annotations

import logging


def log_no_detections_after_merge(
    *,
    track_count: int,
    mqtt_event_count: int,
    now_monotonic: float,
    next_warn_monotonic: float,
    warn_interval_seconds: float,
) -> float:
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
