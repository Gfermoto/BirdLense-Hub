"""Миграция устаревших ключей user_config (weather.ha_* → homeassistant.*)."""

import copy

import yaml

from app_config.app_config import (
    migrate_legacy_homeassistant_from_weather,
    migrate_legacy_trigger_topics,
    migrate_processor_classifier_best_eu_path,
)
from app_config.trigger_config import (
    get_active_trigger_names,
    get_birdnet_topic,
    get_frigate_topic,
    get_legacy_motion_source_label,
)


def test_migrate_copies_legacy_ha_into_homeassistant():
    user = {
        "weather": {"ha_url": "http://ha.test", "ha_token": "tok1", "source": "homeassistant"},
    }
    assert migrate_legacy_homeassistant_from_weather(user) is True
    assert user["homeassistant"]["url"] == "http://ha.test"
    assert user["homeassistant"]["token"] == "tok1"
    assert "ha_url" not in user["weather"]
    assert "ha_token" not in user["weather"]


def test_migrate_does_not_overwrite_existing_homeassistant():
    user = {
        "homeassistant": {"url": "http://new", "token": "newtok"},
        "weather": {"ha_url": "http://old", "ha_token": "oldtok"},
    }
    assert migrate_legacy_homeassistant_from_weather(user) is True
    assert user["homeassistant"]["url"] == "http://new"
    assert user["homeassistant"]["token"] == "newtok"
    assert "ha_url" not in user["weather"]
    assert "ha_token" not in user["weather"]


def test_migrate_noop_when_no_legacy_keys():
    user = {"weather": {"source": "openweather"}, "homeassistant": {"url": "", "token": ""}}
    orig = copy.deepcopy(user)
    assert migrate_legacy_homeassistant_from_weather(user) is False
    assert user == orig


def test_migrate_partial_only_url_in_weather():
    user = {"weather": {"ha_url": "http://only.url"}}
    assert migrate_legacy_homeassistant_from_weather(user) is True
    assert user["homeassistant"]["url"] == "http://only.url"
    assert "ha_url" not in user["weather"]


def test_migrate_drops_empty_legacy_keys():
    user = {"weather": {"ha_url": "", "ha_token": "   ", "source": "homeassistant"}}
    assert migrate_legacy_homeassistant_from_weather(user) is True
    assert "ha_url" not in user["weather"]
    assert "ha_token" not in user["weather"]


def test_processor_rodent_migration_from_legacy_squirrel_keys(tmp_path, monkeypatch):
    """В merged-конфиге: порог и scope из устаревших ключей → Rodent."""
    from app_config.app_config import app_config

    user_cfg = {
        "processor": {
            "min_confidence_binary_squirrel": 0.21,
            "detector_scope": ["Bird", "Squirrel", "bird"],
            "adaptive_profiles": {
                "enabled": False,
                "night": {
                    "overrides": {
                        "min_confidence_binary_squirrel": 0.19,
                    },
                },
            },
        },
    }
    user_config = tmp_path / "user_config.yaml"
    user_config.write_text(yaml.safe_dump(user_cfg), encoding="utf-8")
    old = app_config.user_config_file
    monkeypatch.setattr(app_config, "user_config_file", str(user_config))
    try:
        app_config.reload()
        assert float(app_config.get("processor.min_confidence_binary_rodent")) == 0.21
        scope = app_config.get("processor.detector_scope") or []
        assert scope == ["Bird", "Rodent"]
        rod_o = (
            (app_config.get("processor.adaptive_profiles") or {})
            .get("night", {})
            .get("overrides", {})
            .get("min_confidence_binary_rodent")
        )
        assert rod_o is not None and abs(float(rod_o) - 0.19) < 1e-9
    finally:
        app_config.user_config_file = old
        app_config.reload()


def test_confidence_floors_skip_when_env_set(tmp_path, monkeypatch):
    from app_config.app_config import app_config

    user_cfg = {"processor": {"min_confidence_binary": 0.1}}
    user_config = tmp_path / "user_config.yaml"
    user_config.write_text(yaml.safe_dump(user_cfg), encoding="utf-8")
    old_user_config_file = app_config.user_config_file
    monkeypatch.setattr(app_config, "user_config_file", str(user_config))
    monkeypatch.setenv("BIRDLENSE_SKIP_CONFIDENCE_FLOORS", "1")

    try:
        app_config.reload()
        assert app_config.get("processor.min_confidence_binary") == 0.1
    finally:
        monkeypatch.delenv("BIRDLENSE_SKIP_CONFIDENCE_FLOORS", raising=False)
        app_config.user_config_file = old_user_config_file
        app_config.reload()


def test_confidence_floors_clamp_legacy_soft_values(tmp_path, monkeypatch):
    from app_config.app_config import app_config

    user_cfg = {
        "detection": {"min_confidence_to_store": 0.05},
        "processor": {
            "min_confidence_binary": 0.1,
            "min_confidence_to_process": 0.03,
            "min_track_duration": 0.2,
            "min_box_size_px": 24,
        },
    }
    user_config = tmp_path / "user_config.yaml"
    user_config.write_text(yaml.safe_dump(user_cfg), encoding="utf-8")
    old_user_config_file = app_config.user_config_file
    monkeypatch.setattr(app_config, "user_config_file", str(user_config))

    try:
        app_config.reload()

        assert app_config.get("detection.min_confidence_to_store") == 0.22
        assert app_config.get("processor.min_confidence_binary") == 0.22
        assert app_config.get("processor.min_confidence_to_process") == 0.24
        assert app_config.get("processor.min_track_duration") == 0.35
        assert app_config.get("processor.min_box_size_px") == 24

        app_config.save()
        saved = yaml.safe_load(user_config.read_text(encoding="utf-8")) or {}
        assert float(saved["detection"]["min_confidence_to_store"]) == 0.22
        assert float(saved["processor"]["min_confidence_binary"]) == 0.22
        assert float(saved["processor"]["min_confidence_to_process"]) == 0.24
        assert float(saved["processor"]["min_track_duration"]) == 0.35
        assert int(saved["processor"]["min_box_size_px"]) == 24
    finally:
        app_config.user_config_file = old_user_config_file
        app_config.reload()


