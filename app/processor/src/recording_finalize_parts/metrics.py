from __future__ import annotations

import logging
import json
from pathlib import Path

from api import API
from processor_diagnostics import collect_root_cause_snapshot, write_root_cause_dump
from processor_support import get_data_dir
from datetime import datetime, timezone
from typing import Any

from app_config.app_config import app_config
from processor_runtime_stats import inc_counter
from processor_support import restart_flag_path
from session_state_repository import SessionStateRepository
from recording_finalize_parts.overlay_helpers import _is_valid_track_bbox, _safe_float

PERSIST_SUBSTAGE_SUMMARY_KEYS: tuple[str, ...] = (
    "scales_duration_ms",
    "create_video_duration_ms",
    "dataset_crops_duration_ms",
    "reid_enrich_duration_ms",
    "welfare_enrich_duration_ms",
)

CREATE_VIDEO_INGEST_SUBSTAGE_KEYS: tuple[str, ...] = (
    "visit_processor_ms",
    "commit_ms",
    "weather_ms",
)


def build_persist_substage_ms(
    *,
    scales_duration_ms: float | None,
    create_video_duration_ms: float | None,
    create_video_ingest_timing_ms: dict[str, float] | None,
    dataset_crops_duration_ms: float | None,
    reid_enrich_duration_ms: float | None = None,
    welfare_enrich_duration_ms: float | None = None,
) -> dict[str, Any]:
    """Grouped persist-tail timers for session_summary and readiness aggregation."""
    substage: dict[str, Any] = {
        "scales_ms": scales_duration_ms,
        "create_video_ms": create_video_duration_ms,
        "dataset_crops_ms": dataset_crops_duration_ms,
        "reid_enrich_ms": reid_enrich_duration_ms,
        "welfare_enrich_ms": welfare_enrich_duration_ms,
    }
    if isinstance(create_video_ingest_timing_ms, dict) and create_video_ingest_timing_ms:
        substage["create_video_ingest_ms"] = dict(create_video_ingest_timing_ms)
    return substage


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
