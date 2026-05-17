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
    frigate_trigger_event: dict | None = None,
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
    trig_src = str(trigger_source or "").strip().lower()
    extended_frigate_lookback = bool(lookback_cam) and (
        yolo_tracks_count == 0 or trig_src == "frigate"
    )
    if extended_frigate_lookback:
        # Short default lookback misses Frigate MQTT when YOLO tracks exist later in the clip.
        # Keep a bounded recovery window (same cap as zero-YOLO Frigate sessions).
        lookback = max(merge_window, 15)
        logging.info(
            "Frigate MQTT lookback %ds (camera=%s, yolo_tracks=%s, trigger=%s)",
            lookback,
            lookback_cam,
            yolo_tracks_count,
            trig_src or "unknown",
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

    has_frigate_event = any(str((ev or {}).get("source") or "").strip().lower() == "frigate" for ev in scoped_events)
    if trig_src == "frigate" and not has_frigate_event:
        ev: dict | None = None
        if isinstance(frigate_trigger_event, dict) and frigate_trigger_event:
            ev = dict(frigate_trigger_event)
        else:
            last_event_getter = getattr(motion_detector, "get_last_frigate_event", None)
            if callable(last_event_getter):
                raw = last_event_getter()
                if isinstance(raw, dict) and raw:
                    ev = dict(raw)

        scope_ref = str(scope_camera_id or lookback_cam or "").strip().lower()
        if isinstance(ev, dict) and ev:
            ev_cam = str(ev.get("camera") or "").strip().lower()
            if scope_ref and ev_cam and ev_cam != scope_ref:
                logging.warning(
                    "Finalize MQTT window: skip trigger fallback — Frigate event camera=%s != session=%s",
                    ev_cam,
                    scope_ref,
                )
                ev = None

        if isinstance(ev, dict) and ev:
            camera = str(ev.get("camera") or lookback_cam or scope_camera_id or "").strip()
            if not camera and scope_ref:
                camera = scope_ref
            session_snapshot = bool(ev.get("_session_trigger_snapshot"))
            fallback_ev = {
                "source": "frigate",
                "species": str(ev.get("species") or ev.get("label") or "bird"),
                "label": str(ev.get("label") or ev.get("species") or "bird"),
                "sub_label": str(ev.get("sub_label") or ""),
                "camera": camera,
                "confidence": float(ev.get("confidence") or 0.0),
                "timestamp": str(ev.get("timestamp") or end_time.isoformat()),
                "_synthetic_trigger_fallback": True,
                "_session_trigger_snapshot": session_snapshot,
                # This event already triggered recording; allow fallback salvage
                # even when Frigate payload had no explicit box.
                "_frigate_has_geometry": bool(ev.get("_frigate_has_geometry", True)),
            }
            if isinstance(ev.get("frigate_bbox_norm"), (list, tuple)):
                fallback_ev["frigate_bbox_norm"] = list(ev.get("frigate_bbox_norm") or [])
            scoped_events = [*scoped_events, fallback_ev]
            inc_counter("mqtt_trigger_fallback_injected_total")
            logging.warning(
                "Finalize MQTT window: injected Frigate trigger fallback event camera=%s confidence=%.3f session_snapshot=%s",
                camera,
                float(fallback_ev["confidence"]),
                session_snapshot,
            )
    return scoped_events
