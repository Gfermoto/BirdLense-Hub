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
    trigger_source: str | None = None,
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
            # Long lookback tends to resurrect stale Frigate events and create empty clips.
            # Keep a short recovery window only.
            lookback = max(merge_window, 15)
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
        scoped_events = events
    else:
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
                "Finalize MQTT window camera-scope: dropped %s Frigate event(s) from other cameras (triggered_camera=%s)",
                skipped_frigate,
                scope_cam_l,
            )
        scoped_events = out

    trig_src = str(trigger_source or "").strip().lower()
    has_frigate_event = any(str((ev or {}).get("source") or "").strip().lower() == "frigate" for ev in scoped_events)
    if trig_src == "frigate" and not has_frigate_event:
        last_event_getter = getattr(motion_detector, "get_last_frigate_event", None)
        if callable(last_event_getter):
            ev = last_event_getter()
            if isinstance(ev, dict) and ev:
                camera = str(ev.get("camera") or lookback_cam or scope_camera_id or "").strip()
                fallback_ev = {
                    "source": "frigate",
                    "species": str(ev.get("species") or ev.get("label") or "bird"),
                    "label": str(ev.get("label") or ev.get("species") or "bird"),
                    "sub_label": str(ev.get("sub_label") or ""),
                    "camera": camera,
                    "confidence": float(ev.get("confidence") or 0.0),
                    "timestamp": str(ev.get("timestamp") or end_time.isoformat()),
                    "_synthetic_trigger_fallback": True,
                    # This event already triggered recording; allow fallback salvage
                    # even when Frigate payload had no explicit box.
                    "_frigate_has_geometry": bool(ev.get("_frigate_has_geometry", True)),
                }
                scoped_events = [*scoped_events, fallback_ev]
                inc_counter("mqtt_trigger_fallback_injected_total")
                logging.warning(
                    "Finalize MQTT window: injected Frigate trigger fallback event camera=%s confidence=%.3f",
                    camera,
                    float(fallback_ev["confidence"]),
                )
    return scoped_events
