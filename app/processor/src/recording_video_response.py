"""Video API response helpers for finalized recordings."""

from __future__ import annotations

from typing import Any


def response_video_id(response: Any) -> Any:
    if not isinstance(response, dict):
        return None
    return response.get("video_id")
