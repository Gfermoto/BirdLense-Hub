"""Shared contract for obtaining dataset crops from detections."""

from __future__ import annotations

import json


def best_keyframe_bbox(key_frames) -> tuple[list[float] | None, float | None]:
    """Highest-score keyframe bbox + timestamp, or (None, None)."""
    if not isinstance(key_frames, list):
        return None, None
    dict_frames = [kf for kf in key_frames if isinstance(kf, dict)]
    if not dict_frames:
        return None, None
    best = max(dict_frames, key=lambda k: float(k.get("score") or 0.0))
    bb = best.get("bbox")
    bbox = None
    if isinstance(bb, (list, tuple)) and len(bb) == 4:
        try:
            bbox = [float(v) for v in bb]
        except (TypeError, ValueError):
            bbox = None
    try:
        t_val = float(best.get("t") if best.get("t") is not None else 0.0)
    except (TypeError, ValueError):
        t_val = None
    return bbox, t_val


def bbox_for_offset(frames_payload, offset_sec: float) -> list[float] | None:
    """Return bbox from frames list/JSON closest to offset_sec."""
    frames = frames_payload
    if isinstance(frames_payload, str):
        if not frames_payload.strip():
            return None
        try:
            frames = json.loads(frames_payload)
        except (TypeError, ValueError):
            return None
    if not isinstance(frames, list):
        return None
    best = None
    best_diff = float("inf")
    for frame in frames:
        if not isinstance(frame, dict):
            continue
        bbox = frame.get("bbox")
        if not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
            continue
        try:
            diff = abs(float(frame.get("t", 0.0)) - float(offset_sec))
        except (TypeError, ValueError):
            continue
        if diff < best_diff:
            best_diff = diff
            best = [float(v) for v in bbox]
    return best


def build_detection_crop_request(
    *,
    best_frame=None,
    frames=None,
    key_frames=None,
    start_time: float = 0.0,
    end_time: float = 0.0,
) -> dict:
    """Select best available crop source for one detection."""
    try:
        start = float(start_time or 0.0)
    except (TypeError, ValueError):
        start = 0.0
    try:
        end = float(end_time or start)
    except (TypeError, ValueError):
        end = start
    offset_sec = start + max(0.0, end - start) / 2.0
    kf_bbox, kf_t = best_keyframe_bbox(key_frames)
    if kf_t is not None:
        offset_sec = kf_t
    bbox = kf_bbox if kf_bbox is not None else bbox_for_offset(frames, offset_sec)
    if best_frame is not None:
        return {
            "source_kind": "best_frame",
            "best_frame": best_frame,
            "offset_sec": offset_sec,
            "bbox": bbox,
        }
    if bbox:
        return {
            "source_kind": "video_frames_bbox",
            "best_frame": None,
            "offset_sec": offset_sec,
            "bbox": bbox,
        }
    return {
        "source_kind": "none",
        "best_frame": None,
        "offset_sec": offset_sec,
        "bbox": None,
    }
