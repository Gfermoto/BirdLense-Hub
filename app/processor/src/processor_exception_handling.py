"""Shared helpers for narrowing broad ``except Exception`` in hot paths (#619)."""

from __future__ import annotations

import logging
from typing import Any


def reraise_if_critical(exc: BaseException) -> None:
    """Re-raise process-fatal errors that must not be swallowed."""
    if isinstance(exc, (MemoryError, KeyboardInterrupt, SystemExit)):
        raise exc


def reraise_if_io_critical(exc: BaseException) -> None:
    """Re-raise MemoryError/OSError for persist/finalize hot paths."""
    reraise_if_critical(exc)
    if isinstance(exc, OSError):
        raise exc


def log_handled_exception(
    logger: logging.Logger,
    exc: BaseException,
    message: str,
    *,
    level: int = logging.WARNING,
    **context: Any,
) -> None:
    """Log a handled non-critical exception with optional structured context."""
    reraise_if_critical(exc)
    if context:
        ctx = " ".join(f"{key}={value!r}" for key, value in sorted(context.items()))
        logger.log(level, "%s (%s)", message, ctx, exc_info=exc)
    else:
        logger.log(level, message, exc_info=exc)
