"""Detect vs record timeline helpers (dual-stream Frigate-style parity)."""

from __future__ import annotations

from typing import Any, Mapping


def resolve_detect_record_time_offset_sec(
    runtime_cfg: Mapping[str, Any] | None,
    *,
    camera_id: str | None = None,
) -> float:
    """Seconds added when seeking main MP4 for bbox overlay / TG hires crop."""
    if runtime_cfg is None:
        return 0.0
    offset = 0.0
    raw_global = runtime_cfg.get("processor.detect_record_time_offset_sec")
    if raw_global is not None:
        try:
            offset = float(raw_global)
        except (TypeError, ValueError):
            offset = 0.0
    cam = str(camera_id or runtime_cfg.get("processor._notify_camera_id") or "").strip()
    if not cam:
        return offset
    roles = runtime_cfg.get("processor.camera_tuning_by_role")
    if not isinstance(roles, dict):
        return offset
    role = None
    cameras = runtime_cfg.get("video.cameras")
    if isinstance(cameras, list):
        for row in cameras:
            if isinstance(row, dict) and str(row.get("id") or "").strip() == cam:
                role = str(row.get("tuning_role") or "").strip() or None
                break
    profile = roles.get(role) if role else None
    if not isinstance(profile, dict):
        profile = roles.get(cam)
    if not isinstance(profile, dict):
        return offset
    raw_cam = profile.get("detect_record_time_offset_sec")
    if raw_cam is None:
        return offset
    try:
        return float(raw_cam)
    except (TypeError, ValueError):
        return offset


def apply_record_time_offset(timestamp_sec: float, offset_sec: float) -> float:
    return max(0.0, float(timestamp_sec) + float(offset_sec))
