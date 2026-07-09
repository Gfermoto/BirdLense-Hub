from __future__ import annotations

from typing import Any


def _default_scales_evidence_snapshot(
    *,
    app_config_obj: Any,
    scales_topic_arg: str | None,
) -> dict[str, Any]:
    raw_min_delta = app_config_obj.get("integrations.scales.min_delta_kg_for_estimate")
    min_delta_kg: float | None
    if raw_min_delta is None:
        min_delta_kg = None
    else:
        try:
            min_delta_kg = float(raw_min_delta)
        except (TypeError, ValueError):
            min_delta_kg = None
    return {
        "enabled": bool(app_config_obj.get("integrations.scales.enabled")),
        "weight_estimate_enabled": bool(
            app_config_obj.get(
                "integrations.scales.weight_estimate_enabled",
                True,
            ),
        ),
        "topic_present": bool(scales_topic_arg),
        "estimated_delta_kg": None,
        "sample_count": 0,
        "min_delta_kg": min_delta_kg,
        "require_consecutive_spike": bool(
            app_config_obj.get(
                "integrations.scales.estimate_require_consecutive_spike",
                True,
            ),
        ),
    }


def _tracks_for_finalize(
    frame_processor: Any,
    recording_context: dict[str, Any] | None,
) -> dict[Any, dict[str, Any]]:
    if isinstance(recording_context, dict):
        snap = recording_context.get("tracks_snapshot")
        if isinstance(snap, dict):
            raw = snap
        else:
            raw = getattr(frame_processor, "tracks", None) or {}
    else:
        raw = getattr(frame_processor, "tracks", None) or {}
    try:
        from app_config.app_config import app_config
        from track_spatial_split import split_tracks_by_spatial_jumps

        return split_tracks_by_spatial_jumps(raw, app_config)
    except ImportError:
        return dict(raw)
