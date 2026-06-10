"""Split ByteTrack rows when bbox center jumps between spatial zones (incident a656199a)."""

from __future__ import annotations

import logging
from typing import Any, Mapping

logger = logging.getLogger(__name__)


def _parse_bool(cfg: Mapping[str, Any], key: str, default: bool) -> bool:
    raw = cfg.get(key)
    if raw is None:
        return default
    if isinstance(raw, bool):
        return raw
    return str(raw).strip().lower() in ("1", "true", "yes", "on")


def _parse_float(cfg: Mapping[str, Any], key: str, default: float) -> float:
    raw = cfg.get(key)
    if raw is None:
        return default
    try:
        return float(raw)
    except (TypeError, ValueError):
        return default


def _parse_int(cfg: Mapping[str, Any], key: str, default: int) -> int:
    raw = cfg.get(key)
    if raw is None:
        return default
    try:
        return int(raw)
    except (TypeError, ValueError):
        return default


def _bbox_center_norm(bbox: Any) -> tuple[float, float] | None:
    if not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
        return None
    try:
        x1, y1, x2, y2 = [float(v) for v in bbox]
    except (TypeError, ValueError):
        return None
    if x2 <= x1 or y2 <= y1:
        return None
    return ((x1 + x2) * 0.5, (y1 + y2) * 0.5)


def _center_jump_norm(prev_bbox: Any, curr_bbox: Any) -> float:
    prev = _bbox_center_norm(prev_bbox)
    curr = _bbox_center_norm(curr_bbox)
    if prev is None or curr is None:
        return 0.0
    dx = curr[0] - prev[0]
    dy = curr[1] - prev[1]
    return float((dx * dx + dy * dy) ** 0.5)


def _frame_time(frame: dict[str, Any]) -> float:
    try:
        return float(frame.get("t") if frame.get("t") is not None else frame.get("timestamp") or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _events_in_window(events: list[Any], start_t: float, end_t: float) -> list[Any]:
    out: list[Any] = []
    for ev in events or []:
        if not isinstance(ev, dict):
            continue
        try:
            t_val = float(ev.get("t") if ev.get("t") is not None else 0.0)
        except (TypeError, ValueError):
            continue
        if start_t - 1e-6 <= t_val <= end_t + 1e-6:
            out.append(ev)
    return out


def _key_frames_in_window(key_frames: list[Any], start_t: float, end_t: float) -> list[Any]:
    out: list[Any] = []
    for kf in key_frames or []:
        if not isinstance(kf, dict):
            continue
        try:
            t_val = float(kf.get("t") if kf.get("t") is not None else 0.0)
        except (TypeError, ValueError):
            continue
        if start_t - 1e-6 <= t_val <= end_t + 1e-6:
            out.append(kf)
    return out


def _pick_best_frame(segment: dict[str, Any]) -> None:
    key_frames = segment.get("key_frames") or []
    best_score = float(segment.get("best_frame_score") or 0.0)
    best_crop = segment.get("best_frame")
    for kf in key_frames:
        if not isinstance(kf, dict):
            continue
        score = float(kf.get("score") or 0.0)
        crop = kf.get("crop")
        if crop is not None and score >= best_score:
            best_score = score
            best_crop = crop
    segment["best_frame"] = best_crop
    segment["best_frame_score"] = best_score


def split_track_by_spatial_jumps(
    track_id: Any,
    track: dict[str, Any],
    *,
    max_center_jump_norm: float,
    min_segment_frames: int,
) -> dict[Any, dict[str, Any]]:
    """Return one or more track dicts; split when consecutive frame centers jump too far."""
    frames = [fr for fr in (track.get("frames") or []) if isinstance(fr, dict)]
    if len(frames) < 2:
        return {track_id: track}

    ordered = sorted(frames, key=_frame_time)
    segments: list[list[dict[str, Any]]] = [[ordered[0]]]
    for fr in ordered[1:]:
        prev_bbox = segments[-1][-1].get("bbox")
        jump = _center_jump_norm(prev_bbox, fr.get("bbox"))
        if jump > max_center_jump_norm:
            segments.append([fr])
        else:
            segments[-1].append(fr)

    if len(segments) <= 1:
        return {track_id: track}

    out: dict[Any, dict[str, Any]] = {}
    for idx, seg_frames in enumerate(segments):
        if len(seg_frames) < max(1, int(min_segment_frames)):
            continue
        start_t = _frame_time(seg_frames[0])
        end_t = _frame_time(seg_frames[-1])
        seg_id: Any = track_id if idx == 0 else f"{track_id}:s{idx}"
        seg = dict(track)
        seg["frames"] = seg_frames
        seg["start_time"] = start_t
        seg["end_time"] = end_t
        seg["detector_events"] = _events_in_window(track.get("detector_events") or [], start_t, end_t)
        seg["classifier_events"] = _events_in_window(track.get("classifier_events") or [], start_t, end_t)
        seg["key_frames"] = _key_frames_in_window(track.get("key_frames") or [], start_t, end_t)
        seg["spatial_split_from_track_id"] = track_id
        seg["spatial_split_segment_index"] = idx
        _pick_best_frame(seg)
        out[seg_id] = seg

    if not out:
        return {track_id: track}
    if len(out) > 1:
        logger.info(
            "track_spatial_split: track_id=%s -> %s segment(s) (max_jump=%.3f)",
            track_id,
            len(out),
            max_center_jump_norm,
        )
    return out


def split_tracks_by_spatial_jumps(
    tracks: Mapping[Any, dict[str, Any]] | None,
    app_config: Any,
) -> dict[Any, dict[str, Any]]:
    """Apply spatial jump split to all session tracks before crop/classify decisions."""
    if not tracks:
        return {}
    cfg = getattr(app_config, "config", None) or app_config
    if not _parse_bool(cfg, "processor.track_spatial_split_enabled", True):
        return dict(tracks)
    max_jump = _parse_float(cfg, "processor.track_spatial_split_max_center_jump_norm", 0.18)
    max_jump = max(0.05, min(0.45, max_jump))
    min_frames = _parse_int(cfg, "processor.track_spatial_split_min_segment_frames", 2)
    min_frames = max(1, min(min_frames, 8))

    out: dict[Any, dict[str, Any]] = {}
    for track_id, track in tracks.items():
        if not isinstance(track, dict):
            continue
        split = split_track_by_spatial_jumps(
            track_id,
            track,
            max_center_jump_norm=max_jump,
            min_segment_frames=min_frames,
        )
        out.update(split)
    return out


__all__ = [
    "split_track_by_spatial_jumps",
    "split_tracks_by_spatial_jumps",
]
