"""Shared schemas (Pydantic) for MQTT / detection boundaries (#265)."""

from .events import (
    BirdnetMqttEvent,
    FrigateMqttEvent,
    validate_mqtt_detection_dict,
)

__all__ = [
    "BirdnetMqttEvent",
    "FrigateMqttEvent",
    "validate_mqtt_detection_dict",
]
