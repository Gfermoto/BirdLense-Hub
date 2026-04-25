"""MQTT event-window helpers for recording finalization."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any


def get_recording_mqtt_events(
    mqtt_aggregator: Any,
    motion_detector: Any,
    *,
    start_time: datetime,
    end_time: datetime,
    merge_window: int,
    yolo_tracks_count: int,
) -> list[dict]:
    """Fetch MQTT events with extended Frigate lookback for zero-YOLO sessions."""
    if not mqtt_aggregator:
        return []

    lookback = merge_window
    if yolo_tracks_count == 0:
        triggered_cam = getattr(
            motion_detector,
            "get_triggered_camera",
            lambda: None,
        )()
        if triggered_cam:
            lookback = max(merge_window, 60)
            logging.info(
                "Frigate trigger, 0 YOLO: extended MQTT lookback to %ds",
                lookback,
            )
    return mqtt_aggregator.get_events_in_window(
        start_time,
        end_time,
        merge_window,
        lookback_seconds=lookback,
    )
