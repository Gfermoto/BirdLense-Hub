"""Scales evidence helpers for finalized recordings."""

from __future__ import annotations

from datetime import datetime
from typing import Any


def estimate_recording_scales_delta(
    config: Any,
    video_detections: list[dict],
    *,
    scales_topic_arg: str | None,
    data_dir: str,
    start_time: datetime,
    end_time: datetime,
) -> tuple[float | None, dict[str, Any]]:
    has_non_audio = any(detection.get("source") != "audio" for detection in video_detections)
    scales_on = config.get("integrations.scales.enabled")
    weight_est = config.get("integrations.scales.weight_estimate_enabled", True)
    if not (scales_on and weight_est and scales_topic_arg and has_non_audio):
        return None, {}

    from scale_sample_log import estimate_weight_delta_kg

    raw_min = config.get("integrations.scales.min_delta_kg_for_estimate")
    try:
        min_delta = float(raw_min or 0.008)
    except (TypeError, ValueError):
        min_delta = 0.008
    require_spike = config.get("integrations.scales.estimate_require_consecutive_spike", True)
    estimated_delta, sample_count = estimate_weight_delta_kg(
        data_dir,
        start_time,
        end_time,
        min_delta_kg=min_delta,
        require_consecutive_spike=bool(require_spike),
    )
    return estimated_delta, {
        "estimated_delta_kg": estimated_delta,
        "sample_count": int(sample_count or 0),
        "min_delta_kg": float(min_delta),
    }
