"""Detect-first gate: lores YOLO+ByteTrack before main-stream FFmpeg."""

from __future__ import annotations

import logging
from typing import Any

from runtime_contract import apply_runtime_contract
from app_config.visit_eligibility import visit_eligible_for_named_species
from track_first_contract import (
    has_accepted_ingestible_track_rows,
    is_valid_norm_bbox,
    valid_track_frames,
)

logger = logging.getLogger(__name__)


def is_valid_detect_first_anchor(anchor: dict | None) -> bool:
    """Confirmed lores anchor: track id + normalized bbox."""
    if not isinstance(anchor, dict):
        return False
    if anchor.get("track_id") is None:
        return False
    return is_valid_norm_bbox(anchor.get("bbox"))


def enrich_detect_first_anchor(
    anchor: dict[str, Any],
    *,
    detect_first_frames: int,
    detect_first_hits: int,
    trigger_source: str | None,
    camera_id: str | None,
) -> dict[str, Any]:
    anchor["detect_first_frames"] = detect_first_frames
    anchor["detect_first_hits"] = detect_first_hits
    anchor["trigger_source"] = trigger_source or None
    anchor["camera_id"] = camera_id
    return anchor


def detect_first_runtime_signal_fields(anchor: dict[str, Any] | None) -> dict[str, Any]:
    """Runtime summary fields for recording_session / finalize."""
    if not is_valid_detect_first_anchor(anchor) or not isinstance(anchor, dict):
        return {
            "detect_first_confirmed": False,
            "detect_first_anchor_track_id": None,
            "detect_first_anchor_confidence": 0.0,
            "detect_first_window_frames": 0,
            "detect_first_window_hits": 0,
        }
    return {
        "detect_first_confirmed": True,
        "detect_first_anchor_track_id": anchor.get("track_id"),
        "detect_first_anchor_confidence": float(anchor.get("confidence") or 0.0),
        "detect_first_window_frames": int(anchor.get("detect_first_frames") or 0),
        "detect_first_window_hits": int(anchor.get("detect_first_hits") or 0),
    }


def _anchor_frames_or_fallback(anchor: dict[str, Any]) -> list[dict[str, Any]]:
    frames = valid_track_frames(anchor.get("frames"))
    if frames:
        return frames
    if not is_valid_norm_bbox(anchor.get("bbox")):
        return []
    try:
        t0 = float(anchor.get("start_time") or 0.0)
    except (TypeError, ValueError):
        t0 = 0.0
    return [{"t": t0, "bbox": [float(v) for v in anchor["bbox"][:4]]}]


def sanitize_anchor_for_context(anchor: dict[str, Any] | None) -> dict[str, Any] | None:
    """JSON-safe anchor snapshot for recording_context (no ndarray crops)."""
    if not is_valid_detect_first_anchor(anchor) or not isinstance(anchor, dict):
        return None
    frames = []
    for frame in _anchor_frames_or_fallback(anchor):
        try:
            t_val = float(frame.get("t") if frame.get("t") is not None else frame.get("timestamp") or 0.0)
        except (TypeError, ValueError):
            t_val = 0.0
        bbox = frame.get("bbox")
        frames.append({"t": t_val, "bbox": [float(v) for v in bbox[:4]]})
    if not frames:
        return None
    return {
        "track_id": anchor.get("track_id"),
        "bbox": [float(v) for v in anchor["bbox"][:4]],
        "confidence": float(anchor.get("confidence") or 0.0),
        "detector_label": str(anchor.get("detector_label") or "Bird"),
        "detector_confidence": float(anchor.get("detector_confidence") or anchor.get("confidence") or 0.0),
        "start_time": float(anchor.get("start_time") or 0.0),
        "end_time": float(anchor.get("end_time") or 0.0),
        "frames": frames,
        "detect_first_frames": int(anchor.get("detect_first_frames") or 0),
        "detect_first_hits": int(anchor.get("detect_first_hits") or 0),
    }


