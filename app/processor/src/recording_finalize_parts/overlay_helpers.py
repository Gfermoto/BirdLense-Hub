from __future__ import annotations

from collections import Counter
from typing import Any

from app_config.app_config import app_config
from track_geometry import StaticPinnedTrackConfig, static_pinned_track_reason
from track_first_contract import is_valid_norm_bbox, valid_track_frames
from persist_mode import binary_track_first_enabled


def _rejected_reason_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts = Counter(
        str(item.get("reject_reason_code") or item.get("decision_reason") or "rejected_unknown")
        for item in (rows or [])
    )
    return dict(sorted(counts.items()))


def _sanitize_persisted_overlay_frames(
    video_detections: list[dict[str, Any]],
    *,
    runtime_cfg: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Mark overlay suppression; optionally strip frames only when track-first gate is off."""
    cfg = StaticPinnedTrackConfig.from_runtime_cfg(runtime_cfg or app_config.config or {})
    strip_review = bool(app_config.get("detection.strip_review_only_overlay_frames", False))
    track_first = bool(app_config.get("detection.track_first_gate_enabled", True))
    out: list[dict[str, Any]] = []
    for row in video_detections or []:
        d = dict(row)
        kind = str(d.get("decision_kind") or "").strip().lower()
        if strip_review and not track_first and kind in {"review_only_generic", "review_only"}:
            if d.get("frames"):
                d["frames"] = []
            d["overlay_suppressed"] = "review_only_no_overlay"
            out.append(d)
            continue
        if kind in {"review_only_generic", "review_only"} and d.get("frames"):
            d["overlay_suppressed"] = "review_only_no_overlay"
        frames = d.get("frames") or []
        runtime = runtime_cfg or app_config.config or {}
        skip_static_strip = False
        try:
            from linear_pipeline import is_linear_pipeline

            skip_static_strip = is_linear_pipeline(runtime) or binary_track_first_enabled(runtime)
        except ImportError:
            skip_static_strip = binary_track_first_enabled(runtime)
        if frames and cfg.enabled and not skip_static_strip:
            pseudo = {
                "start_time": d.get("start_time", 0),
                "end_time": d.get("end_time", 0),
                "frames": frames,
            }
            static_reason = static_pinned_track_reason(pseudo, cfg)
            if static_reason:
                d["frames"] = []
                d["overlay_suppressed"] = static_reason
        out.append(d)
    return out


def _is_valid_track_bbox(bbox: Any) -> bool:
    return is_valid_norm_bbox(bbox)


def _valid_track_frames(frames: Any) -> list[dict[str, Any]]:
    return valid_track_frames(frames)


def _row_exempt_from_video_bbox_requirement(row: dict[str, Any]) -> bool:
    """Only framed Frigate MQTT evidence may skip YOLO bbox contract.

    Frameless Frigate standalone used to pass through as 0..duration visits —
    full timeline stripe with no boxes. Those rows must be dropped here.
    """
    frames = row.get("frames")
    has_frames = isinstance(frames, list) and bool(frames)
    if not has_frames:
        return False
    provider = str(row.get("detection_provider") or "").strip().lower()
    if provider == "frigate":
        return True
    if row.get("frigate_standalone") or row.get("frigate_trigger_salvage"):
        return True
    return False


def _safe_float(value: Any, *, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)
