"""Shared feeder-scales source helpers for web and processor."""

from __future__ import annotations

SCALES_SOURCE_MQTT = "mqtt"
SCALES_SOURCE_ESPHOME = "esphome"
SCALES_SOURCE_HOMEASSISTANT = "homeassistant"

LEGACY_SCALES_SOURCE_ESPHOME_MQTT = "esphome_mqtt"
LEGACY_SCALES_SOURCE_ESPHOME_DIRECT = "esphome_direct"

MQTT_BACKED_SCALES_SOURCES = frozenset(
    {
        SCALES_SOURCE_MQTT,
        LEGACY_SCALES_SOURCE_ESPHOME_MQTT,
    }
)


def normalize_scales_source(value: object) -> str:
    """Normalize persisted/user input source to a supported scales source."""
    src = str(value or SCALES_SOURCE_MQTT).strip().lower()
    if src == LEGACY_SCALES_SOURCE_ESPHOME_MQTT:
        return SCALES_SOURCE_MQTT
    if src == LEGACY_SCALES_SOURCE_ESPHOME_DIRECT:
        return SCALES_SOURCE_ESPHOME
    if src in {
        SCALES_SOURCE_MQTT,
        SCALES_SOURCE_ESPHOME,
        SCALES_SOURCE_HOMEASSISTANT,
    }:
        return src
    return SCALES_SOURCE_MQTT


def scales_source_uses_mqtt(source: object) -> bool:
    return normalize_scales_source(source) in MQTT_BACKED_SCALES_SOURCES
