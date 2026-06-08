"""Detect vs record timeline helpers (dual-stream Frigate-style parity)."""

from __future__ import annotations

from typing import Any, Mapping


def _cfg_get(cfg: Mapping[str, Any] | Any, dotted_key: str, default: Any = None) -> Any:
    """Dot-path lookup for flat runtime dicts and nested YAML trees / AppConfig."""
    if cfg is None:
        return default
    getter = getattr(cfg, "get", None)
    if callable(getter):
        try:
            val = getter(dotted_key, default)
            if val is not default or "." not in dotted_key:
                return val
        except TypeError:
            pass
    if isinstance(cfg, Mapping) and dotted_key in cfg:
        return cfg[dotted_key]
    cur: Any = cfg
    for part in dotted_key.split("."):
        if not isinstance(cur, Mapping):
            return default
        if part not in cur:
            return default
        cur = cur[part]
    return cur


def _camera_tuning_role(runtime_cfg: Mapping[str, Any] | Any, camera_id: str) -> str | None:
    cameras = _cfg_get(runtime_cfg, "video.cameras")
    if not isinstance(cameras, list):
        return None
    for row in cameras:
        if isinstance(row, dict) and str(row.get("id") or "").strip() == camera_id:
            role = str(row.get("tuning_role") or "").strip()
            return role or None
    return None


def resolve_detect_record_time_offset_sec(
    runtime_cfg: Mapping[str, Any] | None,
    *,
    camera_id: str | None = None,
) -> float:
    """Seconds added when mapping detect timeline → main MP4 (overlay / TG hires crop)."""
    if runtime_cfg is None:
        return 0.0
    offset = 0.0
    raw_global = _cfg_get(runtime_cfg, "processor.detect_record_time_offset_sec")
    if raw_global is not None:
        try:
            offset = float(raw_global)
        except (TypeError, ValueError):
            offset = 0.0
    cam = str(camera_id or _cfg_get(runtime_cfg, "processor._notify_camera_id") or "").strip()
    if not cam:
        return offset
    role = _camera_tuning_role(runtime_cfg, cam)
    roles = _cfg_get(runtime_cfg, "processor.camera_tuning_by_role")
    if isinstance(roles, dict):
        profile = roles.get(role) if role else None
        if not isinstance(profile, dict):
            profile = roles.get(cam)
        if isinstance(profile, dict) and profile.get("detect_record_time_offset_sec") is not None:
            try:
                offset = float(profile["detect_record_time_offset_sec"])
            except (TypeError, ValueError):
                pass
    cam_over = _cfg_get(runtime_cfg, f"processor.camera_overrides.{cam}")
    if isinstance(cam_over, dict) and cam_over.get("detect_record_time_offset_sec") is not None:
        try:
            offset = float(cam_over["detect_record_time_offset_sec"])
        except (TypeError, ValueError):
            pass
    return offset


def apply_record_time_offset(timestamp_sec: float, offset_sec: float) -> float:
    return max(0.0, float(timestamp_sec) + float(offset_sec))


def shift_detection_timeline_for_playback(
    detection: Mapping[str, Any],
    offset_sec: float,
) -> dict[str, Any]:
    """Shift track keyframe times from detect session clock to main MP4 timeline."""
    if abs(float(offset_sec)) < 1e-9:
        return dict(detection)
    out = dict(detection)
    for key in ("start_time", "end_time"):
        if out.get(key) is not None:
            try:
                out[key] = apply_record_time_offset(float(out[key]), offset_sec)
            except (TypeError, ValueError):
                pass
    frames = out.get("frames")
    if isinstance(frames, list):
        shifted: list[dict[str, Any]] = []
        for frame in frames:
            if not isinstance(frame, dict):
                continue
            row = dict(frame)
            if row.get("t") is not None:
                try:
                    row["t"] = apply_record_time_offset(float(row["t"]), offset_sec)
                except (TypeError, ValueError):
                    pass
            shifted.append(row)
        out["frames"] = shifted
    key_frames = out.get("key_frames")
    if isinstance(key_frames, list):
        shifted_kf: list[dict[str, Any]] = []
        for frame in key_frames:
            if not isinstance(frame, dict):
                continue
            row = dict(frame)
            if row.get("t") is not None:
                try:
                    row["t"] = apply_record_time_offset(float(row["t"]), offset_sec)
                except (TypeError, ValueError):
                    pass
            shifted_kf.append(row)
        out["key_frames"] = shifted_kf
    out["playback_timeline_synced"] = True
    out["playback_timeline_offset_sec"] = round(float(offset_sec), 4)
    return out


def apply_playback_timeline_offset_to_detections(
    video_detections: list[dict[str, Any]],
    *,
    runtime_cfg: Mapping[str, Any] | Any,
    camera_id: str | None,
) -> list[dict[str, Any]]:
    offset = resolve_detect_record_time_offset_sec(runtime_cfg, camera_id=camera_id)
    if abs(offset) < 1e-9:
        return video_detections
    out: list[dict[str, Any]] = []
    for row in video_detections or []:
        if str((row or {}).get("source") or "").strip().lower() != "video":
            out.append(row)
            continue
        if row.get("playback_timeline_synced"):
            out.append(row)
            continue
        out.append(shift_detection_timeline_for_playback(row, offset))
    return out
