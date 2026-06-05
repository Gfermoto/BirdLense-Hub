"""Финал сессии записи: merge, API, MQTT, уведомления (tech debt #201)."""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from api import API
from app_config.app_config import app_config
from decision_trace_builder import build_decision_trace_payload
from detection_fusion import build_fused_video_detections, skip_frigate_ev_for_standalone
from notify_preview_encode import encode_notify_preview_base64
from processor_runtime_stats import inc_counter
from processor_support import get_data_dir, restart_flag_path
from recording_cleanup_policy import should_keep_empty_recording
from recording_dataset_crops import maybe_save_dataset_crops
from recording_decision_trace_log import write_decision_trace_activity
from recording_file_gate import _is_playable_video_file
from recording_ingest_gate import log_missing_video_gate
from recording_mqtt_window import get_recording_mqtt_events
from recording_no_detection_log import (
    log_no_detection_activity,
    log_no_detections_after_merge,
)
from recording_notify_dispatch import notify_unique_species
from recording_post_fusion_rejections import collect_post_fusion_rejections
from linear_pipeline import (
    STAGE_CLASSIFY_ENRICH,
    STAGE_REID_BEHAVIOR,
    is_linear_pipeline,
    linear_skip_frigate_salvage_paths,
    linear_skip_legacy_fusion_safeguards,
)
from recording_scales_evidence import estimate_recording_scales_delta
from recording_session_cleanup import remove_session_dir
from recording_video_response import response_video_id
from recordings_remote_mirror import schedule_recordings_session_mirror
from reid_runtime import enrich_runtime_reid_detections
from processor_diagnostics import collect_root_cause_snapshot, write_root_cause_dump
from session_state_repository import SessionStateRepository
from behavior_baseline_runtime import maybe_predict_video_behavior_bundle
from track_geometry import StaticPinnedTrackConfig, static_pinned_track_reason
from track_first_contract import (
    apply_track_first_persist_gate,
    count_ingestible_track_rows,
    has_ingestible_track_rows,
)
from persist_mode import binary_track_first_enabled

# Пустые сессии без детекций — частое событие; не засоряем лог (раз в интервал — WARNING, иначе DEBUG).
_NO_DETECTIONS_WARN_INTERVAL_S = 120.0
_no_detections_warn_next_monotonic = 0.0


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

            skip_static_strip = is_linear_pipeline(runtime)
        except ImportError:
            pass
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
    if not isinstance(bbox, (list, tuple)) or len(bbox) < 4:
        return False
    try:
        x1, y1, x2, y2 = [float(v) for v in bbox[:4]]
    except (TypeError, ValueError):
        return False
    if not (x2 > x1 and y2 > y1):
        return False
    # Stored frames are normalized; keep a small margin for rounding noise.
    low, high = -0.05, 1.05
    return all(low <= v <= high for v in (x1, y1, x2, y2))


