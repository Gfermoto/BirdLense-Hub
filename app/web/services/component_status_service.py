"""Сборка payload для GET /api/ui/status (#293)."""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta, timezone

from app_config.app_config import app_config
from app_config.trigger_config import (
    format_trigger_display_line,
    get_active_trigger_names,
    get_effective_trigger_config,
    get_legacy_motion_source_label,
)
from models import ActivityLog
from services.feed_service import check_esphome_reachable, check_mqtt_connected
from services.status_service import check_video_reachable, parse_yolo_status_from_heartbeat
from util import ensure_utc

logger = logging.getLogger(__name__)


def _fallback_component_status_payload() -> dict[str, str | None]:
    """Минимальный payload, если основная сборка упала (деплой/verify не должны валить воркер)."""
    return {
        "web": "ok",
        "processor": "unknown",
        "video": "unknown",
        "mqtt": "unknown",
        "esphome": "unknown",
        "yolo": "unknown",
        "motion_source": "unknown",
        "trigger_display": "unknown",
        "active_triggers": [],
        "birdnet_url": None,
    }


def build_component_status_payload_safe(session) -> dict:
    """Как build_component_status_payload, но без необработанных исключений (readiness / status)."""
    try:
        return build_component_status_payload(session)
    except Exception:
        logger.exception("build_component_status_payload failed; using fallback")
        return _fallback_component_status_payload()


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
    mqtt_broker = os.environ.get("MQTT_BROKER") or app_config.get("mqtt.broker")
    trigger_cfg = get_effective_trigger_config(app_config, mqtt_broker=mqtt_broker)
    active_triggers = get_active_trigger_names(app_config, mqtt_broker=mqtt_broker)
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
    if any(
        bool((trigger_cfg.get(name) or {}).get("enabled"))
        and str((trigger_cfg.get(name) or {}).get("source") or "") == "esphome"
        for name in ("motion_sensor", "scales")
    ):
        esphome_display = esphome_status
    elif feed_source != "esphome":
        esphome_display = "not_used"
    trigger_display = format_trigger_display_line(active_triggers)
    video_display = check_video_reachable()
    yolo_display = parse_yolo_status_from_heartbeat(heartbeat_data) if processor_ok else "unknown"
    return {
        "web": "ok",
        "processor": "ok" if processor_ok else "offline",
        "video": video_display,
        "mqtt": mqtt_display,
        "esphome": esphome_display,
        "yolo": yolo_display,
        "motion_source": get_legacy_motion_source_label(app_config, mqtt_broker=mqtt_broker),
        "trigger_display": trigger_display,
        "active_triggers": active_triggers,
        "birdnet_url": birdnet_url or None,
    }
