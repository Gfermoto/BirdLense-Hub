"""Fail-fast merged config validation for Hub web and processor (#492)."""

from __future__ import annotations

import logging
import os

from app_config.app_config import (
    AppConfig,
    validate_merged_config,
    validate_merged_config_semantics,
)
from app_config.config_schema import validate_merged_config_pydantic

logger = logging.getLogger(__name__)


def collect_merged_config_issues(merged: dict | None = None) -> list[str]:
    """Run structural, semantic and Pydantic checks on merged YAML."""
    if merged is None:
        ac = AppConfig()
        merged = ac.load_and_merge_configs()
    issues: list[str] = []
    issues.extend(validate_merged_config(merged))
    issues.extend(validate_merged_config_semantics(merged))
    issues.extend(validate_merged_config_pydantic(merged))
    return issues


def strict_config_enabled(*, for_processor: bool = False) -> bool:
    raw = (os.environ.get("BIRDLENSE_STRICT_CONFIG") or "").strip().lower()
    if raw in ("0", "false", "no", "off"):
        return False
    if raw in ("1", "true", "yes", "on"):
        return True
    if for_processor:
        proc = (os.environ.get("BIRDLENSE_PROCESSOR_STRICT_CONFIG") or "1").strip().lower()
        if proc in ("0", "false", "no", "off"):
            return False
        return True
    env = (os.environ.get("BIRDLENSE_ENV") or os.environ.get("FLASK_ENV") or "").strip().lower()
    return env in ("production", "prod")


def ensure_config_valid_or_raise(*, for_processor: bool = False) -> None:
    """Raise ValueError when strict mode is on and merged config has issues."""
    issues = collect_merged_config_issues()
    for msg in issues:
        logger.error("Config validation: %s", msg)
    if issues and strict_config_enabled(for_processor=for_processor):
        who = "processor" if for_processor else "hub"
        raise ValueError(
            "%s config invalid (%s issue(s)): %s"
            % (who, len(issues), "; ".join(issues[:8])),
        )
