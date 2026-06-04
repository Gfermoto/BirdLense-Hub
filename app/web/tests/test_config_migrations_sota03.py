"""SOTA-03: versioned user_config migrations and PATCH warnings."""

from __future__ import annotations

import yaml

from app_config.config_migrations import (
    USER_CONFIG_SCHEMA_VERSION,
    current_schema_version,
    deprecated_keys_present,
    run_user_config_migrations,
)


def test_run_user_config_migrations_sets_schema_version():
    user = {"weather": {"ha_url": "http://ha", "ha_token": "t"}}
    assert run_user_config_migrations(user) is True
    assert current_schema_version(user) == USER_CONFIG_SCHEMA_VERSION
    assert "ha_url" not in (user.get("weather") or {})


def test_deprecated_keys_present_detects_legacy_weather():
    user = {"weather": {"ha_url": "http://x"}}
    keys = deprecated_keys_present(user)
    assert "weather.ha_url" in keys


def test_track_first_migration_adds_opencv_and_persist_mode():
    user = {
        "processor": {"detect_scheduler_triggers": ["frigate", "motion_sensor"]},
        "detection": {"strip_review_only_overlay_frames": True},
    }
    assert run_user_config_migrations(user) is True
    assert "opencv" in user["processor"]["detect_scheduler_triggers"]
    assert user["detection"]["strip_review_only_overlay_frames"] is False
    assert user["detection"]["persist_mode"] == "binary_track_first"
    assert user["detection"]["track_first_gate_enabled"] is True
    assert current_schema_version(user) == USER_CONFIG_SCHEMA_VERSION


def test_track_first_migration_sets_tuning_role_on_known_cameras():
    user = {
        "video": {
            "cameras": [
                {"id": "BirdBox", "stream_name": "birdbox"},
                {"id": "Forest", "stream_name": "forest"},
            ]
        },
    }
    assert run_user_config_migrations(user) is True
    assert user["video"]["cameras"][0]["tuning_role"] == "feeder_close"
    assert user["video"]["cameras"][1]["tuning_role"] == "feeder_far"


def test_classification_first_migration_disables_arbitration_layers():
    user = {
        "detection": {
            "weighted_arbiter_enabled": True,
            "hypothesis_arbitration_enabled": True,
            "yolo_weak_track_salvage_enabled": True,
        },
        "processor": {"bird_skip_classifier_max_area_frac": 0.015},
    }
    assert run_user_config_migrations(user) is True
    assert user["detection"]["weighted_arbiter_enabled"] is False
    assert user["detection"]["hypothesis_arbitration_enabled"] is False
    assert user["detection"]["yolo_weak_track_salvage_enabled"] is False
    assert user["processor"]["bird_skip_classifier_max_area_frac"] == 0
    assert user["processor"]["classifier_best_guess_enabled"] is True
    assert current_schema_version(user) == USER_CONFIG_SCHEMA_VERSION


def test_classification_reliability_migration_lowers_birder_and_static_far():
    user = {
        "processor": {
            "birder_eu_min_confidence": 0.18,
            "classifier_best_guess_min_events": 2,
        },
    }
    assert run_user_config_migrations(user) is True
    assert user["processor"]["birder_eu_min_confidence"] == 0.15
    assert user["processor"]["classifier_best_guess_min_events"] == 1
    assert user["processor"]["camera_tuning_by_role"]["feeder_far"]["track_static_reject_enabled"] is False
    assert current_schema_version(user) == USER_CONFIG_SCHEMA_VERSION


def test_linear_pipeline_migration_sets_mode():
    user = {"processor": {}}
    assert run_user_config_migrations(user) is True
    assert user["processor"]["pipeline_mode"] == "linear"
    assert current_schema_version(user) == USER_CONFIG_SCHEMA_VERSION


def test_settings_patch_returns_deprecated_warnings(tmp_path, monkeypatch):
    from app_config.app_config import app_config
    from services.settings_patch_service import apply_settings_patch_from_request

    user_path = tmp_path / "user_config.yaml"
    user_path.write_text(
        yaml.safe_dump({"weather": {"ha_url": "http://legacy"}}),
        encoding="utf-8",
    )
    monkeypatch.setattr(app_config, "user_config_file", str(user_path))
    assert "weather.ha_url" in deprecated_keys_present(app_config.load_raw_user_config_dict())

    payload = apply_settings_patch_from_request(
        {"general": {"app_name": "BirdLense Test"}},
        access_role="admin",
        contributor_tier_configured=False,
    )
    warnings = payload.get("settings_warnings", {}).get("deprecated_keys_present")
    assert warnings
    assert "weather.ha_url" in warnings
