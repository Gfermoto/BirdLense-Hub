"""Shared feeder-scales source helpers for web and processor."""

from __future__ import annotations

SCALES_SOURCE_MQTT = "mqtt"
SCALES_SOURCE_ESPHOME_MQTT = "esphome_mqtt"
SCALES_SOURCE_ESPHOME_DIRECT = "esphome_direct"
SCALES_SOURCE_HOMEASSISTANT = "homeassistant"

MQTT_BACKED_SCALES_SOURCES = frozenset(
    {
        SCALES_SOURCE_MQTT,
        SCALES_SOURCE_ESPHOME_MQTT,
    }
)


def normalize_scales_source(value: object) -> str:
    """Normalize persisted/user input source to a supported scales source."""
    src = str(value or SCALES_SOURCE_MQTT).strip().lower()
    if src in {
        SCALES_SOURCE_MQTT,
        SCALES_SOURCE_ESPHOME_MQTT,
        SCALES_SOURCE_ESPHOME_DIRECT,
        SCALES_SOURCE_HOMEASSISTANT,
    }:
        return src
    return SCALES_SOURCE_MQTT


def scales_source_uses_mqtt(source: object) -> bool:
    return normalize_scales_source(source) in MQTT_BACKED_SCALES_SOURCES
