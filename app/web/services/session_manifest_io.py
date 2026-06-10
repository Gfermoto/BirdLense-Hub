"""Read session manifest.json from recording dir (web import/reconcile)."""

from __future__ import annotations

import json
import os
import time
from datetime import datetime
from typing import Any

_IN_PROGRESS_STATES = frozenset({"recording", "persisting"})
_TERMINAL_IMPORT_STATES = frozenset({"ready", "failed"})
_PROCESSOR_TMP_MARKERS = ("video.h264.tmp.mp4",)


def read_session_manifest(session_dir: str) -> dict[str, Any] | None:
    manifest_path = os.path.join(session_dir, "manifest.json")
    if not os.path.isfile(manifest_path):
        return None
    try:
        raw = json.loads(open(manifest_path, encoding="utf-8").read())
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return None
    return raw if isinstance(raw, dict) else None


def _parse_manifest_ts(raw: dict[str, Any], key: str) -> datetime | None:
    val = raw.get(key)
    if not val:
        return None
    try:
        return datetime.fromisoformat(str(val).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def read_session_manifest_times(session_dir: str) -> tuple[datetime | None, datetime | None]:
    raw = read_session_manifest(session_dir)
    if not raw:
        return None, None
    return _parse_manifest_ts(raw, "start_time"), _parse_manifest_ts(raw, "end_time")


def read_session_manifest_state(session_dir: str) -> str | None:
    raw = read_session_manifest(session_dir)
    if not raw:
        return None
    state = raw.get("state")
    if state is None:
        return None
    return str(state).strip().lower() or None


def session_has_processor_in_progress_marker(session_dir: str) -> bool:
    """True when processor sidecar indicates an active or persisting recording."""
    state = read_session_manifest_state(session_dir)
    if state in _IN_PROGRESS_STATES:
        return True
    try:
        names = set(os.listdir(session_dir))
    except OSError:
        return False
    return any(name in names for name in _PROCESSOR_TMP_MARKERS)


def session_importable_from_disk(
    session_dir: str,
    video_mp4: str,
    *,
    grace_minutes: float,
    min_bytes: int,
) -> tuple[bool, str | None]:
    """Whether scan/reconcile may create a Video row for this session dir."""
    if session_has_processor_in_progress_marker(session_dir):
        return False, "in_progress"

    raw = read_session_manifest(session_dir)
    state = None if not raw else str(raw.get("state") or "").strip().lower() or None
    if state in _TERMINAL_IMPORT_STATES:
        if raw and _parse_manifest_ts(raw, "end_time") is not None:
            return True, None
        return False, "manifest_missing_end_time"

    try:
        size = os.path.getsize(video_mp4)
    except OSError:
        return False, "unreadable"

    if size <= 0:
        return False, "empty"

    try:
        age_sec = time.time() - os.path.getmtime(video_mp4)
    except OSError:
        age_sec = float("inf")

    if age_sec < grace_minutes * 60.0:
        return False, "recent_mtime"

    if size < min_bytes:
        return False, "below_min_bytes"

    return True, None


def orphan_purge_grace_skip(
    session_dir: str,
    *,
    video_bytes: int,
    grace_minutes: float,
    min_bytes: int,
) -> bool:
    """True when orphan purge must skip this session (active or too fresh/small)."""
    if session_has_processor_in_progress_marker(session_dir):
        return True

    mp4 = os.path.join(session_dir, "video.mp4")
    try:
        age_sec = time.time() - os.path.getmtime(mp4)
    except OSError:
        age_sec = float("inf")

    if age_sec < grace_minutes * 60.0:
        return True

    nbytes = int(video_bytes or 0)
    if nbytes == 0:
        raw = read_session_manifest(session_dir)
        if raw is not None:
            state = str(raw.get("state") or "").strip().lower() or None
            if state is not None and state not in _TERMINAL_IMPORT_STATES:
                return True
        return False

    if nbytes < min_bytes:
        return True

    return False
