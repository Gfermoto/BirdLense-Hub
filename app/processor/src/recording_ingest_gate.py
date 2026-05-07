"""Ingest gate helpers for finalized recordings."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def log_missing_video_gate(
    api: Any,
    *,
    detection_count: int,
    video_path_for_api: str,
    video_output: str,
) -> None:
    if not api:
        return
    try:
        api.activity_log(
            type="ingest_gate",
            data={
                "reason": "video_file_missing",
                "stage": "processor_finalize",
                "video_path": video_path_for_api,
                "video_output": video_output,
                "detection_count": int(detection_count),
            },
        )
    except Exception:
        logger.exception("ingest_gate activity_log failed")
