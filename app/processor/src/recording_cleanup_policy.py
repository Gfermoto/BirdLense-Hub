"""Cleanup policy helpers for finalized recordings."""

from __future__ import annotations

from typing import Any


def should_keep_empty_recording(config: Any) -> bool:
    keep_empty = bool(
        config.get(
            "processor.keep_recording_when_no_detections",
        )
    )
    file_source = str(config.get("video.source") or "").strip().lower() == "file"
    return keep_empty and file_source
