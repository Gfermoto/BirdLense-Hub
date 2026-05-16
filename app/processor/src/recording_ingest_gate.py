"""Ingest gate helpers for finalized recordings."""

from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)


def log_missing_video_gate(
    api: Any,
    *,
    detection_count: int,
    video_path_for_api: str,
    video_output: str,
) -> None:
    """Record ingest gate when detections exist but output video is invalid."""
    if not api:
        return
    exists = os.path.isfile(video_output)
    size_bytes = 0
    if exists:
        try:
            size_bytes = int(os.path.getsize(video_output))
        except OSError:
            size_bytes = 0
    reason_code = "REC_FILE_UNPLAYABLE" if exists else "REC_FILE_MISSING"
    try:
        api.activity_log(
            type="ingest_gate",
            data={
                "reason": "video_file_missing",
                "reason_code": reason_code,
                "stage": "processor_finalize",
                "video_path": video_path_for_api,
                "video_output": video_output,
                "detection_count": int(detection_count),
                "file_exists": bool(exists),
                "file_size_bytes": int(size_bytes),
            },
        )
    except Exception:
        logger.exception("ingest_gate activity_log failed")