def _safe_float(value: Any, *, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _valid_track_frames(frames: Any) -> list[dict[str, Any]]:
    if not isinstance(frames, list):
        return []
    out: list[dict[str, Any]] = []
    for frame in frames:
        if not isinstance(frame, dict):
            continue
        if _is_valid_track_bbox(frame.get("bbox")):
            out.append(frame)
    return out


def _runtime_wall_latency_seconds(
    runtime_signals: dict[str, Any] | None,
    key: str,
) -> float | None:
    if not isinstance(runtime_signals, dict):
        return None
    value = _safe_float(runtime_signals.get(key), default=-1.0)
    return value if value >= 0.0 else None


def _resolve_session_latencies(
    runtime_signals: dict[str, Any] | None,
    video_detections: list[dict[str, Any]],
) -> tuple[float | None, float | None, float | None, float | None]:
    """Wall-clock trigger latencies plus video-timeline offsets from persisted rows."""
    video_bbox_s, video_track_s = _first_bbox_and_track_latency_seconds(video_detections)
    wall_bbox_s = _runtime_wall_latency_seconds(
        runtime_signals,
        "trigger_to_first_bbox_wall_s",
    )
    wall_track_s = _runtime_wall_latency_seconds(
        runtime_signals,
        "trigger_to_first_track_wall_s",
    )
    trigger_bbox_s = wall_bbox_s if wall_bbox_s is not None else video_bbox_s
    trigger_track_s = wall_track_s if wall_track_s is not None else video_track_s
    return trigger_bbox_s, video_bbox_s, trigger_track_s, video_track_s


def _first_bbox_and_track_latency_seconds(
    video_detections: list[dict[str, Any]],
) -> tuple[float | None, float | None]:
    """Return (first_bbox_latency_s, first_track_latency_s) from persisted rows."""
    bbox_candidates: list[float] = []
    track_candidates: list[float] = []
    for row in video_detections or []:
        if str((row or {}).get("source") or "").strip().lower() != "video":
            continue
        start_time = _safe_float(row.get("start_time"), default=-1.0)
        if start_time >= 0.0:
            track_candidates.append(start_time)
        frames = row.get("frames")
        if not isinstance(frames, list):
            continue
        for frame in frames:
            if not isinstance(frame, dict):
                continue
            if not _is_valid_track_bbox(frame.get("bbox")):
                continue
            ft = _safe_float(frame.get("t"), default=-1.0)
            if ft >= 0.0:
                bbox_candidates.append(ft)
    first_bbox = min(bbox_candidates) if bbox_candidates else None
    first_track = min(track_candidates) if track_candidates else None
    return first_bbox, first_track


def _latency_budget_breaches(
    *,
    trigger_to_first_bbox_latency_s: float | None,
    finalize_duration_ms: float | None,
    fusion_duration_ms: float | None,
    persist_duration_ms: float | None,
) -> list[dict[str, Any]]:
    checks = [
        (
            "trigger_to_first_bbox_latency_s",
            trigger_to_first_bbox_latency_s,
            float(app_config.get("processor.latency_budget_trigger_to_first_bbox_warn_s") or 5.0),
            float(app_config.get("processor.latency_budget_trigger_to_first_bbox_critical_s") or 8.0),
        ),
        (
            "finalize_duration_ms",
            finalize_duration_ms,
            float(app_config.get("processor.latency_budget_finalize_warn_ms") or 5000.0),
            float(app_config.get("processor.latency_budget_finalize_critical_ms") or 15000.0),
        ),
        (
            "fusion_duration_ms",
            fusion_duration_ms,
            float(app_config.get("processor.latency_budget_fusion_warn_ms") or 1200.0),
            float(app_config.get("processor.latency_budget_fusion_critical_ms") or 3500.0),
        ),
        (
            "persist_duration_ms",
            persist_duration_ms,
            float(app_config.get("processor.latency_budget_persist_warn_ms") or 1500.0),
            float(app_config.get("processor.latency_budget_persist_critical_ms") or 5000.0),
        ),
    ]
    breaches: list[dict[str, Any]] = []
    for metric, value, warn_thr, crit_thr in checks:
        try:
            metric_value = float(value) if value is not None else None
        except (TypeError, ValueError):
            metric_value = None
        if metric_value is None or metric_value <= 0:
            continue
        severity = None
        if metric_value >= max(warn_thr, crit_thr):
            severity = "critical"
        elif metric_value >= min(warn_thr, crit_thr):
            severity = "warning"
        if severity is None:
            continue
        breaches.append(
            {
                "metric": metric,
                "value": round(metric_value, 6),
                "warn_threshold": round(float(warn_thr), 6),
                "critical_threshold": round(float(crit_thr), 6),
                "severity": severity,
            },
        )
    return breaches


def _blind_required_frames(
    *,
    min_duration_s: float,
    min_frames_cfg: int,
    min_effective_fps: float,
) -> int:
    duration_floor = max(0.0, float(min_duration_s))
    fps_floor = max(0.1, float(min_effective_fps))
    duration_based = int(max(1, round(duration_floor * fps_floor)))
    return int(max(1, min(int(max(1, min_frames_cfg)), duration_based)))


def _health_event_age_seconds(row: Any | None) -> float | None:
    if not row:
        return None
    try:
        created_at = str(row["created_at"] or "").strip()
        if not created_at:
            return None
        dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return float((datetime.now(timezone.utc) - dt.astimezone(timezone.utc)).total_seconds())
    except Exception:
        return None


def _compute_blind_score(
    *,
    yolo_ran_now: int,
    yolo_raw_now: int,
    frigate_only_now: int,
    current_duration_s: float,
    required_frames: int,
    min_frigate_frames: int,
    min_duration_s: float,
) -> float:
    frames_ratio = min(1.0, float(yolo_ran_now) / float(max(1, required_frames)))
    raw_signal = 1.0 if int(yolo_raw_now) == 0 else 0.0
    if int(min_frigate_frames) <= 0:
        frigate_ratio = 1.0
    else:
        frigate_ratio = min(1.0, float(frigate_only_now) / float(min_frigate_frames))
    duration_ratio = min(1.0, float(current_duration_s) / float(max(0.1, min_duration_s)))
    score = 0.35 * frames_ratio + 0.35 * raw_signal + 0.2 * frigate_ratio + 0.1 * duration_ratio
    return max(0.0, min(1.0, score))


def _blind_suspected_from_final_stats(
    *,
    final_rs: dict[str, Any],
    blind_score: float,
    blind_score_threshold: float,
) -> bool:
    """Suspected only after final session counters (avoids early-copy race)."""
    raw_boxes = int(final_rs.get("yolo_raw_boxes_total") or 0)
    track_frames = int(final_rs.get("yolo_frames_with_tracks") or 0)
    raw_frame_hits = int(final_rs.get("yolo_frames_with_raw_boxes") or 0)
    if raw_boxes > 0 or track_frames > 0 or raw_frame_hits > 0:
        return False
    return bool(blind_score >= float(blind_score_threshold) * 0.5)


def _emit_frigate_hub_panic_if_needed(
    *,
    session_summary: dict[str, Any],
    ctx: dict[str, Any],
    recording_context: dict[str, Any] | None,
    mqtt_events: list[dict],
    output_path_physical: str,
) -> None:
    """Raise panic signal when Frigate saw sustained activity and Hub accepted none."""
    enabled = bool(app_config.get("detection.panic_gate_enabled", True))
    if not enabled:
        return
    min_frigate_events = int(app_config.get("detection.panic_gate_min_frigate_events") or 8)
    min_duration = float(app_config.get("detection.panic_gate_min_duration_seconds") or 20.0)
    duration_s = float(session_summary.get("duration_s") or 0.0)
    accepted = int(session_summary.get("yolo_accepted_boxes_total") or 0)
    frigate_events = [
        ev for ev in (mqtt_events or []) if str((ev or {}).get("source") or "").strip().lower() == "frigate"
    ]
    frigate_count = len(frigate_events)
    if not (duration_s >= max(1.0, min_duration) and accepted == 0 and frigate_count >= max(1, min_frigate_events)):
        return
    panic_payload = {
        "event": "frigate_hub_panic",
        "camera_id": ctx.get("triggered_camera"),
        "duration_s": round(duration_s, 3),
        "frigate_events": frigate_count,
        "yolo_raw_boxes_total": int(session_summary.get("yolo_raw_boxes_total") or 0),
        "yolo_accepted_boxes_total": accepted,
        "session_extended_by_frigate_only": int(session_summary.get("session_extended_by_frigate_only") or 0),
        "runtime_profile": session_summary.get("runtime_profile"),
        "video_dir": output_path_physical,
    }
    inc_counter("detection_panic_frigate_without_hub_total")
    logging.error("detection_panic %s", json.dumps(panic_payload, default=str, separators=(",", ":")))
    try:
        diagnostics = collect_root_cause_snapshot(
            output_path_physical,
            include_dmesg=False,
        )
        diagnostics["panic_payload"] = panic_payload
        diagnostics["recording_context"] = dict(recording_context or {})
        write_root_cause_dump(Path(get_data_dir()), diagnostics, "panic_frigate_without_hub")
    except Exception:
        logging.debug("panic root-cause dump skipped", exc_info=True)


def _run_self_heal_escalation(
    *,
    repo: SessionStateRepository,
    app_config_obj,
    api: API,
    frame_processor,
    mqtt_aggregator,
    camera_id: str | None,
    diagnostics: dict[str, Any],
) -> tuple[str, dict[str, Any]]:
    if not bool(app_config_obj.get("detection.yolo_self_heal_restart_enabled", True)):
        return "disabled", diagnostics
    cooldown_s = float(app_config_obj.get("detection.yolo_self_heal_cooldown_seconds") or 300.0)
    escalation_window_s = float(app_config_obj.get("detection.yolo_self_heal_escalation_window_seconds") or 900.0)
    last_action = repo.latest_health_event(event_type="yolo_self_heal_action", camera_id=camera_id)
    age_s = _health_event_age_seconds(last_action)
    if age_s is not None and age_s < max(0.0, cooldown_s):
        return "cooldown_skip", diagnostics

    stage = 0
    if last_action:
        try:
            payload = json.loads(str(last_action["details_json"] or "{}"))
            prev_stage = int(payload.get("stage") or 0)
            if age_s is not None and age_s <= max(0.0, escalation_window_s):
                stage = min(prev_stage + 1, 3)
        except Exception:
            stage = 0
    actions = ("soft_clear", "reinit", "restart", "alert")
    action = actions[stage]
    details = dict(diagnostics)
    details["stage"] = stage
    details["action"] = action

    if action == "soft_clear":
        try:
            frame_processor.reset()
            details["soft_clear_ok"] = True
        except Exception:
            details["soft_clear_ok"] = False
    elif action == "reinit":
        try:
            frame_processor.reset()
            strat = getattr(frame_processor, "strategy", None)
            if strat is not None and hasattr(strat, "reset"):
                strat.reset()
            details["reinit_ok"] = True
        except Exception:
            details["reinit_ok"] = False
    elif action == "restart":
        flag_path = restart_flag_path()
        try:
            with open(flag_path, "w", encoding="utf-8") as fh:
                fh.write("yolo_blind_confirmed\n")
            details["restart_flag_path"] = flag_path
            details["restart_requested"] = True
        except Exception:
            details["restart_requested"] = False
    elif action == "alert":
        try:
            api.activity_log(type="yolo_self_heal_alert", data=details)
            details["alert_emitted"] = True
        except Exception:
            details["alert_emitted"] = False

    repo.append_detector_health_event(
        event_type="yolo_self_heal_action",
        severity="warning" if action != "alert" else "error",
        camera_id=camera_id,
        details=details,
    )
    return action, details


def _weak_yolo_salvage_row_from_track(
    track_id: Any,
    track: dict[str, Any],
    *,
    max_det_conf: float,
) -> dict[str, Any]:
    detector_events = list(track.get("detector_events") or [])
    detector_label = "Bird"
    if detector_events:
        detector_label = str(detector_events[-1].get("label") or detector_label).strip() or "Bird"
    species_name = detector_label if detector_label in {"Bird", "Rodent", "Animal"} else "Bird"
    return {
        "track_id": int(track_id) if str(track_id).lstrip("-").isdigit() else -9999,
        "accepted": True,
        "visit_eligible": False,
        "notification_eligible": False,
        "species_name": species_name,
        "species": species_name,
        "confidence": float(max_det_conf),
        "start_time": float(track.get("start_time") or 0.0),
        "end_time": float(track.get("end_time") or 0.0),
        "detection_provider": "yolo",
        "detector_confidence": float(max_det_conf),
        "classifier_confidence": None,
        "decision_reason": "review_only_weak_yolo_salvage",
        "decision_kind": "review_only_generic",
        "outcome_bucket": "review_only",
        "source": "video",
        "frames": list(track.get("frames") or []),
        "best_frame": track.get("best_frame"),
        "best_frame_score": float(track.get("best_frame_score") or 0.0),
        "yolo_weak_track_salvage": True,
    }


def _build_weak_yolo_salvage_row(
    tracks: dict[str, Any] | dict[int, Any],
    *,
    min_confidence: float = 0.10,
) -> dict[str, Any] | None:
    rows = _build_weak_yolo_salvage_rows(tracks, min_confidence=min_confidence, max_rows=1)
    return rows[0] if rows else None


def _build_weak_yolo_salvage_rows(
    tracks: dict[str, Any] | dict[int, Any],
    *,
    min_confidence: float = 0.10,
    max_rows: int = 5,
) -> list[dict[str, Any]]:
    scored: list[tuple[float, Any, dict[str, Any], float]] = []
    for track_id, track in (tracks or {}).items():
        frames = list(track.get("frames") or [])
        if not frames:
            continue
        detector_events = list(track.get("detector_events") or [])
        max_det_conf = max((float(ev.get("confidence") or 0.0) for ev in detector_events), default=0.0)
        if max_det_conf < float(min_confidence):
            continue
        try:
            duration = max(0.0, float(track.get("end_time") or 0.0) - float(track.get("start_time") or 0.0))
        except (TypeError, ValueError):
            duration = 0.0
        score = float(len(frames)) + duration * 5.0 + max_det_conf * 3.0
        scored.append((score, track_id, track, max_det_conf))
    if not scored:
        return []
    scored.sort(key=lambda item: item[0], reverse=True)
    limit = max(1, int(max_rows))
    return [
        _weak_yolo_salvage_row_from_track(track_id, track, max_det_conf=max_det_conf)
        for _, track_id, track, max_det_conf in scored[:limit]
    ]


def _pick_frigate_evidence_for_salvage(
    mqtt_events: list[dict[str, Any]],
    *,
    frigate_trigger_event: dict[str, Any] | None,
    session_camera_id: str | None,
) -> dict[str, Any] | None:
    candidates: list[dict[str, Any]] = []
    if isinstance(frigate_trigger_event, dict) and frigate_trigger_event:
        candidates.append(frigate_trigger_event)
    cam_key = str(session_camera_id or "").strip().lower()
    for ev in mqtt_events or []:
        if str((ev or {}).get("source") or "").strip().lower() != "frigate":
            continue
        if cam_key:
            ev_cam = str((ev or {}).get("camera") or "").strip().lower()
            if ev_cam and ev_cam != cam_key:
                continue
        candidates.append(ev)
    if not candidates:
        return None

    def _score(ev: dict[str, Any]) -> tuple[float, float]:
        snapshot = 1.0 if bool(ev.get("_session_trigger_snapshot")) else 0.0
        try:
            conf = float(ev.get("confidence") or 0.0)
        except (TypeError, ValueError):
            conf = 0.0
        return snapshot, conf

    return max(candidates, key=_score)


def _build_frigate_trigger_review_salvage_row(
    ev: dict[str, Any],
    *,
    duration_s: float,
    app_config,
) -> dict[str, Any]:
    from detection_fusion import _species_mapping
    from species_normalizer import normalize

    species_mapping = _species_mapping(app_config)
    raw = ev.get("species") or ev.get("sub_label") or ev.get("label") or ""
    species = normalize(str(raw), species_mapping) if str(raw).strip() else ""
    if not species or species.lower() == "unknown":
        species = str(raw).strip() or "Unidentified"
    try:
        conf = float(ev.get("confidence") or 0.0)
    except (TypeError, ValueError):
        conf = 0.0
    if conf <= 0.0:
        try:
            conf = float(app_config.get("detection.frigate_standalone_missing_score_fallback") or 0.68)
        except (TypeError, ValueError):
            conf = 0.68
    return {
        "track_id": -9001,
        "accepted": True,
        "visit_eligible": False,
        "notification_eligible": False,
        "species_name": species,
        "species": species,
        "confidence": max(0.0, min(1.0, conf)),
        "start_time": 0.0,
        "end_time": max(0.0, float(duration_s)),
        "detection_provider": "frigate",
        "detector_confidence": max(0.0, min(1.0, conf)),
        "classifier_confidence": None,
        "decision_reason": "review_only_frigate_trigger_salvage",
        "decision_kind": "review_only_generic",
        "outcome_bucket": "review_only",
        "source": "video",
        "frigate_trigger_salvage": True,
    }


def _yolo_anchor_row_score(row: dict[str, Any]) -> tuple[float, float, int]:
    return (
        float(row.get("confidence") or 0.0),
        float(row.get("best_frame_score") or 0.0),
        len(row.get("frames") or []),
    )


def _best_yolo_anchor_row(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    anchors = _best_yolo_anchor_rows(rows, max_rows=1)
    return anchors[0] if anchors else None


def _best_yolo_anchor_rows(rows: list[dict[str, Any]], *, max_rows: int = 3) -> list[dict[str, Any]]:
    yolo_rows = [
        row for row in (rows or []) if str((row or {}).get("detection_provider") or "").strip().lower() == "yolo"
    ]
    if not yolo_rows:
        return []
    seen_track_ids: set[int] = set()
    ordered = sorted(yolo_rows, key=_yolo_anchor_row_score, reverse=True)
    out: list[dict[str, Any]] = []
    for row in ordered:
        tid = row.get("track_id")
        try:
            tid_int = int(tid) if tid is not None else None
        except (TypeError, ValueError):
            tid_int = None
        if tid_int is not None:
            if tid_int in seen_track_ids:
                continue
            seen_track_ids.add(tid_int)
        out.append(row)
        if len(out) >= max(1, int(max_rows)):
            break
    return out


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


def finalize_motion_recording(
    api: API,
    motion_detector: Any,
    mqtt_aggregator: Any,
    frame_processor: Any,
    decision_maker: Any,
    *,
    start_time: datetime,
    end_time: datetime,
    output_path_physical: str,
    output_path_logical: str,
    video_output: str,
    video_path_for_api: str,
    scales_topic_arg: Optional[str],
    data_dir: str,
    recording_context: Optional[dict[str, Any]] = None,
) -> None:
    """Свести YOLO+MQTT, сохранить видео в API, уведомления; без детекций — удалить папку."""
    finalize_started_ts = time.perf_counter()
    fusion_started_ts: float | None = None
    fusion_finished_ts: float | None = None
    persist_started_ts: float | None = None
    persist_finished_ts: float | None = None
    decision_trace_started_ts: float | None = None
    decision_trace_finished_ts: float | None = None
    merge_window = int(app_config.get("detection.merge_window_seconds") or 5)
    yolo_tracks_count = len(frame_processor.tracks)
    try:
        from finalize_classification import enrich_tracks_classifier_at_finalize, defer_classifier_to_finalize

        if defer_classifier_to_finalize(app_config):
            enrich_tracks_classifier_at_finalize(
                frame_processor.tracks,
                getattr(frame_processor, "strategy", None),
                app_config,
            )
    except ImportError:
        pass
    decisions = decision_maker.get_decisions(frame_processor.tracks)
    video_detections = [item for item in decisions if item.get("accepted", False)]
    rejected_decisions = [item for item in decisions if not item.get("accepted", False)]
    clf_review_n = sum(1 for item in decisions if bool(item.get("classifier_needs_review")))
    if clf_review_n:
        inc_counter("classifier_needs_review_total", clf_review_n)
    yolo_passed_count = len(video_detections)
    trigger_source = None
    session_camera_id = None
    if isinstance(recording_context, dict):
        trigger_source = str(recording_context.get("triggered_by") or "").strip().lower() or None
        session_camera_id = str(recording_context.get("triggered_camera") or "").strip() or None
    scope_camera_id = None
    if trigger_source == "frigate":
        scope_camera_id = session_camera_id
    frigate_trigger_event = None
    if isinstance(recording_context, dict):
        raw_trigger_ev = recording_context.get("frigate_trigger_event")
        if isinstance(raw_trigger_ev, dict) and raw_trigger_ev:
            frigate_trigger_event = raw_trigger_ev
    mqtt_events = get_recording_mqtt_events(
        mqtt_aggregator,
        motion_detector,
        start_time=start_time,
        end_time=end_time,
        merge_window=merge_window,
        yolo_tracks_count=yolo_tracks_count,
        scope_camera_id=scope_camera_id,
        lookback_camera_id=session_camera_id,
        trigger_source=trigger_source,
        frigate_trigger_event=frigate_trigger_event,
    )
    if yolo_tracks_count > 0:
        min_dur = app_config.get("processor.min_track_duration", 1)
        logging.info(
            "ByteTrack: %s tracks, %s passed min_track_duration=%ss (species with frames)",
            yolo_tracks_count,
            yolo_passed_count,
            min_dur,
        )
        if yolo_passed_count == 0 and yolo_tracks_count > 0:
            logging.warning(
                "YOLO: %s ByteTrack row(s) but none passed DecisionMaker "
                "(duration < processor.min_track_duration, confidence below "
                "processor.min_confidence_to_process / overrides, or below "
                "detection.min_confidence_to_store when falling back to detector label). "
                "Final result will stay empty unless YOLO detector/classifier produce a valid track — lower min_track_duration "
                "or thresholds if you expect video tracks.",
                yolo_tracks_count,
            )
            for tid, t in frame_processor.tracks.items():
                dur = t.get("end_time", 0) - t.get("start_time", 0)
                detector_events = len(t.get("detector_events", []))
                classifier_events = len(t.get("classifier_events", []))
                logging.info(
                    "  track %s: duration=%.2fs, detector_events=%s, classifier_events=%s",
                    tid,
                    dur,
                    detector_events,
                    classifier_events,
                )
        if rejected_decisions:
            rejected_summary = _rejected_reason_counts(rejected_decisions)
            logging.info(
                "DecisionMaker rejected tracks: %s",
                rejected_summary,
            )
    elif mqtt_events:
        standalone_on = bool(app_config.get("detection.frigate_standalone_when_no_yolo", False))
        if not standalone_on:
            logging.warning(
                "ByteTrack: 0 YOLO tracks but %s MQTT events. "
                "Enable detection.frigate_standalone_when_no_yolo for Frigate-only rows.",
                len(mqtt_events),
            )

    audio_detections: list = []
    pre_fusion_finished_ts = time.perf_counter()

    accepted_pre_fusion = list(video_detections)
    triggered_camera = None
    if trigger_source == "frigate" and isinstance(recording_context, dict):
        triggered_camera = session_camera_id
    rs_ctx = {}
    if isinstance(recording_context, dict) and isinstance(recording_context.get("runtime_signals"), dict):
        rs_ctx = dict(recording_context.get("runtime_signals") or {})
    yolo_blind_confirmed = False
    blind_score = 0.0
    blind_suspected = False
    blind_recovered = False
    try:
        yolo_ran_now = int(rs_ctx.get("yolo_frames_ran") or 0)
        yolo_raw_now = int(rs_ctx.get("yolo_raw_boxes_total") or 0)
        frigate_only_now = int(rs_ctx.get("session_extended_by_frigate_only") or 0)
        blind_min_sessions = int(app_config.get("detection.yolo_blind_required_consecutive_sessions") or 1)
        blind_min_frames = int(app_config.get("detection.yolo_blind_min_frames") or 180)
        blind_min_frigate = int(app_config.get("detection.yolo_blind_min_frigate_only_frames") or 120)
        blind_min_duration_s = float(app_config.get("detection.yolo_blind_min_duration_seconds") or 30.0)
        blind_min_effective_fps = float(app_config.get("detection.yolo_blind_min_effective_fps") or 2.0)
        blind_score_threshold = float(app_config.get("detection.yolo_blind_score_threshold") or 0.7)
        current_duration_s = max(0.0, float((end_time - start_time).total_seconds()))
        required_frames = _blind_required_frames(
            min_duration_s=blind_min_duration_s,
            min_frames_cfg=blind_min_frames,
            min_effective_fps=blind_min_effective_fps,
        )
        blind_score = _compute_blind_score(
            yolo_ran_now=yolo_ran_now,
            yolo_raw_now=yolo_raw_now,
            frigate_only_now=frigate_only_now,
            current_duration_s=current_duration_s,
            required_frames=required_frames,
            min_frigate_frames=blind_min_frigate,
            min_duration_s=blind_min_duration_s,
        )
        frigate_blind_gate = blind_min_frigate <= 0 or frigate_only_now >= blind_min_frigate
        blind_now = (
            yolo_ran_now >= required_frames
            and yolo_raw_now == 0
            and frigate_blind_gate
            and current_duration_s >= max(0.0, blind_min_duration_s)
        )
        repo = SessionStateRepository()
        blind_recent = repo.is_blind_confirmed(
            camera_id=session_camera_id,
            min_recent_sessions=max(1, blind_min_sessions),
            min_yolo_frames=max(1, blind_min_frames),
            min_frigate_only_frames=max(1, blind_min_frigate),
            min_duration_seconds=max(0.0, blind_min_duration_s),
            min_effective_fps=max(0.1, blind_min_effective_fps),
        )
        score_ok = blind_score >= blind_score_threshold
        # is_blind_confirmed reads only prior sessions in SQLite; current clip is not
        # persisted yet, so blind_recent lags by one. Same-session blind_now must count
        # for Frigate standalone when require_blind_yolo is enabled.
        yolo_blind_confirmed = bool(
            score_ok and ((blind_now and blind_recent) or (blind_now and yolo_ran_now >= required_frames))
        )
        if yolo_raw_now > 0:
            recent = repo.recent_blind_sessions(camera_id=session_camera_id, limit=1)
            if recent and int(recent[0]["yolo_blind_confirmed"] or 0) == 1:
                blind_recovered = True
    except Exception:
        logging.debug("finalize: blind-state probe failed", exc_info=True)
    fusion_started_ts = time.perf_counter()
    video_detections = build_fused_video_detections(
        video_detections,
        mqtt_events,
        start_time=start_time,
        end_time=end_time,
        app_config=app_config,
        triggered_camera=triggered_camera,
        yolo_blind_confirmed=yolo_blind_confirmed,
        yolo_blind_score=blind_score,
    )
    rejected_decisions.extend(
        collect_post_fusion_rejections(
            app_config,
            accepted_pre_fusion=accepted_pre_fusion,
            persisted_detections=video_detections,
        )
        if not linear_skip_legacy_fusion_safeguards(app_config)
        else []
    )
    if is_linear_pipeline(app_config):
        logging.info(
            "Linear pipeline stage=%s fused_rows=%s",
            STAGE_CLASSIFY_ENRICH,
            len(video_detections or []),
        )
    raw_core_anchor = app_config.get("detection.yolo_core_anchor_enabled")
    if linear_skip_legacy_fusion_safeguards(app_config):
        yolo_core_anchor_enabled = False
    elif raw_core_anchor is None:
        yolo_core_anchor_enabled = not binary_track_first_enabled(app_config)
    else:
        yolo_core_anchor_enabled = bool(raw_core_anchor)
    if yolo_core_anchor_enabled:
        try:
            anchor_max = int(app_config.get("detection.yolo_core_anchor_max_rows") or 3)
        except (TypeError, ValueError):
            anchor_max = 3
        pre_fusion_yolo_anchors = [
            row
            for row in _best_yolo_anchor_rows(accepted_pre_fusion, max_rows=anchor_max)
            if str(row.get("decision_kind") or "").strip().lower() not in {"review_only_generic", "review_only"}
            and str(row.get("decision_reason") or "").strip().lower() != "review_only_generic_bird"
        ]
        has_fused_yolo = any(
            str((row or {}).get("detection_provider") or "").strip().lower() == "yolo" for row in video_detections
        )
        # Keep YOLO as pipeline core: restore top pre-fusion YOLO rows when fusion dropped them all.
        if yolo_tracks_count > 0 and pre_fusion_yolo_anchors and not has_fused_yolo:
            for pre_fusion_yolo_anchor in pre_fusion_yolo_anchors:
                anchor_row = dict(pre_fusion_yolo_anchor)
                anchor_row["yolo_core_anchor_forced"] = True
                if not str(anchor_row.get("decision_reason") or "").strip():
                    anchor_row["decision_reason"] = "yolo_core_anchor_forced"
                if not str(anchor_row.get("decision_kind") or "").strip():
                    anchor_row["decision_kind"] = "accepted_species"
                video_detections.append(anchor_row)
            logging.warning(
                "Finalize safeguard: restored %s YOLO anchor row(s) after fusion removed all YOLO rows "
                "(tracks=%s, pre_fusion_accepted=%s).",
                len(pre_fusion_yolo_anchors),
                yolo_tracks_count,
                len(accepted_pre_fusion),
            )
    require_bbox_tracks = bool(app_config.get("detection.require_bbox_tracks_for_persisted_rows", True))
    if require_bbox_tracks and video_detections:
        kept_rows: list[dict[str, Any]] = []
        dropped_missing_frames = 0
        dropped_empty_bbox = 0
        dropped_bad_bbox_frames = 0
        for row in video_detections:
            row_source = str((row or {}).get("source") or "").strip().lower()
            if row_source != "video":
                kept_rows.append(row)
                continue
            frames = row.get("frames")
            if not isinstance(frames, list) or not frames:
                dropped_missing_frames += 1
                rejected_decisions.append(
                    {
                        "species_name": row.get("species_name") or row.get("species"),
                        "detection_provider": row.get("detection_provider"),
                        "reject_reason_code": "missing_track_frames",
                        "decision_reason": "rejected_missing_track_frames",
                    }
                )
                continue
            valid_frames = _valid_track_frames(frames)
            if not valid_frames:
                dropped_empty_bbox += 1
                rejected_decisions.append(
                    {
                        "species_name": row.get("species_name") or row.get("species"),
                        "detection_provider": row.get("detection_provider"),
                        "reject_reason_code": "empty_bbox_frames",
                        "decision_reason": "rejected_empty_bbox_frames",
                    }
                )
                continue
            if len(valid_frames) != len(frames):
                row = dict(row)
                row["frames"] = valid_frames
                row["dropped_invalid_bbox_frames"] = int(len(frames) - len(valid_frames))
                dropped_bad_bbox_frames += int(len(frames) - len(valid_frames))
            kept_rows.append(row)
        dropped_total = dropped_missing_frames + dropped_empty_bbox
        if dropped_total:
            inc_counter("recording_rejected_bbox_track_contract_total", dropped_total)
            logging.warning(
                "Finalize contract: dropped %s row(s) (missing_frames=%s empty_bbox=%s)",
                dropped_total,
                dropped_missing_frames,
                dropped_empty_bbox,
            )
        if dropped_bad_bbox_frames:
            logging.info(
                "Finalize contract: pruned %s invalid bbox frame(s) across persisted rows",
                dropped_bad_bbox_frames,
            )
        video_detections = kept_rows
    video_detections = _sanitize_persisted_overlay_frames(video_detections)
    if (
        not video_detections
        and yolo_tracks_count > 0
        and bool(app_config.get("detection.yolo_weak_track_salvage_enabled", True))
        and not linear_skip_legacy_fusion_safeguards(app_config)
    ):
        try:
            salvage_min_conf = float(app_config.get("detection.yolo_weak_track_salvage_min_confidence") or 0.10)
        except (TypeError, ValueError):
            salvage_min_conf = 0.10
        try:
            salvage_max_rows = int(app_config.get("detection.yolo_weak_track_salvage_max_rows") or 5)
        except (TypeError, ValueError):
            salvage_max_rows = 5
        salvage_rows = _build_weak_yolo_salvage_rows(
            frame_processor.tracks,
            min_confidence=salvage_min_conf,
            max_rows=salvage_max_rows,
        )
        if salvage_rows:
            video_detections = salvage_rows
            logging.warning(
                "Finalize safeguard: recovered %s weak YOLO track(s) as review-only (top track_id=%s, conf=%.3f).",
                len(salvage_rows),
                salvage_rows[0].get("track_id"),
                float(salvage_rows[0].get("confidence") or 0.0),
            )
    salvage_enabled = bool(app_config.get("detection.frigate_trigger_review_salvage_enabled", False))
    salvage_allow_without_yolo = bool(
        app_config.get("detection.frigate_trigger_review_salvage_allow_without_yolo_tracks", False)
    )
    if salvage_enabled and not salvage_allow_without_yolo and yolo_tracks_count <= 0:
        salvage_enabled = False
    if (
        not video_detections
        and salvage_enabled
        and not linear_skip_frigate_salvage_paths(app_config)
        and (
            trigger_source == "frigate"
            or isinstance(frigate_trigger_event, dict)
            or any(str((ev or {}).get("source") or "").strip().lower() == "frigate" for ev in mqtt_events)
        )
    ):
        try:
            duration_s = max(0.0, (end_time - start_time).total_seconds())
        except (TypeError, AttributeError):
            duration_s = 0.0
        evidence = _pick_frigate_evidence_for_salvage(
            mqtt_events,
            frigate_trigger_event=frigate_trigger_event,
            session_camera_id=session_camera_id,
        )
        if evidence is not None and not skip_frigate_ev_for_standalone(evidence, app_config):
            salvage_row = _build_frigate_trigger_review_salvage_row(
                evidence,
                duration_s=duration_s,
                app_config=app_config,
            )
            video_detections = [salvage_row]
            inc_counter("recording_frigate_trigger_salvage_total")
            logging.warning(
                "Finalize safeguard: recovered Frigate trigger evidence as review-only "
                "(species=%s, conf=%.3f, camera=%s).",
                salvage_row.get("species_name"),
                float(salvage_row.get("confidence") or 0.0),
                session_camera_id,
            )
    track_first_enabled = bool(app_config.get("detection.track_first_gate_enabled", True))
    video_detections, track_first_rejected = apply_track_first_persist_gate(
        video_detections,
        enabled=track_first_enabled,
    )
    if track_first_rejected:
        rejected_decisions.extend(track_first_rejected)
        inc_counter("recording_rejected_track_first_gate_total", len(track_first_rejected))
        logging.warning(
            "Track-first gate: dropped %s row(s) without bbox+track (ingestible=%s).",
            len(track_first_rejected),
            has_ingestible_track_rows(video_detections),
        )
    video_file_ok_early = _is_playable_video_file(video_output)
    if video_detections and video_file_ok_early:
        notify_unique_species(
            api,
            app_config,
            video_detections=video_detections,
            video_output=video_output,
            video_id=None,
            encode_func=encode_notify_preview_base64,
        )
    reid_enrich_duration_ms: float | None = None
    if video_detections:
        reid_enrich_started_ts = time.perf_counter()
        try:
            video_detections = enrich_runtime_reid_detections(
                video_detections,
                video_path=video_path_for_api,
            )
        except Exception as exc:
            inc_counter("reid_runtime_enrich_fail_total")
            logging.warning("Runtime ReID enrich failed; keep fused detections: %s", exc)
        reid_enrich_duration_ms = round(
            max(0.0, (time.perf_counter() - reid_enrich_started_ts) * 1000.0),
            3,
        )
        if is_linear_pipeline(app_config):
            logging.info(
                "Linear pipeline stage=%s rows=%s duration_ms=%s",
                STAGE_REID_BEHAVIOR,
                len(video_detections or []),
                reid_enrich_duration_ms,
            )
    fusion_finished_ts = time.perf_counter()

    fusion_fs = sum(1 for d in video_detections if d.get("frigate_standalone"))
    fusion_yolo = 0
    fusion_frigate = 0
    for d in video_detections:
        prov = str((d or {}).get("detection_provider") or "").strip().lower()
        if prov == "yolo":
            fusion_yolo += 1
        elif prov == "frigate":
            fusion_frigate += 1
    logging.info(
        "Finalize merge snapshot: bytetrack_rows=%s pre_fusion_accepted=%s "
        "post_fusion_persisted=%s rejected_decision_rows=%s "
        "mqtt_events_in_window=%s fusion_frigate_standalone_rows=%s "
        "fusion_provider_yolo=%s fusion_provider_frigate=%s",
        yolo_tracks_count,
        len(accepted_pre_fusion),
        len(video_detections),
        len(rejected_decisions),
        len(mqtt_events),
        fusion_fs,
        fusion_yolo,
        fusion_frigate,
    )
    if yolo_tracks_count > 0 and len(video_detections) > 0 and fusion_yolo == 0:
        logging.warning(
            "Finalize risk: YOLO had %s track(s), but persisted rows are all non-YOLO providers. "
            "Check fusion/source_priority and trigger settings.",
            yolo_tracks_count,
        )
    persisted_without_frames = sum(
        1
        for d in video_detections
        if str((d or {}).get("source") or "").strip().lower() == "video" and not d.get("frames")
    )
    if persisted_without_frames:
        logging.warning(
            "Finalize risk: %s persisted video detection(s) have empty frames (overlay will be missing).",
            persisted_without_frames,
        )

    for i, d in enumerate(video_detections):
        n_frames = len(d.get("frames") or [])
        if n_frames > 0:
            logging.info(
                "Detection %s: %s has %s track frames",
                i,
                d.get("species_name"),
                n_frames,
            )
        else:
            logging.debug(
                "Detection %s: %s has no frames (source=%s)",
                i,
                d.get("species_name"),
                d.get("source"),
            )

    if mqtt_aggregator and video_detections:
        mqtt_aggregator.publish_detections(video_detections, start_time, end_time)

    video_summary = [{k: v for k, v in d.items() if k != "best_frame"} for d in video_detections]
    if video_detections:
        audio_evidence_summary = Counter(str(item.get("audio_evidence") or "none") for item in video_detections)
        logging.info(
            "Fusion audio evidence summary: %s",
            dict(sorted(audio_evidence_summary.items())),
        )
    decision_trace: dict[str, Any] | None = None
    if video_detections or rejected_decisions:
        decision_trace_started_ts = time.perf_counter()
        decision_trace = build_decision_trace_payload(
            app_config=app_config,
            start_time=start_time,
            end_time=end_time,
            video_path=video_path_for_api,
            persisted_tracks=video_detections,
            rejected_tracks=rejected_decisions,
            recording_context=recording_context,
            scales_topic_arg=scales_topic_arg,
        )
        decision_trace_finished_ts = time.perf_counter()
        scales_evidence = decision_trace["scales_evidence"]
    else:
        scales_evidence = _default_scales_evidence_snapshot(
            app_config_obj=app_config,
            scales_topic_arg=scales_topic_arg,
        )
    logging.info(
        "Processing stopped. Video Result: %s; Audio Result: %s",
        video_summary,
        audio_detections,
    )
    if len(video_detections) == 0 and mqtt_aggregator:
        global _no_detections_warn_next_monotonic
        _no_detections_warn_next_monotonic = log_no_detections_after_merge(
            track_count=len(frame_processor.tracks),
            mqtt_event_count=len(mqtt_events),
            now_monotonic=time.monotonic(),
            next_warn_monotonic=_no_detections_warn_next_monotonic,
            warn_interval_seconds=_NO_DETECTIONS_WARN_INTERVAL_S,
        )
    final_rejected_reason_counts = _rejected_reason_counts(rejected_decisions)
    if len(video_detections) == 0:
        log_no_detection_activity(
            api,
            track_count=len(frame_processor.tracks),
            mqtt_event_count=len(mqtt_events),
            rejected_count=len(rejected_decisions),
            video_path_for_api=video_path_for_api,
            trigger_source=trigger_source,
            triggered_camera=session_camera_id,
            rejected_reason_counts=final_rejected_reason_counts,
        )

    video_file_ok = _is_playable_video_file(video_output)
    if len(video_detections) > 0 and not video_file_ok:
        logging.error(
            "Finalize: %s detection(s) but video file missing: %s",
            len(video_detections),
            video_output,
        )
        log_missing_video_gate(
            api,
            detection_count=len(video_detections),
            video_path_for_api=video_path_for_api,
            video_output=video_output,
        )

    persist_started_ts = time.perf_counter()
    scales_duration_ms: float | None = None
    behavior_duration_ms: float | None = None
    create_video_duration_ms: float | None = None
    create_video_ingest_timing_ms: dict[str, float] | None = None
    dataset_crops_duration_ms: float | None = None
    video_id: int | None = None
    if len(video_detections) > 0 and video_file_ok:
        scales_started_ts = time.perf_counter()
        scales_delta_kg, scales_evidence_update = estimate_recording_scales_delta(
            app_config,
            video_detections,
            scales_topic_arg=scales_topic_arg,
            data_dir=data_dir,
            start_time=start_time,
            end_time=end_time,
        )
        scales_duration_ms = round(
            max(0.0, (time.perf_counter() - scales_started_ts) * 1000.0),
            3,
        )
        scales_evidence.update(scales_evidence_update)
        try:
            duration_behavior_s = max(0.0, (end_time - start_time).total_seconds())
        except Exception:
            duration_behavior_s = 0.0
        proc_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        behavior_started_ts = time.perf_counter()
        behavior_bundle = maybe_predict_video_behavior_bundle(
            app_config,
            video_detections,
            duration_s=duration_behavior_s,
            processor_cwd=proc_root,
            video_path=video_path_for_api,
        )
        behavior_duration_ms = round(
            max(0.0, (time.perf_counter() - behavior_started_ts) * 1000.0),
            3,
        )
        br_cfg = app_config.get("processor.behavior_recognition") or {}
        if not isinstance(br_cfg, dict):
            br_cfg = {}
        store_min = float(br_cfg.get("confidence_store_min") or 0.2)
        rev_thr = float(br_cfg.get("confidence_review_threshold") or 0.45)
        behavior_label_kw = None
        behavior_conf_kw = None
        bl = behavior_bundle.get("main_label")
        bc = float(behavior_bundle.get("main_confidence") or 0.0)
        if bl and bc >= store_min:
            behavior_label_kw = str(bl)
            behavior_conf_kw = bc
            if bc < rev_thr and video_detections:
                d0 = video_detections[0]
                if isinstance(d0, dict) and not (d0.get("review_reason") or "").strip():
                    d0["review_reason"] = "behavior_uncertainty"
                    d0["classifier_needs_review"] = True
        create_video_started_ts = time.perf_counter()
        resp = None
        try:
            from recording_session_manifest import (
                mark_persist_failed,
                mark_persist_ready,
                mark_persist_started,
            )

            mark_persist_started(output_path_physical, end_time=end_time)
            resp = api.create_video(
                video_detections,
                audio_detections,
                start_time,
                end_time,
                video_path_for_api,
                trigger_source=trigger_source,
                scales_weight_delta_kg=scales_delta_kg,
                behavior_label=behavior_label_kw,
                behavior_confidence=behavior_conf_kw,
                behavior_model_kind=behavior_bundle.get("model_kind"),
                behavior_model_version=behavior_bundle.get("model_version"),
                behavior_shadow_label=behavior_bundle.get("shadow_label"),
                behavior_shadow_confidence=behavior_bundle.get("shadow_confidence"),
                behavior_shadow_model_kind=behavior_bundle.get("shadow_model_kind"),
                behavior_shadow_model_version=behavior_bundle.get("shadow_model_version"),
            )
            video_id = response_video_id(resp)
            if video_id is None:
                mark_persist_failed(
                    output_path_physical,
                    reason="create_video_no_video_id",
                    end_time=end_time,
                )
                inc_counter("recording_persist_failed_total")
            else:
                mark_persist_ready(
                    output_path_physical,
                    video_id=int(video_id),
                    end_time=end_time,
                )
        except Exception as exc:
            try:
                from recording_session_manifest import mark_persist_failed

                mark_persist_failed(
                    output_path_physical,
                    reason=str(exc),
                    end_time=end_time,
                )
            except Exception:
                logging.debug("manifest persist_failed write skipped", exc_info=True)
            inc_counter("recording_persist_failed_total")
            logging.exception("FinalizeTransaction: create_video failed")
            resp = None
        create_video_duration_ms = round(
            max(0.0, (time.perf_counter() - create_video_started_ts) * 1000.0),
            3,
        )
        if isinstance(resp, dict):
            raw_timing = resp.get("ingest_timing_ms")
            if isinstance(raw_timing, dict):
                create_video_ingest_timing_ms = {
                    str(key): round(float(value), 3) for key, value in raw_timing.items() if value is not None
                }
        if video_id is not None:
            inc_counter("recording_persisted_total", len(video_detections))
            if decision_trace is not None:
                try:
                    decision_trace["video_id"] = int(video_id)
                except (TypeError, ValueError):
                    decision_trace["video_id"] = video_id
            sl = behavior_bundle.get("shadow_label")
            sc = behavior_bundle.get("shadow_confidence")
            logging.info(
                "behavior canary persist video_id=%s shadow=%s(%.3f) saved=%s engine=%s",
                video_id,
                sl,
                float(sc or 0.0),
                bool(sl and str(sl).strip()),
                str((br_cfg.get("engine") if isinstance(br_cfg, dict) else "") or ""),
            )
            api.activity_log_async(
                type="behavior_shadow_prediction",
                data={
                    "video_id": video_id,
                    "main_label": behavior_bundle.get("main_label"),
                    "main_confidence": behavior_bundle.get("main_confidence"),
                    "model_kind": behavior_bundle.get("model_kind"),
                    "model_version": behavior_bundle.get("model_version"),
                    "shadow_label": behavior_bundle.get("shadow_label"),
                    "shadow_confidence": behavior_bundle.get("shadow_confidence"),
                    "shadow_model_kind": behavior_bundle.get("shadow_model_kind"),
                    "shadow_model_version": behavior_bundle.get("shadow_model_version"),
                },
            )
        dataset_crops_started_ts = time.perf_counter()
        maybe_save_dataset_crops(
            app_config,
            video_id=video_id,
            video_detections=video_detections,
            data_dir=get_data_dir(),
            video_output=video_output,
        )
        dataset_crops_duration_ms = round(
            max(0.0, (time.perf_counter() - dataset_crops_started_ts) * 1000.0),
            3,
        )
    persist_finished_ts = time.perf_counter()
    if decision_trace is not None:
        write_decision_trace_activity(api, decision_trace)
    if not video_file_ok:
        remove_session_dir(output_path_physical, reason="bad")
    elif len(video_detections) == 0:
        if should_keep_empty_recording(app_config):
            logging.info(
                "keep_recording_when_no_detections: retaining session (0 detections, file source): %s",
                output_path_physical,
            )
        else:
            inc_counter("recording_clips_deleted_empty_total")
            remove_session_dir(output_path_physical, reason="empty")
    # Фоновая копия на SFTP/NAS (#350): не блокирует finalize; только если каталог ещё на диске.
    try:
        if os.path.isdir(output_path_physical):
            schedule_recordings_session_mirror(output_path_physical)
    except Exception as e:
        logging.debug("recordings mirror schedule skipped: %s", e)

    try:
        rs: dict[str, Any] = {}
        if isinstance(recording_context, dict):
            raw_rs = recording_context.get("runtime_signals")
            if isinstance(raw_rs, dict):
                rs = raw_rs
        duration_s: float | None
        try:
            duration_s = max(0.0, (end_time - start_time).total_seconds())
        except Exception:
            duration_s = None
        ctx: dict[str, Any] = recording_context if isinstance(recording_context, dict) else {}
        blind_score_threshold = float(app_config.get("detection.yolo_blind_score_threshold") or 0.7)
        blind_suspected = _blind_suspected_from_final_stats(
            final_rs=rs,
            blind_score=blind_score,
            blind_score_threshold=blind_score_threshold,
        )
        (
            trigger_to_first_bbox_s,
            first_bbox_latency_s,
            trigger_to_first_track_s,
            first_track_latency_s,
        ) = _resolve_session_latencies(rs, video_detections)
        wall_bbox_s = _runtime_wall_latency_seconds(
            rs,
            "trigger_to_first_bbox_wall_s",
        )
        wall_track_s = _runtime_wall_latency_seconds(
            rs,
            "trigger_to_first_track_wall_s",
        )
        finalize_duration_ms = round(
            max(0.0, (time.perf_counter() - finalize_started_ts) * 1000.0),
            3,
        )
        fusion_duration_ms = (
            None
            if fusion_started_ts is None or fusion_finished_ts is None
            else round(
                max(0.0, (fusion_finished_ts - fusion_started_ts) * 1000.0),
                3,
            )
        )
        persist_duration_ms = (
            None
            if persist_started_ts is None or persist_finished_ts is None
            else round(
                max(0.0, (persist_finished_ts - persist_started_ts) * 1000.0),
                3,
            )
        )
        pre_fusion_duration_ms = round(
            max(0.0, (pre_fusion_finished_ts - finalize_started_ts) * 1000.0),
            3,
        )
        decision_trace_duration_ms = (
            None
            if decision_trace_started_ts is None or decision_trace_finished_ts is None
            else round(
                max(
                    0.0,
                    (decision_trace_finished_ts - decision_trace_started_ts) * 1000.0,
                ),
                3,
            )
        )
        finalize_critical_path_ms = round(
            max(
                0.0,
                float(finalize_duration_ms or 0.0)
                - float(pre_fusion_duration_ms or 0.0)
                - float(decision_trace_duration_ms or 0.0),
            ),
            3,
        )
        session_summary: dict[str, Any] = {
            "event": "recording_session_summary",
            "duration_s": round(duration_s, 3) if duration_s is not None else None,
            "triggered_camera": ctx.get("triggered_camera"),
            "camera_slot": ctx.get("camera_slot"),
            "trigger_source": trigger_source,
            "video_path": video_path_for_api,
            "frames_seen": int(rs.get("frames_seen") or 0),
            "yolo_frames_ran": int(rs.get("yolo_frames_ran") or 0),
            "yolo_frames_with_tracks": int(rs.get("yolo_frames_with_tracks") or 0),
            "yolo_frames_with_raw_boxes": int(rs.get("yolo_frames_with_raw_boxes") or 0),
            "yolo_raw_boxes_total": int(rs.get("yolo_raw_boxes_total") or 0),
            "yolo_accepted_boxes_total": int(rs.get("yolo_accepted_boxes_total") or 0),
            "yolo_frames_raw_unaccepted": int(rs.get("yolo_frames_raw_unaccepted") or 0),
            "yolo_frames_raw_no_track": int(rs.get("yolo_frames_raw_no_track") or 0),
            "detect_first_confirmed": bool(rs.get("detect_first_confirmed")),
            "detect_first_anchor_track_id": rs.get("detect_first_anchor_track_id"),
            "detect_first_anchor_confidence": round(float(rs.get("detect_first_anchor_confidence") or 0.0), 4),
            "detect_first_window_frames": int(rs.get("detect_first_window_frames") or 0),
            "detect_first_window_hits": int(rs.get("detect_first_window_hits") or 0),
            "detection_acceptance_gap": bool(
                int(rs.get("yolo_raw_boxes_total") or 0) > 0 and int(rs.get("yolo_accepted_boxes_total") or 0) == 0
            ),
            "low_light_blocked_frames": int(rs.get("low_light_blocked_frames") or 0),
            "session_extended_by_frigate_only": int(rs.get("session_extended_by_frigate_only") or 0),
            "bytetrack_rows": yolo_tracks_count,
            "pre_fusion_accepted_rows": len(accepted_pre_fusion),
            "post_fusion_persisted": 1 if video_id is not None else 0,
            "ingestible_track_rows": count_ingestible_track_rows(video_detections),
            "db_persist_success": bool(video_id is not None),
            "fusion_dropped_rows": max(
                0,
                int(len(accepted_pre_fusion) - len(video_detections)),
            ),
            "rejected_decision_rows": len(rejected_decisions),
            "rejected_reason_counts": final_rejected_reason_counts,
            "mqtt_events_in_window": len(mqtt_events),
            "video_file_ok": bool(video_file_ok),
            "runtime_profile": rs.get("runtime_profile"),
            "yolo_blind_suspected": bool(blind_suspected),
            "yolo_blind_confirmed": bool(yolo_blind_confirmed),
            "yolo_blind_score": round(float(blind_score), 4),
            "track_id_switches_count": int(rs.get("track_id_switches_count") or 0),
            "avg_track_duration_sec": round(float(rs.get("avg_track_duration_sec") or 0.0), 4),
            "finalize_duration_ms": finalize_duration_ms,
            "finalize_critical_path_ms": finalize_critical_path_ms,
            "pre_fusion_duration_ms": pre_fusion_duration_ms,
            "decision_trace_duration_ms": decision_trace_duration_ms,
            "fusion_duration_ms": fusion_duration_ms,
            "persist_duration_ms": persist_duration_ms,
            "scales_duration_ms": scales_duration_ms,
            "behavior_duration_ms": behavior_duration_ms,
            "create_video_duration_ms": create_video_duration_ms,
            "create_video_ingest_timing_ms": create_video_ingest_timing_ms,
            "reid_enrich_duration_ms": reid_enrich_duration_ms,
            "dataset_crops_duration_ms": dataset_crops_duration_ms,
            "trigger_to_first_bbox_latency_s": (
                None if trigger_to_first_bbox_s is None else round(float(trigger_to_first_bbox_s), 6)
            ),
            "trigger_to_first_bbox_wall_s": (None if wall_bbox_s is None else round(float(wall_bbox_s), 6)),
            "trigger_to_first_track_wall_s": (None if wall_track_s is None else round(float(wall_track_s), 6)),
            "first_bbox_latency_s": (None if first_bbox_latency_s is None else round(float(first_bbox_latency_s), 6)),
            "first_track_latency_s": (
                None if trigger_to_first_track_s is None else round(float(trigger_to_first_track_s), 6)
            ),
            "video_first_track_latency_s": (
                None if first_track_latency_s is None else round(float(first_track_latency_s), 6)
            ),
            "concurrent_recording": dict(ctx.get("concurrent_recording") or {}),
        }
        latency_breaches = _latency_budget_breaches(
            trigger_to_first_bbox_latency_s=(
                None if trigger_to_first_bbox_s is None else float(trigger_to_first_bbox_s)
            ),
            finalize_duration_ms=(None if finalize_duration_ms is None else float(finalize_duration_ms)),
            fusion_duration_ms=(None if fusion_duration_ms is None else float(fusion_duration_ms)),
            persist_duration_ms=(None if persist_duration_ms is None else float(persist_duration_ms)),
        )
        session_summary["latency_budget_breaches"] = latency_breaches
        try:
            from trigger_graph import build_session_trigger_graph

            session_summary["trigger_graph"] = build_session_trigger_graph(
                session_summary=session_summary,
                recording_context=ctx,
                persisted_tracks=video_detections,
                rejected_tracks=rejected_decisions,
                mqtt_events=mqtt_events,
            )
        except Exception:
            logging.debug("trigger_graph build failed", exc_info=True)
        _emit_frigate_hub_panic_if_needed(
            session_summary=session_summary,
            ctx=ctx,
            recording_context=recording_context if isinstance(recording_context, dict) else {},
            mqtt_events=mqtt_events,
            output_path_physical=output_path_physical,
        )
        logging.info(
            "recording_session_summary %s",
            json.dumps(session_summary, default=str, separators=(",", ":")),
        )
        try:
            repo = SessionStateRepository()
            repo.save_session_runtime(session_summary)
            try:
                if bool(app_config.get("active_learning.enabled", True)):
                    al_reason = None
                    al_payload = {
                        "duration_s": session_summary.get("duration_s"),
                        "frames_seen": session_summary.get("frames_seen"),
                        "yolo_frames_ran": session_summary.get("yolo_frames_ran"),
                        "yolo_raw_boxes_total": session_summary.get("yolo_raw_boxes_total"),
                        "post_fusion_persisted": session_summary.get("post_fusion_persisted"),
                        "session_extended_by_frigate_only": session_summary.get("session_extended_by_frigate_only"),
                        "blind_score": session_summary.get("yolo_blind_score"),
                    }
                    if (
                        int(session_summary.get("session_extended_by_frigate_only") or 0) > 0
                        and int(session_summary.get("yolo_raw_boxes_total") or 0) == 0
                    ):
                        al_reason = "frigate_only_yolo_silent"
                    elif (
                        int(session_summary.get("post_fusion_persisted") or 0) == 0
                        and int(session_summary.get("frames_seen") or 0) > 0
                        and bool(session_summary.get("video_file_ok"))
                    ):
                        al_reason = "empty_fusion_with_video"
                    elif float(session_summary.get("yolo_blind_score") or 0.0) >= 0.5:
                        al_reason = "yolo_blind_suspected"
                    if al_reason:
                        repo.append_active_learning_buffer(
                            reason_code=al_reason,
                            camera_id=ctx.get("triggered_camera"),
                            severity="warning",
                            payload=al_payload,
                        )
            except Exception:
                logging.debug("active learning buffer append skipped", exc_info=True)
            try:
                breaches = session_summary.get("latency_budget_breaches") or []
                if isinstance(breaches, list) and breaches:
                    severity = "warning"
                    if any(
                        str((b or {}).get("severity") or "").lower() == "critical"
                        for b in breaches
                        if isinstance(b, dict)
                    ):
                        severity = "critical"
                    repo.append_detector_health_event(
                        event_type="runtime_latency_budget_breach",
                        severity=severity,
                        camera_id=ctx.get("triggered_camera"),
                        details={
                            "camera_slot": ctx.get("camera_slot"),
                            "trigger_source": trigger_source,
                            "breaches": breaches,
                        },
                    )
            except Exception:
                logging.debug("latency budget event append skipped", exc_info=True)
            try:
                watchdog_enabled = bool(app_config.get("detection.yolo_watchdog_enabled", True))
                min_fps = float(app_config.get("detection.yolo_watchdog_min_effective_fps") or 1.2)
                min_duration = float(app_config.get("detection.yolo_watchdog_min_duration_seconds") or 20.0)
                min_frames = int(app_config.get("detection.yolo_watchdog_min_frames") or 40)
                duration_now = float(session_summary.get("duration_s") or 0.0)
                yolo_ran_now = int(session_summary.get("yolo_frames_ran") or 0)
                yolo_raw_now = int(session_summary.get("yolo_raw_boxes_total") or 0)
                effective_fps = (yolo_ran_now / duration_now) if duration_now > 0.0 else 0.0
                watchdog_trip = (
                    watchdog_enabled
                    and not bool(yolo_blind_confirmed)
                    and duration_now >= max(1.0, min_duration)
                    and yolo_ran_now >= max(1, min_frames)
                    and yolo_raw_now == 0
                    and effective_fps < max(0.1, min_fps)
                )
                if watchdog_trip:
                    wd_details = {
                        "duration_s": round(duration_now, 3),
                        "yolo_frames_ran": yolo_ran_now,
                        "yolo_raw_boxes_total": yolo_raw_now,
                        "effective_fps": round(effective_fps, 3),
                        "min_effective_fps": max(0.1, min_fps),
                    }
                    repo.append_detector_health_event(
                        event_type="yolo_watchdog_fps_low",
                        severity="warning",
                        camera_id=ctx.get("triggered_camera"),
                        details=wd_details,
                    )
                    diag = collect_root_cause_snapshot(mqtt_aggregator=mqtt_aggregator)
                    dump_refs = write_root_cause_dump(diag, reason="yolo_watchdog_fps_low")
                    diag["dump_refs"] = dump_refs
                    action, action_details = _run_self_heal_escalation(
                        repo=repo,
                        app_config_obj=app_config,
                        api=api,
                        frame_processor=frame_processor,
                        mqtt_aggregator=mqtt_aggregator,
                        camera_id=ctx.get("triggered_camera"),
                        diagnostics=diag,
                    )
                    if action:
                        logging.warning("yolo_watchdog action=%s details=%s", action, action_details)
            except Exception:
                logging.debug("yolo watchdog probe skipped", exc_info=True)
            if bool(yolo_blind_confirmed):
                repo.append_detector_health_event(
                    event_type="yolo_blind_confirmed",
                    severity="warning",
                    camera_id=ctx.get("triggered_camera"),
                    details={
                        "yolo_frames_ran": session_summary["yolo_frames_ran"],
                        "yolo_raw_boxes_total": session_summary["yolo_raw_boxes_total"],
                        "session_extended_by_frigate_only": session_summary["session_extended_by_frigate_only"],
                        "mqtt_events_in_window": session_summary["mqtt_events_in_window"],
                        "blind_score": session_summary["yolo_blind_score"],
                    },
                )
                diag = collect_root_cause_snapshot(mqtt_aggregator=mqtt_aggregator)
                dump_refs = write_root_cause_dump(diag, reason="yolo_blind_confirmed")
                diag["dump_refs"] = dump_refs
                action, action_details = _run_self_heal_escalation(
                    repo=repo,
                    app_config_obj=app_config,
                    api=api,
                    frame_processor=frame_processor,
                    mqtt_aggregator=mqtt_aggregator,
                    camera_id=ctx.get("triggered_camera"),
                    diagnostics=diag,
                )
                if action:
                    logging.warning("self-heal action=%s details=%s", action, action_details)
            if bool(blind_recovered):
                repo.append_detector_health_event(
                    event_type="yolo_blind_recovered",
                    severity="info",
                    camera_id=ctx.get("triggered_camera"),
                    details={
                        "yolo_frames_ran": session_summary["yolo_frames_ran"],
                        "yolo_raw_boxes_total": session_summary["yolo_raw_boxes_total"],
                    },
                )
            if bool(app_config.get("processor.runtime_metrics_maintenance_async", True)):

                def _deferred_maintenance() -> None:
                    try:
                        maint_repo = SessionStateRepository()
                        res = maint_repo.run_maintenance_if_due(app_config_obj=app_config)
                        if res:
                            maint_repo.append_detector_health_event(
                                event_type="runtime_metrics_maintenance",
                                severity="info",
                                camera_id=ctx.get("triggered_camera"),
                                details=res,
                            )
                    except Exception:
                        logging.debug(
                            "deferred runtime metrics maintenance skipped",
                            exc_info=True,
                        )

                threading.Thread(
                    target=_deferred_maintenance,
                    daemon=True,
                    name="birdlense-runtime-metrics-maintenance",
                ).start()
            else:
                maintenance_res = repo.run_maintenance_if_due(app_config_obj=app_config)
                if maintenance_res:
                    repo.append_detector_health_event(
                        event_type="runtime_metrics_maintenance",
                        severity="info",
                        camera_id=ctx.get("triggered_camera"),
                        details=maintenance_res,
                    )
        except Exception:
            logging.warning("recording_session_summary persist skipped", exc_info=True)
    except Exception:
        logging.warning("recording_session_summary skipped", exc_info=True)
