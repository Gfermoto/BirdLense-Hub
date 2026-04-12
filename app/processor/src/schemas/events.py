"""
Normalized MQTT detection payloads after JSON parse (Frigate / BirdNET).

Use for strict validation at subsystem boundaries; parsers in ``mqtt_aggregator``
may stay lenient and optionally call ``validate_mqtt_detection_dict`` when debugging.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class FrigateMqttEvent(BaseModel):
    """Shape aligned with ``_parse_frigate_event`` output."""

    model_config = ConfigDict(extra="ignore")

    source: Literal["frigate"] = "frigate"
    species: str
    label: str = ""
    sub_label: str = ""
    confidence: float = Field(ge=0.0)
    camera: str = ""
    timestamp: str


class BirdnetMqttEvent(BaseModel):
    """Shape aligned with ``_parse_birdnet_event`` core fields."""

    model_config = ConfigDict(extra="ignore")

    source: Literal["birdnet"] = "birdnet"
    species: str
    common_name: str = ""
    confidence: float = Field(ge=0.0)
    timestamp: str
    scientific_name: str | None = None
    species_code: str | None = None
    audio_source: str | None = None
    camera_id: str | None = None
    site_id: str | None = None
    bird_image_url: str | None = None


def validate_mqtt_detection_dict(ev: dict) -> tuple[FrigateMqttEvent | BirdnetMqttEvent | None, str | None]:
    """Return validated model or (None, error message)."""
    src = ev.get("source")
    try:
        if src == "frigate":
            return FrigateMqttEvent.model_validate(ev), None
        if src == "birdnet":
            return BirdnetMqttEvent.model_validate(ev), None
    except Exception as e:
        return None, str(e)
    return None, f"unknown source: {src!r}"
