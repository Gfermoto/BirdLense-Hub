from app_config.scales_config import (
    SCALES_SOURCE_ESPHOME,
    SCALES_SOURCE_MQTT,
    normalize_scales_source,
    scales_source_uses_mqtt,
)


def test_normalize_scales_source_accepts_new_values():
    assert normalize_scales_source("mqtt") == SCALES_SOURCE_MQTT
    assert normalize_scales_source("esphome") == SCALES_SOURCE_ESPHOME


def test_normalize_scales_source_maps_legacy_values():
    assert normalize_scales_source("esphome_mqtt") == SCALES_SOURCE_MQTT
    assert normalize_scales_source("esphome_direct") == SCALES_SOURCE_ESPHOME


def test_scales_source_uses_mqtt_only_for_mqtt_family():
    assert scales_source_uses_mqtt("mqtt") is True
    assert scales_source_uses_mqtt("esphome_mqtt") is True
    assert scales_source_uses_mqtt("esphome") is False
