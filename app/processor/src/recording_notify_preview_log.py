"""Notification preview activity-log helpers for finalized recordings."""

from __future__ import annotations

import logging
from typing import Any


def write_notify_preview_activity(
    api: Any,
    *,
    species: str,
    video_id: Any,
    preview_source: str | None,
    image_base64: str | None,
) -> None:
    if not api:
        return
    try:
        api.activity_log(
            type="notify_preview_generated",
            data={
                "species": species,
                "video_id": video_id,
                "preview_source": preview_source,
                "has_image": bool(image_base64),
            },
        )
    except Exception as err:
        logging.warning("notify_preview activity_log failed: %s", err)
