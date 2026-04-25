"""Notification error helpers for finalized recordings."""

from __future__ import annotations

from typing import Any


def notify_error_hint(error: Any) -> str:
    response = getattr(error, "response", None)
    if response is None:
        return ""
    hint = ""
    if response.status_code == 403:
        hint = " (check PROCESSOR_SECRET in app/.env)"
    return f" {response.status_code}{hint}"