def test_migrate_legacy_trigger_topics_copies_into_new_domains():
    user = {
        "mqtt": {
            "frigate_topic": "custom/frigate",
            "birdnet_topic": "custom/birdnet",
        }
    }

    assert migrate_legacy_trigger_topics(user) is True
    assert user["triggers"]["frigate"]["topic"] == "custom/frigate"
    assert user["integrations"]["birdnet"]["mqtt_topic"] == "custom/birdnet"


def test_grouped_trigger_helpers_read_triggers_flat():
    cfg = {
        "mqtt": {"broker": "mqtt.local", "frigate_topic": "frigate/events"},
        "triggers": {
            "opencv": {"enabled": True},
            "frigate": {"enabled": True},
            "motion_sensor": {
                "enabled": True,
                "source": "esphome",
                "esphome_url": "http://esp",
                "esphome_sensor_id": "pir",
            },
        },
        "integrations": {"scales": {"motion_trigger_enabled": True, "source": "mqtt"}},
    }

    def _get(key, default=None):
        current = cfg
        for part in key.split("."):
            if not isinstance(current, dict) or part not in current:
                return default
            current = current[part]
        return current

    assert get_frigate_topic(_get) == "frigate/events"
    assert get_birdnet_topic(_get) == "birdnet"
    assert get_active_trigger_names(_get, mqtt_broker="mqtt.local") == [
        "opencv",
        "frigate",
        "motion_sensor",
        "scales",
    ]
    assert get_legacy_motion_source_label(_get, mqtt_broker="mqtt.local") == ("opencv,frigate,motion_sensor,scales")


def test_fold_legacy_motion_does_not_force_frigate_enabled():
    """Смерженный default ``motion.source`` не должен перетирать ``triggers.frigate.enabled`` (#fold-only)."""
    from app_config.trigger_config import fold_legacy_motion_out_of_merged_config

    merged = {
        "motion": {
            "source": "frigate",
            "frigate_label_filter": ["bird"],
        },
        "triggers": {
            "opencv": {"enabled": True},
            "frigate": {"enabled": False, "topic": "frigate/events"},
        },
    }
    fold_legacy_motion_out_of_merged_config(merged)
    assert "motion" not in merged
    assert merged["triggers"]["frigate"]["enabled"] is False
    assert merged["triggers"]["frigate"]["label_filter"] == ["bird"]


def test_migrate_legacy_motion_block_moves_into_triggers():
    from app_config.trigger_config import migrate_legacy_motion_block

    user = {
        "motion": {
            "source": "esphome",
            "esphome_url": "http://esp",
            "esphome_sensor_id": "pir",
            "frigate_label_filter": ["bird"],
        }
    }
    assert migrate_legacy_motion_block(user) is True
    assert "motion" not in user
    assert user["triggers"]["motion_sensor"]["enabled"] is True
    assert user["triggers"]["motion_sensor"]["source"] == "esphome"
    assert user["triggers"]["frigate"]["label_filter"] == ["bird"]


def test_migrate_processor_classifier_best_eu_relative_path():
    user = {
        "processor": {
            "models": {"classifier": "models/classification/weights/best_EU.pt"},
        },
    }
    assert migrate_processor_classifier_best_eu_path(user) is True
    assert user["processor"]["models"]["classifier"] == ("models/classification/weights/best.pt")


def test_migrate_processor_classifier_best_eu_absolute_path():
    user = {
        "processor": {
            "models": {
                "classifier": "/app/processor/models/classification/weights/best_EU.pt",
            },
        },
    }
    assert migrate_processor_classifier_best_eu_path(user) is True
    assert user["processor"]["models"]["classifier"] == ("models/classification/weights/best.pt")


def test_migrate_processor_classifier_unchanged_for_canonical():
    user = {
        "processor": {
            "models": {"classifier": "models/classification/weights/best.pt"},
        },
    }
    assert migrate_processor_classifier_best_eu_path(user) is False


def test_fold_motion_settings_patch_into_triggers():
    from app_config.trigger_config import fold_motion_settings_patch_into_triggers

    updates = {
        "motion": {
            "frigate_label_exclude": ["cat", "dog"],
            "frigate_label_filter": ["bird"],
        },
        "triggers": {"frigate": {"enabled": True, "min_trigger_score": 0.5}},
    }
    fold_motion_settings_patch_into_triggers(updates)
    assert "motion" not in updates
    assert updates["triggers"]["frigate"]["label_exclude"] == ["cat", "dog"]
    assert updates["triggers"]["frigate"]["label_filter"] == ["bird"]
    assert updates["triggers"]["frigate"]["min_trigger_score"] == 0.5


def test_normalize_settings_patch_folds_motion_into_triggers():
    from services.settings_patch_service import normalize_settings_patch_updates

    out = normalize_settings_patch_updates(
        {
            "motion": {
                "frigate_label_filter": ["bird"],
                "frigate_label_exclude": ["cat"],
            }
        },
        access_role="admin",
        contributor_tier_configured=False,
    )
    assert "motion" not in out
    assert out["triggers"]["frigate"]["label_filter"] == ["bird"]
    assert out["triggers"]["frigate"]["label_exclude"] == ["cat"]
