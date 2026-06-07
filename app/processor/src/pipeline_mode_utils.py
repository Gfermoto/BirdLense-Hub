"""Pipeline mode helpers without heavy linear_pipeline imports (safe for detection_quality)."""

from __future__ import annotations

from typing import Any

from processor_config_defaults import PIPELINE_MODE


def pipeline_mode(app_config: Any) -> str:
    return str(app_config.get("processor.pipeline_mode") or PIPELINE_MODE).strip().lower()


def is_linear_pipeline(app_config: Any) -> bool:
    return pipeline_mode(app_config) in {"linear", "simple"}


def linear_disable_legacy_quality_gates(app_config: Any) -> bool:
    """Linear: skip legacy static/MOG2/motion-global veto so tracks are not starved."""
    return is_linear_pipeline(app_config)


def linear_live_scoring_engine_enabled(app_config: Any) -> bool:
    """ScoringEngine on live frames in linear mode (phantom/static FP filter)."""
    if not is_linear_pipeline(app_config):
        return True
    raw = app_config.get("processor.linear_live_scoring_engine_enabled")
    if raw is None:
        return True
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def linear_disable_live_quality_gates(app_config: Any) -> bool:
    """Deprecated alias — legacy gates only."""
    return linear_disable_legacy_quality_gates(app_config)
