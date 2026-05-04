"""Финал сессии записи: merge, spectrogram, API, MQTT, уведомления (tech debt #201)."""

from __future__ import annotations

import logging
import os
import time
from collections import Counter
from datetime import datetime
from typing import Any, Optional

from api import API
from app_config.app_config import app_config
from decision_trace_builder import build_decision_trace_payload
from detection_fusion import build_fused_video_detections
from notify_preview_encode import encode_notify_preview_base64
from processor_runtime_stats import inc_counter
from processor_support import get_data_dir
from recording_cleanup_policy import should_keep_empty_recording
from recording_dataset_crops import maybe_save_dataset_crops
from recording_decision_trace_log import write_decision_trace_activity
from recording_file_gate import _is_playable_video_file
from recording_ingest_gate import log_missing_video_gate
from recording_mqtt_window import get_recording_mqtt_events
from recording_no_detection_log import log_no_detections_after_merge
from recording_notify_dispatch import notify_unique_species
from recording_post_fusion_rejections import collect_post_fusion_rejections
from recording_scales_evidence import estimate_recording_scales_delta
from recording_session_cleanup import remove_session_dir
from recording_video_response import response_video_id
from recordings_remote_mirror import schedule_recordings_session_mirror
from recording_spectrogram import maybe_generate_recording_spectrogram
from reid_runtime import enrich_runtime_reid_detections
from spectrogram import generate_spectrogram

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
    merge_window = int(app_config.get("detection.merge_window_seconds") or 5)
    yolo_tracks_count = len(frame_processor.tracks)
    decisions = decision_maker.get_decisions(frame_processor.tracks)
    video_detections = [item for item in decisions if item.get("accepted", False)]
    rejected_decisions = [item for item in decisions if not item.get("accepted", False)]
    clf_review_n = sum(1 for item in decisions if bool(item.get("classifier_needs_review")))
    if clf_review_n:
        inc_counter("classifier_needs_review_total", clf_review_n)
    yolo_passed_count = len(video_detections)
    mqtt_events = get_recording_mqtt_events(
        mqtt_aggregator,
        motion_detector,
        start_time=start_time,
        end_time=end_time,
        merge_window=merge_window,
        yolo_tracks_count=yolo_tracks_count,
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
    video_detections = build_fused_video_detections(
        video_detections,
        mqtt_events,
        start_time=start_time,
        end_time=end_time,
        app_config=app_config,
    )
    rejected_decisions.extend(
        collect_post_fusion_rejections(
            app_config,
            accepted_pre_fusion=accepted_pre_fusion,
            persisted_detections=video_detections,
        )
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
        resp = api.create_video(
            video_detections,
            audio_detections,
            start_time,
            end_time,
            video_path_for_api,
            spectrogram_path,
            scales_weight_delta_kg=scales_delta_kg,
        )
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
            remove_session_dir(output_path_physical, reason="empty")
    # Фоновая копия на SFTP/NAS (#350): не блокирует finalize; только если каталог ещё на диске.
    try:
        if os.path.isdir(output_path_physical):
            schedule_recordings_session_mirror(output_path_physical)
    except Exception as e:
        logging.debug("recordings mirror schedule skipped: %s", e)
