"""Shared ``decision_trace`` payload builder."""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any

from app_config.trigger_config import (
    format_motion_source_summary,
    format_trigger_display_line,
    get_active_trigger_names,
)
from processor_provenance import build_pipeline_fingerprint
from runtime_contract import apply_runtime_contract_rows, summarize_runtime_contract

_DECISION_TRACE_FIELDS = (
    "track_id",
    "accepted",
    "outcome_bucket",
    "species_name",
    "confidence",
    "arbitration_reason",
    "decision_reason_before_arbitration",
    "decision_reason",
    "decision_kind",
    "trust_band",
    "reject_reason_code",
    "evidence_state",
    "detector_label",
    "detector_confidence",
    "detector_event_count",
    "classifier_threshold",
    "classifier_species_name",
    "classifier_confidence",
    "classifier_entropy",
    "classifier_top1_top2_margin",
    "classifier_needs_review",
    "classifier_event_count",
    "classifier_vote_share",
    "best_frame_score",
    "key_frame_count",
    "audio_evidence",
    "audio_support_count",
    "audio_support_species",
    "audio_conflict_species",
    "audio_conflict_score",
    "_birdnet_prior",
    "_birdnet_timestamp_parse_failed",
    "_multi_camera_count",
    "_multi_camera_support",
    "_fusion_used",
    "_fusion_score",
    "_fusion_scorer_status",
    "_fusion_model_path",
    "audio_top_species",
    "audio_top_score",
    "audio_top_support_count",
    "frigate_standalone",
    "frigate_merge_suppressed",
    "primary_provider",
    "provider_lineage",
    "primary_signal",
    "threshold_path",
    "fallback_used",
    "fallback_reason",
    "yolo_track_present",
    "review_reason",
    "reid_model",
    "reid_similarity",
    "individual_nickname",
    "welfare_model",
    "welfare_distance",
    "welfare_needs_review",
)
_DECISION_TRACE_LIMIT = 40


def _compact_runtime_signals(
    runtime_signals: dict[str, Any] | None,
    *,
    max_items: int = 24,
) -> dict[str, Any]:
    """Keep only compact scalar runtime signals for trace payload."""
    if not isinstance(runtime_signals, dict):
        return {}
    out: dict[str, Any] = {}
    for key in sorted(runtime_signals.keys()):
        if len(out) >= max(1, int(max_items)):
            break
        value = runtime_signals.get(key)
        if isinstance(value, (bool, int, float)):
            out[str(key)] = value
            continue
        if isinstance(value, str) and len(value) <= 64:
            out[str(key)] = value
    return out


def _policy_snapshot(app_config) -> dict[str, Any]:
    def _get(key: str, default: Any) -> Any:
        try:
            return app_config.get(key, default)
        except Exception:
            return default

    def _flt(key: str, default: float) -> float:
        try:
            return float(_get(key, default))
        except (TypeError, ValueError):
            return float(default)

    def _int(key: str, default: int) -> int:
        try:
            return int(_get(key, default))
        except (TypeError, ValueError):
            return int(default)

    return {
        "min_track_duration": _flt("processor.min_track_duration", 1.0),
        "min_confidence_to_process": _flt("processor.min_confidence_to_process", 0.3),
        "min_confidence_to_store": _flt("detection.min_confidence_to_store", 0.05),
        "classifier_fallback_bird": bool(_get("processor.classifier_fallback_bird", True)),
        "generic_bird_min_detector_conf": _flt("processor.generic_bird_min_detector_conf", 0.45),
        "generic_bird_min_frames": _int("processor.generic_bird_min_frames", 3),
        "generic_bird_min_area_frac": _flt("processor.generic_bird_min_area_frac", 0.01),
        "generic_bird_min_best_frame_score": _flt("processor.generic_bird_min_best_frame_score", 6.5),
        # Runtime backend snapshot for GPU/ONNX observability.
        "inference_backend": str(_get("processor.inference_backend", "auto") or "auto"),
        "classifier_inference_backend": str(_get("processor.classifier_inference_backend", "auto") or "auto"),
        "inference_device": str(_get("processor.inference_device", "auto") or "auto"),
        "video_encoding": str(_get("video.encoding", "jetson") or "jetson"),
        "video_capture_backend": str(_get("video.capture_backend", "auto") or "auto"),
        "reid_runtime_enabled": bool(_get("processor.reid.runtime_enabled", True)),
        "reid_device": str(_get("processor.reid.device", "auto") or "auto"),
        "welfare_runtime_enabled": bool(_get("processor.welfare.runtime_enabled", True)),
        "welfare_device": str(_get("processor.welfare.device", "auto") or "auto"),
    }


