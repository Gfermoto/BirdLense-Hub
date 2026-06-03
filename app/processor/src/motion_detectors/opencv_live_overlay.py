"""In-memory Live overlay snapshots (OpenCV motion + YOLO boxes) per camera."""

from __future__ import annotations

import threading
import time
from typing import Any

_lock = threading.Lock()
_by_camera: dict[str, dict[str, Any]] = {}
_live_detectors: dict[str, Any] = {}
_DETECTOR_POLYGONS_STALE_TTL_SEC = 1.0


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


def _merge_camera_payload(camera_id: str, payload: dict[str, Any], *, source: str) -> None:
    cid = str(camera_id or "").strip()
    if not cid:
        return
    with _lock:
        cur = dict(_by_camera.get(cid, {}))
        prev_updated = cur.get("updated_at")
        try:
            prev_updated_f = float(prev_updated) if prev_updated is not None else None
        except (TypeError, ValueError):
            prev_updated_f = None
        now_ts = time.time()
        prev_age = (now_ts - prev_updated_f) if prev_updated_f is not None else None

        if (
            source == "opencv"
            and "detector_polygons" not in payload
            and isinstance(cur.get("detector_polygons"), list)
            and (prev_age is None or prev_age > _DETECTOR_POLYGONS_STALE_TTL_SEC)
        ):
            # OpenCV heartbeat should not preserve stale YOLO boxes forever.
            cur["detector_polygons"] = []
        cur.update(payload)
        cur["updated_at"] = now_ts
        _by_camera[cid] = cur


def set_opencv_live_overlay(camera_id: str, payload: dict[str, Any]) -> None:
    _merge_camera_payload(camera_id, payload, source="opencv")


def set_yolo_live_overlay(camera_id: str, payload: dict[str, Any]) -> None:
    _merge_camera_payload(camera_id, payload, source="yolo")


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
    static_cfg = None
    try:
        from app_config.app_config import app_config
        from track_geometry import StaticPinnedTrackConfig, static_pinned_track_reason

        static_cfg = StaticPinnedTrackConfig.from_runtime_cfg(app_config.config or {})
    except Exception:
        static_cfg = None
    for tr in tracks.values():
        if not isinstance(tr, dict):
            continue
        bbox = None
        frames = tr.get("frames")
        if isinstance(frames, list) and frames:
            if static_cfg is not None and static_cfg.enabled:
                pseudo = {
                    "start_time": tr.get("start_time", 0),
                    "end_time": tr.get("end_time", 0),
                    "frames": frames,
                }
                if static_pinned_track_reason(pseudo, static_cfg):
                    continue
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
