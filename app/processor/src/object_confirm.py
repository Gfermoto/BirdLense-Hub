"""Object confirm gate — NVR-style score history (min_score + median/threshold).

Mirrors common NVR object filters: detections below min_score are zeroed in history;
track is confirmed when padded median or peak score crosses threshold.
"""

from __future__ import annotations

import statistics
from typing import Any

from persist_mode import binary_track_first_min_detector_conf


def _float_cfg(app_config, key: str, default: float) -> float:
    try:
        return float(app_config.get(key) or default)
    except (TypeError, ValueError):
        return default


def object_confirm_min_score(app_config, min_confidence_to_process: float) -> float:
    raw = app_config.get("processor.object_confirm_min_score")
    if raw is not None and str(raw).strip() != "":
        return _float_cfg(app_config, "processor.object_confirm_min_score", 0.12)
    return binary_track_first_min_detector_conf(app_config, float(min_confidence_to_process))


def object_confirm_threshold(app_config, min_confidence_to_process: float) -> float:
    raw = app_config.get("processor.object_confirm_threshold")
    if raw is not None and str(raw).strip() != "":
        return _float_cfg(app_config, "processor.object_confirm_threshold", 0.12)
    return object_confirm_min_score(app_config, min_confidence_to_process)


def detector_bird_score_history(
    track: dict[str, Any],
    *,
    min_score: float,
) -> list[float]:
    """Per-frame bird scores; below min_score → 0.0 (ignored in median)."""
    out: list[float] = []
    for ev in track.get("detector_events") or []:
        if not isinstance(ev, dict):
            continue
        if str(ev.get("label") or "").strip().lower() != "bird":
            continue
        try:
            conf = float(ev.get("confidence") or 0.0)
        except (TypeError, ValueError):
            conf = 0.0
        out.append(conf if conf >= float(min_score) else 0.0)
    return out


def padded_median_score(scores: list[float], *, pad_to: int = 3) -> float:
    if not scores:
        return 0.0
    padded = list(scores)
    while len(padded) < max(1, int(pad_to)):
        padded.append(0.0)
    return float(statistics.median(padded))


def track_object_confirmed(
    *,
    app_config,
    track: dict[str, Any],
    min_confidence_to_process: float,
) -> tuple[bool, float, str]:
    """
    Returns (confirmed, score_used, reason_suffix).
    Confirmed if peak ≥ threshold OR padded median ≥ threshold.
    """
    min_score = object_confirm_min_score(app_config, float(min_confidence_to_process))
    threshold = object_confirm_threshold(app_config, float(min_confidence_to_process))
    history = detector_bird_score_history(track, min_score=min_score)
    if not history:
        return False, 0.0, "no_bird_scores"
    peak = max(history)
    median = padded_median_score(history)
    if peak >= threshold:
        return True, peak, "peak_threshold"
    if median >= threshold:
        return True, median, "median_threshold"
    return False, median, "below_threshold"
