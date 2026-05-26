"""Pydantic merged-config validation (SOTA-01 / #492)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
import yaml

from app_config.app_config import AppConfig, validate_merged_config_semantics
from app_config.config_schema import (
    BirdlenseMergedConfig,
    validate_merged_config_pydantic,
    write_config_json_schema,
)


def _default_config_path() -> Path:
    return Path(__file__).resolve().parents[2] / "app_config" / "default_config.yaml"


def test_default_config_yaml_passes_pydantic():
    raw = yaml.safe_load(_default_config_path().read_text(encoding="utf-8")) or {}
    issues = validate_merged_config_pydantic(raw)
    assert issues == [], issues


def test_pydantic_rejects_invalid_confidence():
    merged = {
        "processor": {"min_confidence_binary": 1.5},
        "detection": {"min_confidence_to_store": 0.1},
    }
    issues = validate_merged_config_pydantic(merged)
    assert any("min_confidence_binary" in msg for msg in issues)


def test_pydantic_rejects_store_gt_process():
    merged = {
        "detection": {"min_confidence_to_store": 0.5},
        "processor": {"min_confidence_to_process": 0.3},
    }
    issues = validate_merged_config_pydantic(merged)
    assert len(issues) >= 1
    assert any("min_confidence_to_store" in msg for msg in issues)


def test_pydantic_static_motion_calibration_fields():
    merged = {
        "processor": {
            "static_object_suppression_enabled": True,
            "static_scene_bird_min_confidence": 0.3,
            "static_temporal_max_jitter_px": 2.5,
            "background_subtraction_var_threshold": 18.0,
        },
        "detection": {"min_confidence_to_store": 0.1},
    }
    issues = validate_merged_config_pydantic(merged)
    assert issues == [], issues


def test_pydantic_accepts_extra_unknown_processor_keys():
    merged = {
        "processor": {
            "min_confidence_binary": 0.2,
            "future_experimental_flag": True,
        },
        "detection": {"min_confidence_to_store": 0.1},
    }
    issues = validate_merged_config_pydantic(merged)
    assert issues == []


def test_pydantic_inference_lores_wh_pair():
    model = BirdlenseMergedConfig.model_validate(
        {"processor": {"inference_lores_wh": [704, 576]}},
    )
    assert model.processor is not None
    assert model.processor.inference_lores_wh == [704, 576]


def test_pydantic_invalid_lores_wh():
    issues = validate_merged_config_pydantic(
        {"processor": {"inference_lores_wh": [704]}},
    )
    assert issues


def test_app_config_load_merged_includes_pydantic(monkeypatch):
    monkeypatch.delenv("BIRDLENSE_STRICT_CONFIG", raising=False)
    cfg = AppConfig(
        user_config="__nonexistent_user_test__.yaml",
        default_config="default_config.yaml",
    )
    assert cfg.get("processor.detection_strategy") == "two_stage"


def test_validate_user_config_tree_uses_pydantic():
    ac = AppConfig(user_config="__nonexistent_user_test__.yaml")
    issues = ac.validate_user_config_tree(
        {"processor": {"min_confidence_binary": "not-a-number"}},
    )
    assert issues


def test_write_config_json_schema(tmp_path):
    path = write_config_json_schema(tmp_path / "schema.json")
    assert path.is_file()
    assert "properties" in path.read_text(encoding="utf-8")


def test_pydantic_validate_can_be_disabled(monkeypatch):
    monkeypatch.setenv("BIRDLENSE_PYDANTIC_CONFIG_VALIDATE", "0")
    issues = validate_merged_config_pydantic(
        {"processor": {"min_confidence_binary": 99}},
    )
    assert issues == []


def test_semantics_and_pydantic_both_run():
    merged = {
        "detection": {"min_confidence_to_store": 0.4},
        "processor": {"min_confidence_to_process": 0.3},
    }
    sem = validate_merged_config_semantics(merged)
    pyd = validate_merged_config_pydantic(merged)
    assert sem
    assert pyd
