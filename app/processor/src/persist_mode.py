"""Persist pipeline mode — architectural contract for live recordings.

binary_track_first (default): YOLO track + bbox is the persist gate; species/classifier
is enrichment. Avoids «tracks in session, zero in DB» when classifier is weak.

legacy: pre-2026-06 multi-gate behavior (classifier/store_floor can veto valid tracks).
"""

from __future__ import annotations

import logging

from typing import Any

from track_first_contract import is_valid_norm_bbox, valid_track_frames
from processor_config_defaults import MIN_CONFIDENCE_TO_PROCESS


_legacy_persist_warned = False


def persist_mode_name(app_config) -> str:
    raw = str(app_config.get("detection.persist_mode") or "binary_track_first").strip().lower()
    if raw == "legacy":
        global _legacy_persist_warned
        if not _legacy_persist_warned:
            logging.getLogger(__name__).warning(
                "detection.persist_mode=legacy is unsupported (#621); migrate user_config to binary_track_first",
            )
            _legacy_persist_warned = True
        return "legacy"
    return raw


def binary_track_first_enabled(app_config) -> bool:
    mode = persist_mode_name(app_config)
    return mode in {"binary_track_first", "track_first"}


def _is_valid_norm_bbox(bbox: Any) -> bool:
    return is_valid_norm_bbox(bbox)


def track_has_bbox_frames(track: dict[str, Any]) -> bool:
    return bool(valid_track_frames(track.get("frames")))


def binary_track_first_min_detector_conf(app_config, min_confidence_to_process: float) -> float:
    """YOLO bird floor for btf — align with binary detect, not combined species threshold."""
    try:
        bird = float(
            app_config.get("processor.min_confidence_binary_bird")
            or app_config.get("processor.min_confidence_binary")
            or 0.12
        )
    except (TypeError, ValueError):
        bird = 0.12
    try:
        proc = float(min_confidence_to_process)
    except (TypeError, ValueError):
        proc = bird
    return min(bird, proc)


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
    floor = binary_track_first_min_detector_conf(app_config, float(min_confidence_to_process))
    if float(detector_conf) < floor:
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
    reason = str(row.get("decision_reason") or "").strip()
    if reason in {
        "accepted_binary_track_classifier_uncertain",
        "accepted_classifier_best_guess",
        "track_first_persist",
        "detect_first_anchor_persist",
        "detect_first_pre_fusion_restore",
        "detect_first_track_safeguard",
        "yolo_core_anchor_forced",
    }:
        return True
    if not track_has_bbox_frames(row):
        return False
    try:
        min_proc = float(app_config.get("processor.min_confidence_to_process") or MIN_CONFIDENCE_TO_PROCESS)
    except (TypeError, ValueError):
        min_proc = 0.12
    det_conf = float(row.get("detector_confidence") or conf)
    floor = binary_track_first_min_detector_conf(app_config, min_proc)
    label = str(row.get("detector_label") or row.get("species_name") or "").strip().lower()
    if label not in {"bird", "unknown"}:
        return reason == "accepted_species" and det_conf >= floor
    return det_conf >= floor


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
    has_bird = False
    for ev in detector_events or []:
        if not isinstance(ev, dict):
            continue
        if str(ev.get("label") or "").strip().lower() == "bird":
            has_bird = True
            break
    if not has_bird:
        return False
    return True
