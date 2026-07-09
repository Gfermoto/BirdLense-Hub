"""Restore dense ByteTrack frames on persist rows (CV-G / Frigate lifecycle parity)."""

from __future__ import annotations

import logging
from typing import Any

from track_first_contract import valid_track_frames

logger = logging.getLogger(__name__)


def _track_id_matches(left: Any, right: Any) -> bool:
    if left is None or right is None:
        return False
    try:
        return int(left) == int(right)
    except (TypeError, ValueError):
        return str(left) == str(right)


def restore_dense_persist_frames(
    video_detections: list[dict[str, Any]] | None,
    session_tracks: dict[Any, dict[str, Any]] | None,
    *,
    min_runtime_frames: int = 4,
    min_persist_frames: int = 3,
) -> tuple[list[dict[str, Any]], int]:
    """Backfill sparse YOLO persist rows from runtime tracks when fusion dropped frame density."""
    tracks = session_tracks or {}
    out: list[dict[str, Any]] = []
    restored = 0
    for row in video_detections or []:
        item = dict(row)
        if str(item.get("source") or "").strip().lower() != "video":
            out.append(item)
            continue
        if str(item.get("detection_provider") or "").strip().lower() != "yolo":
            out.append(item)
            continue
        track = None
        tid = item.get("track_id")
        for track_key, track_val in tracks.items():
            if _track_id_matches(tid, track_key) and isinstance(track_val, dict):
                track = track_val
                break
        if track is None:
            out.append(item)
            continue
        runtime_frames = valid_track_frames(track.get("frames"))
        persist_frames = valid_track_frames(item.get("frames"))
        if len(runtime_frames) < max(1, int(min_runtime_frames)):
            out.append(item)
            continue
        if len(persist_frames) >= len(runtime_frames):
            out.append(item)
            continue
        if len(persist_frames) >= max(1, int(min_persist_frames)):
            out.append(item)
            continue
        item["frames"] = runtime_frames
        item["dense_track_restored"] = True
        item["dense_track_restored_from_count"] = len(persist_frames)
        restored += 1
        logger.info(
            "dense_track_persist: restored track_id=%s frames %s→%s",
            tid,
            len(persist_frames),
            len(runtime_frames),
        )
        out.append(item)
    return out, restored
