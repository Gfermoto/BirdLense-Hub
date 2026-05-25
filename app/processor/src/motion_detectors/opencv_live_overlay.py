"""In-memory Live overlay snapshots (OpenCV motion + YOLO boxes) per camera."""

from __future__ import annotations

import threading
import time
from typing import Any

_lock = threading.Lock()
_by_camera: dict[str, dict[str, Any]] = {}
_live_detectors: dict[str, Any] = {}


def register_opencv_live_detector(camera_id: str, detector: Any) -> None:
    """Register detector for background Live overlay refresh (independent of detect())."""
    cid = str(camera_id or "").strip()
    if not cid or detector is None:
        return
    with _lock:
        _live_detectors[cid] = detector


def snapshot_opencv_live_detectors() -> dict[str, Any]:
    with _lock:
        return dict(_live_detectors)


def refresh_all_opencv_live_detectors() -> None:
    """One overlay tick per registered camera (safe to call from heartbeat thread)."""
    for detector in snapshot_opencv_live_detectors().values():
        tick = getattr(detector, "refresh_live_overlay", None)
        if callable(tick):
            try:
                tick()
            except Exception:
                pass


def _merge_camera_payload(camera_id: str, payload: dict[str, Any]) -> None:
    cid = str(camera_id or "").strip()
    if not cid:
        return
    with _lock:
        cur = dict(_by_camera.get(cid, {}))
        cur.update(payload)
        cur["updated_at"] = time.time()
        _by_camera[cid] = cur


def set_opencv_live_overlay(camera_id: str, payload: dict[str, Any]) -> None:
    _merge_camera_payload(camera_id, payload)


def set_yolo_live_overlay(camera_id: str, payload: dict[str, Any]) -> None:
    _merge_camera_payload(camera_id, payload)


def _bbox_norm_to_polygon(bbox) -> list[list[float]] | None:
    if not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
        return None
    try:
        x1, y1, x2, y2 = [float(v) for v in bbox]
    except (TypeError, ValueError):
        return None
    if not (x2 > x1 and y2 > y1):
        return None
    return [[x1, y1], [x2, y1], [x2, y2], [x1, y2]]


def detection_results_to_detector_polygons(
    results: list | None,
    *,
    limit: int = 20,
) -> list[list[list[float]]]:
    """Live UI boxes from the current frame only (no stale track history)."""
    polys: list[list[list[float]]] = []
    if not results:
        return polys
    for res in results:
        poly = _bbox_norm_to_polygon(getattr(res, "bbox", None))
        if poly:
            polys.append(poly)
        if len(polys) >= limit:
            break
    return polys


def tracks_to_detector_polygons(tracks: dict | None, *, limit: int = 20) -> list[list[list[float]]]:
    """Normalized xyxy boxes as 4-point polygons for Live UI."""
    polys: list[list[list[float]]] = []
    if not isinstance(tracks, dict):
        return polys
    for tr in tracks.values():
        if not isinstance(tr, dict):
            continue
        bbox = None
        frames = tr.get("frames")
        if isinstance(frames, list) and frames:
            last = frames[-1]
            if isinstance(last, dict):
                bbox = last.get("bbox")
        poly = _bbox_norm_to_polygon(bbox)
        if poly:
            polys.append(poly)
        if len(polys) >= limit:
            break
    return polys


def snapshot_opencv_live_by_camera() -> dict[str, dict[str, Any]]:
    with _lock:
        return {k: dict(v) for k, v in _by_camera.items()}
