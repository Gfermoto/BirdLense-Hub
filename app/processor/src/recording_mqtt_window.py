"""MQTT event-window helpers for recording finalization."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from processor_runtime_stats import inc_counter


def get_recording_mqtt_events(
    mqtt_aggregator: Any,
    motion_detector: Any,
    *,
    start_time: datetime,
    end_time: datetime,
    merge_window: int,
    yolo_tracks_count: int,
    scope_camera_id: str | None = None,
    lookback_camera_id: str | None = None,
) -> list[dict]:
    """Fetch MQTT events with extended Frigate lookback for zero-YOLO sessions."""
    if not mqtt_aggregator:
        return []

    lookback = merge_window
    lookback_cam = lookback_camera_id
    if lookback_cam is None:
        lookback_cam = getattr(
            motion_detector,
            "get_triggered_camera",
            lambda: None,
        )()
    scope_cam_l = str(scope_camera_id or "").strip().lower()
    if yolo_tracks_count == 0:
        if lookback_cam:
            lookback = max(merge_window, 60)
            logging.info(
                "Frigate trigger (camera=%s), 0 YOLO: extended MQTT lookback to %ds",
                lookback_cam,
                lookback,
            )
    events = mqtt_aggregator.get_events_in_window(
        start_time,
        end_time,
        merge_window,
        lookback_seconds=lookback,
    )
    if not scope_cam_l:
        return events
    out: list[dict] = []
    skipped_frigate = 0
    for ev in events:
        source = str((ev or {}).get("source") or "").strip().lower()
        if source != "frigate":
            out.append(ev)
            continue
        cam = str((ev or {}).get("camera") or "").strip().lower()
        if not cam:
            out.append(ev)
            continue
        if cam == scope_cam_l:
            out.append(ev)
        else:
            skipped_frigate += 1
    if skipped_frigate > 0:
        inc_counter("mqtt_scope_drop_total", skipped_frigate)
        logging.info(
            "Finalize MQTT window camera-scope: dropped %s Frigate event(s) from other cameras "
            "(triggered_camera=%s)",
            skipped_frigate,
            scope_cam_l,
        )
    return out
