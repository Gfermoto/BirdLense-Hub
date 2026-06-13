"""Финал сессии записи: merge, API, MQTT, уведомления (tech debt #201)."""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from collections import Counter
from datetime import datetime
from typing import Any, Optional

from api import API
from app_config.app_config import app_config
from decision_trace_builder import build_decision_trace_payload
from detection_fusion import build_fused_video_detections, skip_frigate_ev_for_standalone
from notify_preview_encode import encode_notify_preview_base64
from processor_runtime_stats import inc_counter
from processor_support import get_data_dir
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
    frigate_salvage_allow_without_yolo,
    frigate_salvage_opted_in,
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
from processor_config_defaults import (
    YOLO_BLIND_MIN_FRAMES,
    YOLO_BLIND_MIN_FRIGATE_ONLY_FRAMES,
    config_int,
)
from session_state_repository import SessionStateRepository
from behavior_baseline_runtime import maybe_predict_video_behavior_bundle
from track_first_contract import (
    apply_track_first_persist_gate,
    count_ingestible_track_rows,
    has_ingestible_track_rows,
)
from detect_first import restore_detect_first_persist_rows
from persist_mode import binary_track_first_enabled


from recording_finalize_parts.overlay_helpers import (
    _rejected_reason_counts,
    _sanitize_persisted_overlay_frames,
    _valid_track_frames,
    _row_exempt_from_video_bbox_requirement,
)
from recording_finalize_parts.metrics import (
    _runtime_wall_latency_seconds,
    _resolve_session_latencies,
    _latency_budget_breaches,
    _blind_required_frames,
    _compute_blind_score,
    _blind_suspected_from_final_stats,
    _emit_frigate_hub_panic_if_needed,
    _run_self_heal_escalation,
    build_persist_substage_ms,
)
from recording_finalize_parts.salvage import (
    _build_weak_yolo_salvage_rows,
    _pick_frigate_evidence_for_salvage,
    _build_frigate_trigger_review_salvage_row,
    _best_yolo_anchor_rows,
)
from recording_finalize_parts.tracks_scales import _default_scales_evidence_snapshot, _tracks_for_finalize

