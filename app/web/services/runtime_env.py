"""Shared runtime environment helpers for Flask/web services."""

from __future__ import annotations

import os


def env_flag_enabled(raw: str | None) -> bool:
    """Return True for common env truthy values."""
    return (raw or "").strip().lower() in {"1", "true", "yes", "on"}


def is_production_runtime() -> bool:
    """Return True when FLASK_ENV or BIRDLENSE_ENV indicates production."""
    values = {
        (os.environ.get("FLASK_ENV") or "").strip().lower(),
        (os.environ.get("BIRDLENSE_ENV") or "").strip().lower(),
    }
    return any(value in {"production", "prod"} for value in values)
