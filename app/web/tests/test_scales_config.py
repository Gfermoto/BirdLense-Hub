from pathlib import Path

import yaml

from app_config.app_config import migrate_legacy_scales_source
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


def test_esphome_default_weight_sensor_id_matches_repo_firmware():
    root = Path(__file__).resolve().parents[2]
    default_cfg = yaml.safe_load((root / "app_config" / "default_config.yaml").read_text())
    user_cfg = yaml.safe_load((root / "app_config" / "user_config.yaml").read_text())

    assert default_cfg["integrations"]["scales"]["esphome_weight_sensor_id"] == "weight_live_internal"
    assert user_cfg["integrations"]["scales"]["esphome_weight_sensor_id"] == "weight_live_internal"


def test_migrate_legacy_scales_source_fixes_bad_esphome_weight_sensor_default():
    user = {
        "integrations": {
            "scales": {
                "source": "esphome",
                "esphome_weight_sensor_id": "raw_hx711",
            }
        }
    }

    assert migrate_legacy_scales_source(user) is True
    assert user["integrations"]["scales"]["esphome_weight_sensor_id"] == "weight_live_internal"
