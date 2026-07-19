"""Camera tuning_role → processor.camera_tuning_by_role preset (cycle-free)."""

from __future__ import annotations

from typing import Any


def resolve_camera_tuning_role(app_config, camera_id: str | None) -> str | None:
    cam = str(camera_id or "").strip()
    if not cam:
        return None
    try:
        from app_config.cameras import get_valid_cameras
    except ImportError:
        return None
    cameras = get_valid_cameras(video_config=(app_config.get("video") or {}))
    for row in cameras:
        if not isinstance(row, dict):
            continue
        row_id = str(row.get("id") or "").strip()
        legacy_id = str(row.get("legacy_id") or "").strip()
        if cam not in {row_id, legacy_id}:
            continue
        role = str(row.get("tuning_role") or "").strip()
        return role or None
    return None


def role_preset(app_config, camera_id: str | None) -> dict[str, Any]:
    role = resolve_camera_tuning_role(app_config, camera_id)
    if not role:
        return {}
    raw = app_config.get(f"processor.camera_tuning_by_role.{role}")
    return dict(raw) if isinstance(raw, dict) else {}
