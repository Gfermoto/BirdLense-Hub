"""Топики весов MQTT: mqtt_bird_present_topic vs {prefix}/bird_present."""

from __future__ import annotations

from unittest.mock import patch

import mqtt_runtime as mr


def _cfg_get(overrides: dict):
    def get(key, default=None):
        return overrides[key] if key in overrides else default

    return get


def test_scales_mqtt_bird_present_explicit_wins():
    g = _cfg_get(
        {
            "integrations.scales.enabled": True,
            "integrations.scales.source": "mqtt",
            "integrations.scales.mqtt_bird_present_topic": "  frigate/bird_present ",
            "integrations.scales.mqtt_topic_prefix": "other",
        }
    )
    with patch.object(mr.app_config, "get", side_effect=g):
        assert mr.scales_mqtt_bird_present_topic() == "frigate/bird_present"


def test_scales_mqtt_bird_present_from_prefix_when_explicit_empty():
    g = _cfg_get(
        {
            "integrations.scales.enabled": True,
            "integrations.scales.source": "mqtt",
            "integrations.scales.mqtt_bird_present_topic": "",
            "integrations.scales.mqtt_topic_prefix": "frigate",
        }
    )
    with patch.object(mr.app_config, "get", side_effect=g):
        assert mr.scales_mqtt_bird_present_topic() == "frigate/bird_present"


def test_scales_mqtt_bird_present_none_without_prefix_and_explicit():
    g = _cfg_get(
        {
            "integrations.scales.enabled": True,
            "integrations.scales.source": "mqtt",
            "integrations.scales.mqtt_bird_present_topic": "",
            "integrations.scales.mqtt_topic_prefix": "",
        }
    )
    with patch.object(mr.app_config, "get", side_effect=g):
        assert mr.scales_mqtt_bird_present_topic() is None


def test_scales_mqtt_bird_present_disabled():
    g = _cfg_get({"integrations.scales.enabled": False})
    with patch.object(mr.app_config, "get", side_effect=g):
        assert mr.scales_mqtt_bird_present_topic() is None


def test_scales_mqtt_bird_present_not_mqtt_source():
    g = _cfg_get(
        {
            "integrations.scales.enabled": True,
            "integrations.scales.source": "homeassistant",
            "integrations.scales.mqtt_bird_present_topic": "x/y",
        }
    )
    with patch.object(mr.app_config, "get", side_effect=g):
        assert mr.scales_mqtt_bird_present_topic() is None
