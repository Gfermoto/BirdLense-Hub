"""Persist pipeline mode — architectural contract for live recordings.

binary_track_first (default): YOLO track + bbox is the persist gate; species/classifier
is enrichment. Avoids «tracks in session, zero in DB» when classifier is weak.

legacy: pre-2026-06 multi-gate behavior (classifier/store_floor can veto valid tracks).
"""

from __future__ import annotations

from typing import Any


def persist_mode_name(app_config) -> str:
    return str(app_config.get("detection.persist_mode") or "binary_track_first").strip().lower()


def binary_track_first_enabled(app_config) -> bool:
    mode = persist_mode_name(app_config)
    return mode in {"binary_track_first", "track_first"}


def track_has_bbox_frames(track: dict[str, Any]) -> bool:
    frames = track.get("frames")
    if not isinstance(frames, list) or not frames:
        return False
    for frame in frames:
        if not isinstance(frame, dict):
            continue
        bbox = frame.get("bbox")
        if isinstance(bbox, (list, tuple)) and len(bbox) >= 4:
            try:
                x1, y1, x2, y2 = [float(v) for v in bbox[:4]]
            except (TypeError, ValueError):
                continue
            if x2 > x1 and y2 > y1:
                return True
    return False


def can_binary_track_first_accept(
    *,
    app_config,
    detector_label: str,
    detector_conf: float,
    min_confidence_to_process: float,
    track: dict[str, Any],
) -> bool:
    if not binary_track_first_enabled(app_config):
        return False
    if str(detector_label or "").strip().lower() != "bird":
        return False
    if float(detector_conf) < float(min_confidence_to_process):
        return False
    return track_has_bbox_frames(track)


def passes_binary_track_first_store_floor(
    *,
    app_config,
    row: dict[str, Any],
    min_conf_store: float,
) -> bool:
    """YOLO bird+bbox may persist below ``min_confidence_to_store`` when mode is track-first."""
    conf = float(row.get("confidence") or 0.0)
    if conf >= float(min_conf_store):
        return True
    if not binary_track_first_enabled(app_config):
        return False
    if str(row.get("detection_provider") or "").strip().lower() != "yolo":
        return False
    if not track_has_bbox_frames(row):
        return False
    reason = str(row.get("decision_reason") or "").strip()
    if reason == "accepted_binary_track_classifier_uncertain":
        return True
    label = str(row.get("detector_label") or row.get("species_name") or "").strip().lower()
    if label not in {"bird", "unknown"}:
        return False
    try:
        min_proc = float(app_config.get("processor.min_confidence_to_process") or 0.12)
    except (TypeError, ValueError):
        min_proc = 0.12
    det_conf = float(row.get("detector_confidence") or conf)
    return det_conf >= min_proc


def defer_static_pinned_reject(
    *,
    app_config,
    track: dict[str, Any],
    detector_events: list[Any],
    min_confidence_to_process: float,
) -> bool:
    """Under binary_track_first, do not veto bird+bbox tracks on static geometry alone."""
    if not binary_track_first_enabled(app_config):
        return False
    if not track_has_bbox_frames(track):
        return False
    max_conf = 0.0
    has_bird = False
    for ev in detector_events or []:
        if not isinstance(ev, dict):
            continue
        label = str(ev.get("label") or "").strip().lower()
        if label == "bird":
            has_bird = True
        try:
            max_conf = max(max_conf, float(ev.get("confidence") or 0.0))
        except (TypeError, ValueError):
            continue
    if not has_bird:
        return False
    return max_conf >= float(min_confidence_to_process)
