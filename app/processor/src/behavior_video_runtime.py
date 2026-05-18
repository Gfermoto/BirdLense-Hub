"""Video-tracklet behavior runtime (shadow-safe MVP for #459)."""

from __future__ import annotations

import math
from typing import Any


def _safe_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _tracklet_stats(video_detections: list[dict[str, Any]]) -> dict[str, float]:
    frame_rows = 0.0
    tracks = 0.0
    mean_span = 0.0
    moving_tracks = 0.0
    for row in video_detections:
        frames = row.get('frames') or []
        if not isinstance(frames, list) or not frames:
            continue
        tracks += 1.0
        frame_rows += float(len(frames))
        x0 = y0 = x1 = y1 = None
        x2 = y2 = x3 = y3 = None
        if isinstance(frames[0], dict):
            b = frames[0].get('bbox')
            if isinstance(b, list) and len(b) == 4:
                x0, y0, x1, y1 = [_safe_float(v) for v in b]
        if isinstance(frames[-1], dict):
            b = frames[-1].get('bbox')
            if isinstance(b, list) and len(b) == 4:
                x2, y2, x3, y3 = [_safe_float(v) for v in b]
        if None not in (x0, y0, x1, y1, x2, y2, x3, y3):
            c0x = (x0 + x1) * 0.5
            c0y = (y0 + y1) * 0.5
            c1x = (x2 + x3) * 0.5
            c1y = (y2 + y3) * 0.5
            drift = math.hypot(c1x - c0x, c1y - c0y)
            mean_span += drift
            if drift >= 0.08:
                moving_tracks += 1.0
    if tracks > 0:
        mean_span /= tracks
    return {
        'frame_rows': frame_rows,
        'tracks': tracks,
        'mean_span': mean_span,
        'moving_ratio': (moving_tracks / tracks) if tracks > 0 else 0.0,
    }


def maybe_predict_video_behavior_video(
    app_config: Any,
    video_detections: list[dict[str, Any]],
    *,
    duration_s: float,
) -> tuple[str | None, float, str, str]:
    """Return (label, confidence, model_kind, model_version) for shadow/runtime."""
    br = app_config.get('processor.behavior_recognition') or {}
    if not isinstance(br, dict) or not bool(br.get('enabled')):
        return None, 0.0, 'video_v1_shadow', str(br.get('video_model_version') or 'x3d-s-shadow-v0')

    model_kind = str(br.get('video_model_kind') or 'video_v1_shadow').strip() or 'video_v1_shadow'
    model_version = str(br.get('video_model_version') or 'x3d-s-shadow-v0').strip() or 'x3d-s-shadow-v0'
    if not video_detections:
        return None, 0.0, model_kind, model_version

    st = _tracklet_stats(video_detections)
    duration = max(1.0, _safe_float(duration_s, 0.0))
    fps_eff = st['frame_rows'] / duration
    motion = st['moving_ratio']
    span = st['mean_span']
    tracks = st['tracks']

    # Lightweight rule-backed proxy for video-model shadow mode.
    if motion >= 0.55 or span >= 0.18:
        return 'flying', min(0.95, 0.52 + motion * 0.42), model_kind, model_version
    if fps_eff >= 5.0 and tracks >= 2.0:
        return 'feeding', min(0.93, 0.45 + min(1.0, fps_eff / 12.0) * 0.42), model_kind, model_version
    if span <= 0.03 and fps_eff <= 2.0:
        return 'perched_idle', min(0.9, 0.5 + (1.0 - span) * 0.25), model_kind, model_version
    return 'alert', min(0.86, 0.4 + (0.2 + motion) * 0.35), model_kind, model_version
