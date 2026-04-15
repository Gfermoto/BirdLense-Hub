"""Сборка payload для GET /api/ui/status (#293)."""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone

from app_config.app_config import app_config
from models import ActivityLog
from services.feed_service import check_esphome_reachable, check_mqtt_connected
from services.status_service import check_video_reachable, parse_yolo_status_from_heartbeat
from util import ensure_utc

_TRIGGER_LABELS = {
    "opencv": "OpenCV",
    "frigate": "Frigate (MQTT)",
    "mqtt": "MQTT sensor",
    "esphome": "ESPHome",
    "pir": "PIR",
}


def _trigger_display(motion_source: str, frigate_parallel: bool) -> str:
    trigger_display = _TRIGGER_LABELS.get(motion_source, motion_source)
    if motion_source == "opencv" and frigate_parallel:
        return "OpenCV + Frigate (MQTT)"
    if motion_source == "mqtt" and frigate_parallel:
        return "MQTT sensor + Frigate (MQTT)"
    if motion_source == "esphome" and frigate_parallel:
        return "ESPHome + Frigate (MQTT)"
    return trigger_display


def build_component_status_payload(session) -> dict:
    """Статусы Video / MQTT / ESPHome / YOLO / процессор для UI."""
    last_heartbeat = (
        session.query(ActivityLog).filter_by(type="heartbeat").order_by(ActivityLog.updated_at.desc()).first()
    )
    processor_ok = False
    if last_heartbeat and last_heartbeat.updated_at:
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=5)
        try:
            updated = ensure_utc(last_heartbeat.updated_at)
            processor_ok = updated >= cutoff
        except (TypeError, ValueError):
            processor_ok = False
    heartbeat_data = None
    if last_heartbeat and last_heartbeat.data:
        try:
            heartbeat_data = (
                json.loads(last_heartbeat.data) if isinstance(last_heartbeat.data, str) else last_heartbeat.data
            )
        except (TypeError, ValueError):
            pass
    mqtt_status = check_mqtt_connected()
    esphome_status = check_esphome_reachable()
    feed_source = app_config.get("feed.source", "mqtt")
    motion_source = app_config.get("motion.source", "opencv")
    mqtt_broker = os.environ.get("MQTT_BROKER") or app_config.get("mqtt.broker")
    if mqtt_broker:
        if processor_ok and isinstance(heartbeat_data, dict) and "mqtt_connected" in heartbeat_data:
            mqtt_display = "ok" if heartbeat_data.get("mqtt_connected") else "error"
        else:
            mqtt_display = mqtt_status
    elif feed_source == "mqtt":
        mqtt_display = mqtt_status
    else:
        mqtt_display = "not_used"
    esphome_display = esphome_status if feed_source == "esphome" else "not_used"
    birdnet_url = (app_config.get("general.birdnet_url") or "").strip()
    frigate_parallel = bool(mqtt_broker and (app_config.get("mqtt.frigate_topic") or "").strip())
    trigger_display = _trigger_display(motion_source, frigate_parallel)
    video_display = check_video_reachable()
    yolo_display = parse_yolo_status_from_heartbeat(heartbeat_data) if processor_ok else "unknown"
    return {
        "web": "ok",
        "processor": "ok" if processor_ok else "offline",
        "video": video_display,
        "mqtt": mqtt_display,
        "esphome": esphome_display,
        "yolo": yolo_display,
        "motion_source": motion_source,
        "trigger_display": trigger_display,
        "birdnet_url": birdnet_url or None,
    }