def build_persist_row_from_anchor(
    anchor: dict[str, Any] | None,
    *,
    video_duration_s: float,
    reason: str = "detect_first_anchor_persist",
) -> dict[str, Any] | None:
    """Ingestible YOLO row from confirmed lores anchor."""
    if not isinstance(anchor, dict):
        return None
    frames = _anchor_frames_or_fallback(anchor)
    if not frames:
        return None
    try:
        start_time = float(anchor.get("start_time") if anchor.get("start_time") is not None else frames[0].get("t") or 0.0)
    except (TypeError, ValueError):
        start_time = 0.0
    try:
        end_time = float(anchor.get("end_time") if anchor.get("end_time") is not None else frames[-1].get("t") or video_duration_s)
    except (TypeError, ValueError):
        end_time = float(video_duration_s)
    end_time = max(start_time, min(end_time, float(video_duration_s)))
    conf = float(anchor.get("confidence") or anchor.get("detector_confidence") or 0.0)
    label = str(anchor.get("detector_label") or "Bird").strip() or "Bird"
    species_name = label if label.lower() != "bird" else "Bird"
    return apply_runtime_contract(
        {
            "track_id": anchor.get("track_id"),
            "accepted": True,
            "visit_eligible": visit_eligible_for_named_species(
                species_name=species_name,
                visit_eligible=True,
            ),
            "notification_eligible": False,
            "species_name": species_name,
            "start_time": start_time,
            "end_time": end_time,
            "confidence": conf,
            "source": "video",
            "detection_provider": "yolo",
            "frames": frames,
            "decision_reason": reason,
            "decision_kind": "accepted_species",
            "detector_label": label,
            "detector_confidence": float(anchor.get("detector_confidence") or conf),
            "detect_first_safeguard": True,
        }
    )


def _build_safeguard_row_from_track(
    track_id: Any,
    track: dict[str, Any],
    *,
    video_duration_s: float,
    reason: str,
) -> dict[str, Any] | None:
    frames = valid_track_frames(track.get("frames"))
    if not frames:
        return None
    has_bird = any(
        str((ev or {}).get("label") or "").strip().lower() == "bird"
        for ev in (track.get("detector_events") or [])
        if isinstance(ev, dict)
    )
    if not has_bird:
        return None
    try:
        start_time = float(track.get("start_time") or frames[0].get("t") or 0.0)
    except (TypeError, ValueError):
        start_time = 0.0
    try:
        end_time = float(track.get("end_time") or frames[-1].get("t") or video_duration_s)
    except (TypeError, ValueError):
        end_time = float(video_duration_s)
    end_time = max(start_time, min(end_time, float(video_duration_s)))
    det_conf = max(
        (float(ev.get("confidence") or 0.0) for ev in (track.get("detector_events") or []) if isinstance(ev, dict)),
        default=0.0,
    )
    return apply_runtime_contract(
        {
            "track_id": track_id,
            "accepted": True,
            "visit_eligible": visit_eligible_for_named_species(
                species_name="Bird",
                visit_eligible=True,
            ),
            "notification_eligible": False,
            "species_name": "Bird",
            "start_time": start_time,
            "end_time": end_time,
            "confidence": max(det_conf, 0.12),
            "source": "video",
            "detection_provider": "yolo",
            "frames": frames,
            "decision_reason": reason,
            "decision_kind": "accepted_species",
            "detector_label": "Bird",
            "detector_confidence": det_conf,
            "detect_first_safeguard": True,
        }
    )


def _track_id_matches(left: Any, right: Any) -> bool:
    if left is None or right is None:
        return False
    try:
        return int(left) == int(right)
    except (TypeError, ValueError):
        return str(left) == str(right)


