"""Runtime platform profile (BIRDLENSE_PLATFORM) for logging and ops."""

from __future__ import annotations

import logging
import os
from typing import Final

logger = logging.getLogger(__name__)

KNOWN_PLATFORMS: Final[frozenset[str]] = frozenset({"intel_nuc", "jetson_nano"})
DEFAULT_PLATFORM: Final[str] = "intel_nuc"


def normalize_platform(raw: str | None = None) -> str:
    """Return canonical platform id: intel_nuc | jetson_nano."""
    value = (raw if raw is not None else os.environ.get("BIRDLENSE_PLATFORM", "")).strip()
    value = value.replace("-", "_").lower()
    if not value:
        return DEFAULT_PLATFORM
    if value in KNOWN_PLATFORMS:
        return value
    logger.warning("Unknown BIRDLENSE_PLATFORM=%r — treating as %s", value, DEFAULT_PLATFORM)
    return DEFAULT_PLATFORM


def log_platform_profile() -> str:
    """Log resolved platform once at processor startup; return canonical id."""
    platform = normalize_platform()
    logger.info(
        "Platform profile: %s (BIRDLENSE_PLATFORM env=%r)",
        platform,
        os.environ.get("BIRDLENSE_PLATFORM"),
    )
    return platform
