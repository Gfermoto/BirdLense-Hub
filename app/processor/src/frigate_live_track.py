"""Optional Frigate MQTT bbox cache for live overlay when YOLO has no track.

BirdLense is standalone-first: OpenCV/weight/MQTT triggers + own YOLO+ByteTrack are the
product core. This module is used only when Frigate is present in the environment —
never required for recording, species, or notify.
"""

from __future__ import annotations

import threading
import time
from typing import Any, Iterable

_lock = threading.Lock()
_by_camera: dict[str, dict[str, Any]] = {}

_BIRD_LABELS = frozenset({"bird", "birds"})


def _is_bird_label(labels: Iterable[str] | None) -> bool:
    if not labels:
        return False
    for raw in labels:
        key = str(raw or "").strip().lower()
        if key in _BIRD_LABELS or key.startswith("bird"):
            return True
    return False


def update_frigate_live_track(
    camera_id: str,
    *,
    bbox_norm: list[float] | None,
    score: float = 0.0,
    event_id: str | None = None,
    event_type: str = "",
    labels: Iterable[str] | None = None,
) -> None:
    """Store or clear the latest Frigate bird bbox for a camera."""
    cid = str(camera_id or "").strip()
    if not cid:
        return
    ev_type = str(event_type or "").strip().lower()
    with _lock:
        if ev_type == "end":
            cur = _by_camera.get(cid)
            if cur and event_id and str(cur.get("event_id") or "") == str(event_id):
                _by_camera.pop(cid, None)
            return
        if not bbox_norm or len(bbox_norm) < 4:
            return
        if labels is not None and not _is_bird_label(labels):
            return
        try:
            box = [float(bbox_norm[i]) for i in range(4)]
        except (TypeError, ValueError, IndexError):
            return
        if box[2] <= box[0] or box[3] <= box[1]:
            return
        _by_camera[cid] = {
            "bbox_norm": box,
            "score": float(score or 0.0),
            "event_id": str(event_id or ""),
            "updated_at": time.time(),
            "source": "frigate",
        }


def get_frigate_live_bbox(camera_id: str, *, max_age_sec: float | None = None) -> list[float] | None:
    """Return fresh normalized xyxy bbox or None."""
    cid = str(camera_id or "").strip()
    if not cid:
        return None
    if max_age_sec is None:
        try:
            from app_config.app_config import app_config

            max_age_sec = float(app_config.get("ui.frigate_live_bbox_max_age_seconds") or 2.5)
        except (TypeError, ValueError):
            max_age_sec = 2.5
    max_age_sec = max(0.2, min(30.0, float(max_age_sec)))
    with _lock:
        row = _by_camera.get(cid)
        if not row:
            return None
        age = time.time() - float(row.get("updated_at") or 0.0)
        if age > max_age_sec:
            return None
        bbox = row.get("bbox_norm")
        if isinstance(bbox, list) and len(bbox) >= 4:
            return list(bbox)
        return None


def clear_frigate_live_track(camera_id: str) -> None:
    cid = str(camera_id or "").strip()
    if not cid:
        return
    with _lock:
        _by_camera.pop(cid, None)


def snapshot_frigate_live_tracks() -> dict[str, dict[str, Any]]:
    with _lock:
        return {k: dict(v) for k, v in _by_camera.items()}
