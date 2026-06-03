"""Read session manifest.json from recording dir (web import/reconcile)."""

from __future__ import annotations

import json
import os
from datetime import datetime


def read_session_manifest_times(session_dir: str) -> tuple[datetime | None, datetime | None]:
    manifest_path = os.path.join(session_dir, "manifest.json")
    if not os.path.isfile(manifest_path):
        return None, None
    try:
        raw = json.loads(open(manifest_path, encoding="utf-8").read())
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return None, None
    if not isinstance(raw, dict):
        return None, None

    def _parse_ts(key: str) -> datetime | None:
        val = raw.get(key)
        if not val:
            return None
        try:
            return datetime.fromisoformat(str(val).replace("Z", "+00:00"))
        except (TypeError, ValueError):
            return None

    return _parse_ts("start_time"), _parse_ts("end_time")
