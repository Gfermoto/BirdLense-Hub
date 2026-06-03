"""Sidecar manifest.json per recording session (FinalizeTransaction / reconcile)."""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

MANIFEST_FILENAME = "manifest.json"
SCHEMA = "recording_session_manifest@v1"


def _manifest_path(session_dir: str) -> str:
    return os.path.join(session_dir, MANIFEST_FILENAME)


def _read_manifest(session_dir: str) -> dict[str, Any]:
    path = _manifest_path(session_dir)
    if not os.path.isfile(path):
        return {}
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return {}


def _write_manifest(session_dir: str, data: dict[str, Any]) -> None:
    path = _manifest_path(session_dir)
    os.makedirs(session_dir, exist_ok=True)
    payload = {
        "schema": SCHEMA,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        **data,
    }
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    os.replace(tmp, path)


def write_recording_started(
    session_dir: str,
    *,
    video_path_logical: str,
    start_time: datetime,
    camera_id: str | None = None,
    camera_slot: str | None = None,
    trigger_source: str | None = None,
) -> None:
    _write_manifest(
        session_dir,
        {
            "state": "recording",
            "video_path": video_path_logical,
            "start_time": start_time.astimezone(timezone.utc).isoformat(),
            "camera_id": camera_id,
            "camera_slot": camera_slot,
            "trigger_source": trigger_source,
        },
    )


def mark_persist_started(session_dir: str, *, end_time: datetime | None = None) -> None:
    data = _read_manifest(session_dir)
    data["state"] = "persisting"
    if end_time is not None:
        data["end_time"] = end_time.astimezone(timezone.utc).isoformat()
    _write_manifest(session_dir, data)


def mark_persist_ready(session_dir: str, *, video_id: int, end_time: datetime | None = None) -> None:
    data = _read_manifest(session_dir)
    data["state"] = "ready"
    data["video_id"] = int(video_id)
    if end_time is not None:
        data["end_time"] = end_time.astimezone(timezone.utc).isoformat()
    _write_manifest(session_dir, data)


def mark_persist_failed(
    session_dir: str,
    *,
    reason: str,
    end_time: datetime | None = None,
) -> None:
    data = _read_manifest(session_dir)
    data["state"] = "failed"
    data["fail_reason"] = str(reason)[:500]
    if end_time is not None:
        data["end_time"] = end_time.astimezone(timezone.utc).isoformat()
    _write_manifest(session_dir, data)