def decision_trace_row(item: dict, *, persisted_to_clip: bool) -> dict:
    """Build a compact serialized row for one persisted/rejected track."""
    row = {}
    for key in _DECISION_TRACE_FIELDS:
        if key in item:
            row[key] = item.get(key)
    row["accepted"] = bool(item.get("accepted", False))
    row["persisted_to_clip"] = bool(persisted_to_clip)
    row["confidence"] = float(item.get("confidence") or 0.0)
    row["best_frame_score"] = float(item.get("best_frame_score") or 0.0)
    row["key_frame_count"] = int(item.get("key_frame_count") or 0)
    row["classifier_vote_share"] = float(item.get("classifier_vote_share") or 0.0)
    row["detector_event_count"] = int(item.get("detector_event_count") or 0)
    row["classifier_event_count"] = int(item.get("classifier_event_count") or 0)
    row["_birdnet_prior"] = float(item.get("_birdnet_prior") or 0.0)
    row["_multi_camera_count"] = int(item.get("_multi_camera_count") or 0)
    row["_multi_camera_support"] = bool(item.get("_multi_camera_support") or False)
    row["fallback_used"] = bool(item.get("fallback_used") or False)
    row["yolo_track_present"] = bool(item.get("yolo_track_present") or False)
    if item.get("provider_lineage") is not None:
        row["provider_lineage"] = list(item.get("provider_lineage") or [])
    if item.get("audio_evidence") is None:
        row["audio_evidence"] = "none"
    return row


def clip_trace_rows(
    rows: list[dict],
    limit: int = _DECISION_TRACE_LIMIT,
) -> tuple[list[dict], int]:
    """Trim very long track lists while preserving leading context."""
    rows = list(rows or [])
    if len(rows) <= limit:
        return rows, 0
    return rows[:limit], len(rows) - limit


