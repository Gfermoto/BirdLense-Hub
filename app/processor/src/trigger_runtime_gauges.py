"""Trigger-path observability for processor_runtime_stats.json (#432 / Scale B1)."""

from __future__ import annotations

import logging
import os
from typing import Any

from app_config.app_config import app_config
from app_config.trigger_config import (
    effective_active_trigger_names_for_mqtt_status,
    get_active_trigger_names,
    get_effective_trigger_config,
)
from processor_runtime_stats import set_gauge

logger = logging.getLogger(__name__)


def _mqtt_live(aggregator: Any | None) -> bool:
    if aggregator is None:
        return False
    try:
        return bool(aggregator.is_mqtt_live())
    except Exception:
        return False


def refresh_trigger_runtime_gauges(
    *,
    mqtt_broker: str | None,
    mqtt_aggregator: Any | None = None,
    trigger_config: dict[str, dict[str, Any]] | None = None,
) -> None:
    """Publish gauges derived from merged triggers.* and live MQTT (best-effort).

    Called after motion stack build and on MQTT connect/disconnect so operators can
    alert on ``trigger_frigate_degraded_no_mqtt`` or ``trigger_degraded_effective_lt_configured``.
    """
    try:
        tc = trigger_config or get_effective_trigger_config(app_config, mqtt_broker=mqtt_broker)
        opencv_on = bool((tc.get("opencv") or {}).get("enabled"))
        frigate_on = bool((tc.get("frigate") or {}).get("enabled"))
        motion_sensor_on = bool((tc.get("motion_sensor") or {}).get("enabled"))
        scales_on = bool((tc.get("scales") or {}).get("enabled"))

        set_gauge("trigger_cfg_opencv_enabled", 1 if opencv_on else 0)
        set_gauge("trigger_cfg_frigate_enabled", 1 if frigate_on else 0)
        set_gauge("trigger_cfg_motion_sensor_enabled", 1 if motion_sensor_on else 0)
        set_gauge("trigger_cfg_scales_enabled", 1 if scales_on else 0)

        mqtt_configured = bool(str(mqtt_broker or "").strip())
        set_gauge("trigger_mqtt_configured", 1 if mqtt_configured else 0)

        live = _mqtt_live(mqtt_aggregator) if mqtt_configured else False
        set_gauge("trigger_mqtt_live", 1 if live else 0)

        set_gauge(
            "trigger_frigate_degraded_no_mqtt",
            1 if (frigate_on and mqtt_configured and not live) else 0,
        )

        configured = get_active_trigger_names(app_config, mqtt_broker=mqtt_broker)
        mqtt_disp = "ok" if live else "down"
        effective = effective_active_trigger_names_for_mqtt_status(
            configured,
            tc,
            mqtt_display=mqtt_disp,
        )
        set_gauge("trigger_configured_paths_count", float(len(configured)))
        set_gauge("trigger_effective_paths_count", float(len(effective)))
        set_gauge(
            "trigger_degraded_effective_lt_configured",
            1 if len(effective) < len(configured) else 0,
        )
    except Exception:
        logger.debug("refresh_trigger_runtime_gauges failed", exc_info=True)


def notify_mqtt_connection_changed_for_trigger_gauges(mqtt_aggregator: Any | None) -> None:
    """Hook from MQTTEventAggregator connect/disconnect handlers."""
    if mqtt_aggregator is None:
        return
    try:
        broker = getattr(mqtt_aggregator, "broker", None) or (
            os.environ.get("MQTT_BROKER") or app_config.get("mqtt.broker")
        )
        refresh_trigger_runtime_gauges(mqtt_broker=str(broker) if broker else None, mqtt_aggregator=mqtt_aggregator)
    except Exception:
        logger.debug("notify_mqtt_connection_changed_for_trigger_gauges failed", exc_info=True)