# Пустые сессии без детекций — частое событие; не засоряем лог (раз в интервал — WARNING, иначе DEBUG).
_NO_DETECTIONS_WARN_INTERVAL_S = 120.0
_no_detections_warn_next_monotonic = 0.0


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
    session_tracks = _tracks_for_finalize(frame_processor, recording_context)
    yolo_tracks_count = len(session_tracks)
    session_camera_id = None
    if isinstance(recording_context, dict):
        session_camera_id = str(recording_context.get("triggered_camera") or "").strip() or None
    try:
        from finalize_classification import enrich_tracks_classifier_at_finalize, defer_classifier_to_finalize

        if defer_classifier_to_finalize(app_config):
            enrich_tracks_classifier_at_finalize(
                session_tracks,
                getattr(frame_processor, "strategy", None),
                app_config,
                video_path=video_output,
                camera_id=session_camera_id,
            )
    except ImportError:
        pass
    decisions = decision_maker.get_decisions(session_tracks)
    video_detections = [item for item in decisions if item.get("accepted", False)]
    rejected_decisions = [item for item in decisions if not item.get("accepted", False)]
    clf_review_n = sum(1 for item in decisions if bool(item.get("classifier_needs_review")))
    if clf_review_n:
        inc_counter("classifier_needs_review_total", clf_review_n)
    yolo_passed_count = len(video_detections)
    trigger_source = None
    if isinstance(recording_context, dict):
        trigger_source = str(recording_context.get("triggered_by") or "").strip().lower() or None
        if not session_camera_id:
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
            for tid, t in session_tracks.items():
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
        blind_min_frames = config_int(
            app_config,
            "detection.yolo_blind_min_frames",
            YOLO_BLIND_MIN_FRAMES,
        )
        blind_min_frigate = config_int(
            app_config,
            "detection.yolo_blind_min_frigate_only_frames",
            YOLO_BLIND_MIN_FRIGATE_ONLY_FRAMES,
        )
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
            if _row_exempt_from_video_bbox_requirement(row):
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
    try:
        from dual_stream_timeline import apply_playback_timeline_offset_to_detections

        video_detections = apply_playback_timeline_offset_to_detections(
            video_detections,
            runtime_cfg=app_config,
            camera_id=session_camera_id,
        )
    except ImportError:
        pass
    detect_first_restored = False
    try:
        session_duration_s = max(0.0, float((end_time - start_time).total_seconds()))
    except (TypeError, AttributeError):
        session_duration_s = 0.0
    if not linear_skip_legacy_fusion_safeguards(app_config):
        video_detections, detect_first_restored = restore_detect_first_persist_rows(
            video_detections,
            recording_context=recording_context if isinstance(recording_context, dict) else None,
            accepted_pre_fusion=accepted_pre_fusion,
            frame_processor_tracks=session_tracks,
            video_duration_s=session_duration_s,
        )
        if detect_first_restored:
            inc_counter("detect_first_persist_safeguard_total")
    try:
        from dense_track_persist import restore_dense_persist_frames

        video_detections, dense_restored = restore_dense_persist_frames(
            video_detections,
            session_tracks,
        )
        if dense_restored:
            inc_counter("dense_track_persist_restored_total", dense_restored)
    except ImportError:
        dense_restored = 0
    skip_weak_salvage = bool(rs_ctx.get("detect_first_confirmed")) and not detect_first_restored
    if (
        not video_detections
        and yolo_tracks_count > 0
        and bool(app_config.get("detection.yolo_weak_track_salvage_enabled", True))
        and not linear_skip_legacy_fusion_safeguards(app_config)
        and not skip_weak_salvage
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
            session_tracks,
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
    salvage_enabled = frigate_salvage_opted_in(app_config, camera_id=session_camera_id)
    salvage_allow_without_yolo = frigate_salvage_allow_without_yolo(app_config, camera_id=session_camera_id)
    if salvage_enabled and not salvage_allow_without_yolo and yolo_tracks_count <= 0:
        salvage_enabled = False
    if (
        not video_detections
        and salvage_enabled
        and not linear_skip_frigate_salvage_paths(app_config, camera_id=session_camera_id)
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
    try:
        from playback_geometry import enrich_detections_playback_geometry

        video_detections = enrich_detections_playback_geometry(video_detections, frame_processor)
    except ImportError:
        pass
    reid_enrich_duration_ms: float | None = None
    if video_detections:
        reid_enrich_started_ts = time.perf_counter()
        try:
            video_detections = enrich_runtime_reid_detections(
                video_detections,
                video_path=video_path_for_api,
            )
        except Exception as exc:
            from processor_exception_handling import reraise_if_io_critical

            reraise_if_io_critical(exc)
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
            track_count=len(session_tracks),
            mqtt_event_count=len(mqtt_events),
            now_monotonic=time.monotonic(),
            next_warn_monotonic=_no_detections_warn_next_monotonic,
            warn_interval_seconds=_NO_DETECTIONS_WARN_INTERVAL_S,
        )
    final_rejected_reason_counts = _rejected_reason_counts(rejected_decisions)
    if len(video_detections) == 0:
        log_no_detection_activity(
            api,
            track_count=len(session_tracks),
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
                camera_id=session_camera_id,
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
                if session_camera_id:
                    for row in video_detections:
                        if isinstance(row, dict) and not row.get("camera_id"):
                            row["camera_id"] = session_camera_id
                notify_unique_species(
                    api,
                    app_config,
                    video_detections=video_detections,
                    video_output=video_output,
                    video_id=video_id,
                    encode_func=lambda d, v: encode_notify_preview_base64(d, v, runtime_cfg=app_config),
                )
        except Exception as exc:
            from processor_exception_handling import reraise_if_io_critical

            reraise_if_io_critical(exc)
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
    elif len(video_detections) > 0 and video_id is None:
        inc_counter("recording_persist_orphan_rollback_total")
        remove_session_dir(output_path_physical, reason="persist_failed")
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
            "detect_first_safeguard_restored": int(detect_first_restored),
            "detection_acceptance_gap": bool(
                int(rs.get("yolo_raw_boxes_total") or 0) > 0 and int(rs.get("yolo_accepted_boxes_total") or 0) == 0
            ),
            "quality_reject_counts": dict(rs.get("quality_reject_counts") or {}),
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
            "persist_substage_ms": build_persist_substage_ms(
                scales_duration_ms=scales_duration_ms,
                behavior_duration_ms=behavior_duration_ms,
                create_video_duration_ms=create_video_duration_ms,
                create_video_ingest_timing_ms=create_video_ingest_timing_ms,
                dataset_crops_duration_ms=dataset_crops_duration_ms,
                reid_enrich_duration_ms=reid_enrich_duration_ms,
            ),
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
