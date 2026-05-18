"""Финал сессии записи: merge, spectrogram, API, MQTT, уведомления (tech debt #201)."""

from __future__ import annotations

import json
import logging
import os
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
from recording_scales_evidence import estimate_recording_scales_delta
from recording_session_cleanup import remove_session_dir
from recording_video_response import response_video_id
from recordings_remote_mirror import schedule_recordings_session_mirror
from recording_spectrogram import maybe_generate_recording_spectrogram
from reid_runtime import enrich_runtime_reid_detections
from session_state_repository import SessionStateRepository
from spectrogram import generate_spectrogram
from behavior_baseline_runtime import maybe_predict_video_behavior

# Пустые сессии без детекций — частое событие; не засоряем лог (раз в интервал — WARNING, иначе DEBUG).
_NO_DETECTIONS_WARN_INTERVAL_S = 120.0
_no_detections_warn_next_monotonic = 0.0


def _build_weak_yolo_salvage_row(
    tracks: dict[str, Any] | dict[int, Any],
    *,
    min_confidence: float = 0.10,
) -> dict[str, Any] | None:
    best_track = None
    best_score = -1.0
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
        if score > best_score:
            best_score = score
            best_track = (track_id, track, max_det_conf)
    if not best_track:
        return None
    track_id, track, max_det_conf = best_track
    detector_events = list(track.get("detector_events") or [])
    detector_label = "Bird"
    if detector_events:
        detector_label = str(detector_events[-1].get("label") or detector_label).strip() or "Bird"
    species_name = detector_label if detector_label in {"Bird", "Rodent"} else "Bird"
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


