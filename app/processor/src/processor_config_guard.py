"""Processor startup config guard (#492)."""

from __future__ import annotations

import logging
import sys

logger = logging.getLogger(__name__)


def assert_processor_config_valid() -> None:
    """Fail fast before loading YOLO when merged config is invalid."""
    try:
        from app_config.config_guard import ensure_config_valid_or_raise
    except ImportError:
        from config_guard import ensure_config_valid_or_raise  # type: ignore

    try:
        ensure_config_valid_or_raise(for_processor=True)
    except ValueError as exc:
        logger.critical("%s", exc)
        sys.exit(1)