def restore_detect_first_persist_rows(
    video_detections: list[dict[str, Any]] | None,
    *,
    recording_context: dict[str, Any] | None,
    accepted_pre_fusion: list[dict[str, Any]] | None,
    frame_processor_tracks: dict[Any, dict[str, Any]] | None,
    video_duration_s: float,
) -> tuple[list[dict[str, Any]], bool]:
    """When detect-first confirmed bird but fusion/gates left nothing ingestible — restore core row."""
    rows = list(video_detections or [])
    if has_accepted_ingestible_track_rows(rows):
        return rows, False

    ctx = dict(recording_context or {})
    rs = dict(ctx.get("runtime_signals") or {})
    if not bool(rs.get("detect_first_confirmed")):
        return rows, False

    anchor_tid = rs.get("detect_first_anchor_track_id")

    pre_fusion_yolo = [
        row
        for row in (accepted_pre_fusion or [])
        if str(row.get("detection_provider") or "").strip().lower() == "yolo"
        and valid_track_frames(row.get("frames"))
    ]
    if anchor_tid is not None:
        for row in pre_fusion_yolo:
            if _track_id_matches(row.get("track_id"), anchor_tid):
                restored = dict(row)
                restored["detect_first_safeguard"] = True
                restored["decision_reason"] = "detect_first_pre_fusion_restore"
                logger.warning(
                    "Detect-first safeguard: restored anchor-matched pre-fusion row track_id=%s frames=%s",
                    restored.get("track_id"),
                    len(restored.get("frames") or []),
                )
                return [restored], True

    for row in sorted(pre_fusion_yolo, key=lambda item: -float(item.get("confidence") or 0.0)):
        restored = dict(row)
        restored["detect_first_safeguard"] = True
        if not str(restored.get("decision_reason") or "").strip():
            restored["decision_reason"] = "detect_first_pre_fusion_restore"
        logger.warning(
            "Detect-first safeguard: restored pre-fusion YOLO row track_id=%s frames=%s",
            restored.get("track_id"),
            len(restored.get("frames") or []),
        )
        return [restored], True

    tracks = frame_processor_tracks or {}
    ordered_ids: list[Any] = []
    if anchor_tid is not None:
        for tid in tracks:
            if _track_id_matches(tid, anchor_tid):
                ordered_ids.append(tid)
                break
    ordered_ids.extend(tid for tid in tracks if tid not in ordered_ids)

    best: dict[str, Any] | None = None
    best_score = -1.0
    for track_id in ordered_ids:
        track = tracks.get(track_id)
        if not isinstance(track, dict):
            continue
        candidate = _build_safeguard_row_from_track(
            track_id,
            track,
            video_duration_s=video_duration_s,
            reason="detect_first_track_safeguard",
        )
        if candidate is None:
            continue
        score = len(candidate.get("frames") or []) + float(candidate.get("confidence") or 0.0)
        if score > best_score:
            best_score = score
            best = candidate
    if best is not None:
        logger.warning(
            "Detect-first safeguard: restored live track row track_id=%s frames=%s",
            best.get("track_id"),
            len(best.get("frames") or []),
        )
        return [best], True

    anchor_only_enabled = False
    try:
        from app_config.app_config import app_config

        anchor_only_enabled = bool(app_config.get("processor.detect_first_anchor_only_persist_enabled", False))
    except Exception:
        anchor_only_enabled = False
    if anchor_only_enabled:
        anchor_row = build_persist_row_from_anchor(
            ctx.get("detect_first_anchor"),
            video_duration_s=video_duration_s,
        )
        if anchor_row is not None:
            anchor_row["classifier_needs_review"] = True
            anchor_row["review_reason"] = "detect_first_anchor_only"
            logger.warning(
                "Detect-first safeguard: restored anchor-only row track_id=%s frames=%s",
                anchor_row.get("track_id"),
                len(anchor_row.get("frames") or []),
            )
            return [anchor_row], True

    return rows, False


def build_frigate_assisted_detect_first_anchor(
    *,
    app_config,
    camera_id: str | None,
    motion_detector: Any,
    trigger_source: str | None,
) -> dict[str, Any] | None:
    """When lores YOLO misses but Frigate already confirmed bird+bbox, allow main record."""
    trigger = str(trigger_source or "").strip().lower()
    if trigger != "frigate":
        return None
    if not bool(app_config.get("processor.detect_first_frigate_assist_enabled", True)):
        return None
    try:
        min_conf = float(app_config.get("processor.detect_first_frigate_assist_min_confidence") or 0.50)
    except (TypeError, ValueError):
        min_conf = 0.50
    get_ev = getattr(motion_detector, "get_last_frigate_event", None)
    ev = get_ev() if callable(get_ev) else None
    if not isinstance(ev, dict):
        return None
    ev_cam = str(ev.get("camera") or "").strip()
    cam = str(camera_id or ev_cam or "").strip()
    if cam and ev_cam and cam != ev_cam:
        return None
    try:
        conf = float(ev.get("confidence") or 0.0)
    except (TypeError, ValueError):
        conf = 0.0
    if conf < min_conf or not ev.get("_frigate_has_geometry"):
        return None
    try:
        from frigate_live_track import get_frigate_live_bbox
    except ImportError:
        return None
    bbox = get_frigate_live_bbox(cam or ev_cam)
    if not is_valid_norm_bbox(bbox):
        return None
    logger.info(
        "detect_first: frigate-assisted anchor camera=%s conf=%.3f (lores YOLO missed)",
        cam or ev_cam or "?",
        conf,
    )
    return {
        "track_id": 0,
        "bbox": [float(v) for v in bbox[:4]],
        "confidence": conf,
        "start_time": 0.0,
        "end_time": 0.0,
        "frames": [{"t": 0.0, "bbox": [float(v) for v in bbox[:4]]}],
        "detect_first_frigate_assisted": True,
        "frigate_label": ev.get("label"),
    }