def _best_yolo_anchor_row(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    yolo_rows = [
        row for row in (rows or []) if str((row or {}).get("detection_provider") or "").strip().lower() == "yolo"
    ]
    if not yolo_rows:
        return None
    return max(
        yolo_rows,
        key=lambda row: (
            float(row.get("confidence") or 0.0),
            float(row.get("best_frame_score") or 0.0),
            len(row.get("frames") or []),
        ),
    )


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
    merge_window = int(app_config.get("detection.merge_window_seconds") or 5)
    yolo_tracks_count = len(frame_processor.tracks)
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
            rejected_summary = Counter(
                str(item.get("reject_reason_code") or item.get("decision_reason") or "rejected_unknown")
                for item in rejected_decisions
            )
            logging.info(
                "DecisionMaker rejected tracks: %s",
                dict(sorted(rejected_summary.items())),
            )
    elif mqtt_events:
        logging.warning(
            "ByteTrack: 0 YOLO tracks but %s MQTT events. "
            "Without YOLO, Frigate MQTT does not become a final detection unless "
            "detection.frigate_standalone_when_no_yolo is enabled (see detection_fusion).",
            len(mqtt_events),
        )

    audio_detections: list = []
    spectrogram_path = maybe_generate_recording_spectrogram(
        app_config,
        mqtt_events=mqtt_events,
        video_output=video_output,
        output_path_physical=output_path_physical,
        output_path_logical=output_path_logical,
        generate_func=generate_spectrogram,
    )

    accepted_pre_fusion = list(video_detections)
    triggered_camera = None
    if trigger_source == "frigate" and isinstance(recording_context, dict):
        triggered_camera = session_camera_id
    rs_ctx = {}
    if isinstance(recording_context, dict) and isinstance(recording_context.get("runtime_signals"), dict):
        rs_ctx = dict(recording_context.get("runtime_signals") or {})
    yolo_blind_confirmed = False
    blind_recovered = False
    try:
        yolo_ran_now = int(rs_ctx.get("yolo_frames_ran") or 0)
        yolo_raw_now = int(rs_ctx.get("yolo_raw_boxes_total") or 0)
        frigate_only_now = int(rs_ctx.get("session_extended_by_frigate_only") or 0)
        blind_min_sessions = int(app_config.get("detection.yolo_blind_required_consecutive_sessions") or 1)
        blind_min_frames = int(app_config.get("detection.yolo_blind_min_frames") or 180)
        blind_min_frigate = int(app_config.get("detection.yolo_blind_min_frigate_only_frames") or 120)
        blind_min_duration_s = float(app_config.get("detection.yolo_blind_min_duration_seconds") or 30.0)
        current_duration_s = max(0.0, float((end_time - start_time).total_seconds()))
        blind_now = (
            yolo_ran_now >= max(1, blind_min_frames)
            and yolo_raw_now == 0
            and frigate_only_now >= max(1, blind_min_frigate)
            and current_duration_s >= max(0.0, blind_min_duration_s)
        )
        repo = SessionStateRepository()
        blind_recent = repo.is_blind_confirmed(
            camera_id=session_camera_id,
            min_recent_sessions=max(1, blind_min_sessions),
            min_yolo_frames=max(1, blind_min_frames),
            min_frigate_only_frames=max(1, blind_min_frigate),
            min_duration_seconds=max(0.0, blind_min_duration_s),
        )
        yolo_blind_confirmed = bool(blind_now and blind_recent)
        if yolo_raw_now > 0:
            recent = repo.recent_blind_sessions(camera_id=session_camera_id, limit=1)
            if recent and int(recent[0]["yolo_blind_confirmed"] or 0) == 1:
                blind_recovered = True
    except Exception:
        logging.debug("finalize: blind-state probe failed", exc_info=True)
    video_detections = build_fused_video_detections(
        video_detections,
        mqtt_events,
        start_time=start_time,
        end_time=end_time,
        app_config=app_config,
        triggered_camera=triggered_camera,
        yolo_blind_confirmed=yolo_blind_confirmed,
    )
    rejected_decisions.extend(
        collect_post_fusion_rejections(
            app_config,
            accepted_pre_fusion=accepted_pre_fusion,
            persisted_detections=video_detections,
        )
    )
    yolo_core_anchor_enabled = bool(app_config.get("detection.yolo_core_anchor_enabled", True))
    if yolo_core_anchor_enabled:
        pre_fusion_yolo_anchor = _best_yolo_anchor_row(accepted_pre_fusion)
        has_fused_yolo = any(
            str((row or {}).get("detection_provider") or "").strip().lower() == "yolo" for row in video_detections
        )
        # Keep YOLO as pipeline core, but do not disable fallback: we only restore
        # a single anchor row when YOLO had accepted rows and fusion dropped them all.
        if yolo_tracks_count > 0 and pre_fusion_yolo_anchor and not has_fused_yolo:
            anchor_row = dict(pre_fusion_yolo_anchor)
            anchor_row["yolo_core_anchor_forced"] = True
            if not str(anchor_row.get("decision_reason") or "").strip():
                anchor_row["decision_reason"] = "yolo_core_anchor_forced"
            if not str(anchor_row.get("decision_kind") or "").strip():
                anchor_row["decision_kind"] = "accepted_species"
            video_detections.append(anchor_row)
            logging.warning(
                "Finalize safeguard: restored one YOLO anchor row after fusion removed all YOLO rows "
                "(tracks=%s, pre_fusion_accepted=%s).",
                yolo_tracks_count,
                len(accepted_pre_fusion),
            )
    require_frames_for_video_rows = bool(app_config.get("detection.persist_video_detections_require_frames", True))
    if require_frames_for_video_rows and video_detections:
        has_yolo_rows_with_frames_in_final = any(
            str((row or {}).get("detection_provider") or "").strip().lower() == "yolo"
            and bool((row or {}).get("frames"))
            for row in video_detections
        )
        had_yolo_rows_with_frames_pre_fusion = any(
            str((row or {}).get("detection_provider") or "").strip().lower() == "yolo"
            and bool((row or {}).get("frames"))
            for row in accepted_pre_fusion
        )
        has_yolo_rows_with_frames = has_yolo_rows_with_frames_in_final or had_yolo_rows_with_frames_pre_fusion
        kept_rows: list[dict[str, Any]] = []
        dropped_no_frames = 0
        kept_no_frames_frigate = 0
        dropped_no_frames_frigate_when_yolo = 0
        for row in video_detections:
            row_source = str((row or {}).get("source") or "").strip().lower()
            row_provider = str((row or {}).get("detection_provider") or "").strip().lower()
            row_kind = str((row or {}).get("decision_kind") or "").strip().lower()
            keep_without_frames = (
                bool((row or {}).get("frigate_standalone"))
                or row_kind
                in {
                    "frigate_standalone",
                    "frigate_standalone_excluded",
                }
            ) and not has_yolo_rows_with_frames
            if row_source == "video" and not row.get("frames") and not keep_without_frames:
                if row_provider == "frigate" and row_kind in {"frigate_standalone", "frigate_standalone_excluded"}:
                    dropped_no_frames_frigate_when_yolo += 1
                dropped_no_frames += 1
                continue
            if row_source == "video" and not row.get("frames") and keep_without_frames:
                kept_no_frames_frigate += 1
            kept_rows.append(row)
        if dropped_no_frames:
            logging.warning(
                "Finalize safeguard: dropped %s video row(s) without frames "
                "(detection.persist_video_detections_require_frames=true).",
                dropped_no_frames,
            )
        if kept_no_frames_frigate:
            logging.info(
                "Finalize safeguard: kept %s Frigate standalone video row(s) without frames "
                "(event persistence fallback).",
                kept_no_frames_frigate,
            )
        if dropped_no_frames_frigate_when_yolo:
            logging.info(
                "Finalize safeguard: dropped %s Frigate standalone row(s) without frames "
                "because YOLO rows with frames are present (YOLO-priority).",
                dropped_no_frames_frigate_when_yolo,
            )
        video_detections = kept_rows
    if (
        not video_detections
        and yolo_tracks_count > 0
        and bool(app_config.get("detection.yolo_weak_track_salvage_enabled", True))
    ):
        try:
            salvage_min_conf = float(app_config.get("detection.yolo_weak_track_salvage_min_confidence") or 0.10)
        except (TypeError, ValueError):
            salvage_min_conf = 0.10
        salvage = _build_weak_yolo_salvage_row(
            frame_processor.tracks,
            min_confidence=salvage_min_conf,
        )
        if salvage is not None:
            video_detections = [salvage]
            logging.warning(
                "Finalize safeguard: recovered weak YOLO track as review-only (track_id=%s, conf=%.3f).",
                salvage.get("track_id"),
                float(salvage.get("confidence") or 0.0),
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
    if video_detections:
        try:
            video_detections = enrich_runtime_reid_detections(
                video_detections,
                video_path=video_path_for_api,
            )
        except Exception as exc:
            inc_counter("reid_runtime_enrich_fail_total")
            logging.warning("Runtime ReID enrich failed; keep fused detections: %s", exc)

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
    scales_evidence = decision_trace["scales_evidence"]
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
    if len(video_detections) == 0:
        log_no_detection_activity(
            api,
            track_count=len(frame_processor.tracks),
            mqtt_event_count=len(mqtt_events),
            rejected_count=len(rejected_decisions),
            video_path_for_api=video_path_for_api,
            trigger_source=trigger_source,
            triggered_camera=session_camera_id,
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

    if len(video_detections) > 0 and video_file_ok:
        scales_delta_kg, scales_evidence_update = estimate_recording_scales_delta(
            app_config,
            video_detections,
            scales_topic_arg=scales_topic_arg,
            data_dir=data_dir,
            start_time=start_time,
            end_time=end_time,
        )
        scales_evidence.update(scales_evidence_update)
        try:
            duration_behavior_s = max(0.0, (end_time - start_time).total_seconds())
        except Exception:
            duration_behavior_s = 0.0
        proc_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        bl, bc = maybe_predict_video_behavior(
            app_config,
            video_detections,
            duration_s=duration_behavior_s,
            processor_cwd=proc_root,
        )
        br_cfg = app_config.get("processor.behavior_recognition") or {}
        if not isinstance(br_cfg, dict):
            br_cfg = {}
        store_min = float(br_cfg.get("confidence_store_min") or 0.2)
        rev_thr = float(br_cfg.get("confidence_review_threshold") or 0.45)
        behavior_label_kw = None
        behavior_conf_kw = None
        if bl and float(bc) >= store_min:
            behavior_label_kw = bl
            behavior_conf_kw = float(bc)
            if float(bc) < rev_thr and video_detections:
                d0 = video_detections[0]
                if isinstance(d0, dict) and not (d0.get("review_reason") or "").strip():
                    d0["review_reason"] = "behavior_uncertainty"
                    d0["classifier_needs_review"] = True
        resp = api.create_video(
            video_detections,
            audio_detections,
            start_time,
            end_time,
            video_path_for_api,
            spectrogram_path,
            scales_weight_delta_kg=scales_delta_kg,
            behavior_label=behavior_label_kw,
            behavior_confidence=behavior_conf_kw,
        )
        inc_counter("recording_persisted_total", len(video_detections))
        video_id = response_video_id(resp)
        if video_id is not None:
            try:
                decision_trace["video_id"] = int(video_id)
            except (TypeError, ValueError):
                decision_trace["video_id"] = video_id
        maybe_save_dataset_crops(
            app_config,
            video_id=video_id,
            video_detections=video_detections,
            data_dir=get_data_dir(),
            video_output=video_output,
        )
        notify_unique_species(
            api,
            app_config,
            video_detections=video_detections,
            video_output=video_output,
            video_id=video_id,
            encode_func=encode_notify_preview_base64,
        )
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
        session_summary = {
            "event": "recording_session_summary",
            "duration_s": round(duration_s, 3) if duration_s is not None else None,
            "triggered_camera": ctx.get("triggered_camera"),
            "frames_seen": int(rs.get("frames_seen") or 0),
            "yolo_frames_ran": int(rs.get("yolo_frames_ran") or 0),
            "yolo_frames_with_tracks": int(rs.get("yolo_frames_with_tracks") or 0),
            "yolo_frames_with_raw_boxes": int(rs.get("yolo_frames_with_raw_boxes") or 0),
            "yolo_raw_boxes_total": int(rs.get("yolo_raw_boxes_total") or 0),
            "yolo_accepted_boxes_total": int(rs.get("yolo_accepted_boxes_total") or 0),
            "low_light_blocked_frames": int(rs.get("low_light_blocked_frames") or 0),
            "session_extended_by_frigate_only": int(rs.get("session_extended_by_frigate_only") or 0),
            "bytetrack_rows": yolo_tracks_count,
            "post_fusion_persisted": len(video_detections),
            "rejected_decision_rows": len(rejected_decisions),
            "mqtt_events_in_window": len(mqtt_events),
            "video_file_ok": bool(video_file_ok),
            "runtime_profile": rs.get("runtime_profile"),
            "yolo_blind_confirmed": bool(yolo_blind_confirmed),
        }
        logging.info(
            "recording_session_summary %s",
            json.dumps(session_summary, default=str, separators=(",", ":")),
        )
        try:
            repo = SessionStateRepository()
            repo.save_session_runtime(session_summary)
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
                    },
                )
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
        except Exception:
            logging.debug("recording_session_summary persist skipped", exc_info=True)
    except Exception:
        logging.debug("recording_session_summary skipped", exc_info=True)