def build_decision_trace_payload(
    *,
    app_config,
    start_time: datetime,
    end_time: datetime,
    video_path: str,
    persisted_tracks: list[dict] | None,
    rejected_tracks: list[dict] | None,
    video_id: int | None = None,
    recording_context: dict[str, Any] | None = None,
    scales_topic_arg: str | None = None,
    contract_version: str = "2026-04-yolo-first-v1",
) -> dict[str, Any]:
    """Build the shared JSON payload stored in ``ActivityLog``."""
    persisted_tracks = apply_runtime_contract_rows(persisted_tracks or [])
    rejected_tracks = apply_runtime_contract_rows(rejected_tracks or [])
    clip_duration_seconds = max(0.0, (end_time - start_time).total_seconds())
    review_only_count = sum(1 for item in persisted_tracks if str(item.get("outcome_bucket") or "") == "review_only")

    active_at_trace = recording_context.get("active_triggers") if recording_context else None
    if not isinstance(active_at_trace, list):
        mqtt_broker = (os.environ.get("MQTT_BROKER") or app_config.get("mqtt.broker") or "").strip() or None
        active_at_trace = list(
            get_active_trigger_names(app_config, mqtt_broker=mqtt_broker),
        )
    trigger_display = str((recording_context or {}).get("trigger_display") or "").strip()
    if not trigger_display:
        trigger_display = format_trigger_display_line(active_at_trace)
    motion_source = str((recording_context or {}).get("motion_source") or "").strip()
    if not motion_source:
        motion_source = format_motion_source_summary(active_at_trace)
    video_source = (recording_context or {}).get("video_source")
    if video_source is None:
        video_source = app_config.get("video.source")

    trace: dict[str, Any] = {
        "decision_contract_version": contract_version,
        "start_time": start_time.isoformat(),
        "end_time": end_time.isoformat(),
        "video_path": video_path,
        "merge_window_seconds": int(
            app_config.get("detection.merge_window_seconds") or 5,
        ),
        "persisted_tracks": [],
        "rejected_tracks": [],
        "pipeline_fingerprint": build_pipeline_fingerprint(app_config),
        "recording_context": {
            "motion_source": motion_source,
            "active_triggers": list(active_at_trace),
            "trigger_display": trigger_display,
            "triggered_by": (recording_context or {}).get("triggered_by"),
            "video_source": video_source,
            "triggered_camera": (recording_context or {}).get("triggered_camera"),
            "frigate_activity_hold_seconds": (recording_context or {}).get("frigate_activity_hold_seconds"),
            "pipeline_policy": dict((recording_context or {}).get("pipeline_policy") or {}),
            "min_seconds_between_recordings": float(
                app_config.get("processor.min_seconds_between_recordings") or 0,
            ),
            "clip_duration_seconds": round(clip_duration_seconds, 3),
            "runtime_signals": _compact_runtime_signals(
                (recording_context or {}).get("runtime_signals"),
            ),
            "regen_profile": (recording_context or {}).get("regen_profile"),
            "policy_snapshot": _policy_snapshot(app_config),
        },
        "scales_evidence": {
            "enabled": bool(app_config.get("integrations.scales.enabled")),
            "weight_estimate_enabled": bool(
                app_config.get(
                    "integrations.scales.weight_estimate_enabled",
                    True,
                ),
            ),
            "topic_present": bool(scales_topic_arg),
            "estimated_delta_kg": None,
            "sample_count": 0,
            "min_delta_kg": None,
            "require_consecutive_spike": bool(
                app_config.get(
                    "integrations.scales.estimate_require_consecutive_spike",
                    True,
                ),
            ),
        },
        "outcome_summary": {
            "persisted_track_count": len(persisted_tracks),
            "review_only_count": review_only_count,
            "rejected_track_count": len(rejected_tracks),
        },
        "runtime_contract_summary": summarize_runtime_contract(
            persisted_tracks,
            rejected_tracks,
        ),
    }

    raw_min_delta = app_config.get("integrations.scales.min_delta_kg_for_estimate")
    if raw_min_delta is not None:
        try:
            trace["scales_evidence"]["min_delta_kg"] = float(raw_min_delta)
        except (TypeError, ValueError):
            trace["scales_evidence"]["min_delta_kg"] = None

    accepted_trace_rows = [decision_trace_row(item, persisted_to_clip=True) for item in persisted_tracks]
    rejected_trace_rows = [decision_trace_row(item, persisted_to_clip=False) for item in rejected_tracks]
    accepted_trace_rows, accepted_trimmed = clip_trace_rows(
        accepted_trace_rows,
    )
    rejected_trace_rows, rejected_trimmed = clip_trace_rows(
        rejected_trace_rows,
    )
    trace["persisted_tracks"] = accepted_trace_rows
    trace["accepted_tracks"] = trace["persisted_tracks"]
    trace["rejected_tracks"] = rejected_trace_rows
    trace["persisted_track_count"] = len(persisted_tracks)
    trace["accepted_track_count"] = len(persisted_tracks)
    trace["rejected_track_count"] = len(rejected_tracks)
    if accepted_trimmed:
        trace["persisted_tracks_truncated"] = accepted_trimmed
        trace["accepted_tracks_truncated"] = accepted_trimmed
    if rejected_trimmed:
        trace["rejected_tracks_truncated"] = rejected_trimmed
    if video_id is not None:
        trace["video_id"] = int(video_id)
    return trace
