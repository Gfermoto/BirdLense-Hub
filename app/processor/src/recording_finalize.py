"""Финал сессии записи: merge, spectrogram, API, MQTT, уведомления (tech debt #201)."""

from __future__ import annotations

import logging
import os
import shutil
import time
from collections import Counter
from datetime import datetime
from typing import Any, Optional

from api import API
from app_config.app_config import app_config
from dataset_saver import save_dataset_crops
from decision_trace_builder import build_decision_trace_payload
from decision_outcome import compute_outcome_bucket
from detection_fusion import build_fused_video_detections
from notify_preview_encode import encode_notify_preview_base64
from processor_support import get_data_dir
from spectrogram import generate_spectrogram

# Пустые сессии без детекций — частое событие; не засоряем лог (раз в интервал — WARNING, иначе DEBUG).
_NO_DETECTIONS_WARN_INTERVAL_S = 120.0
_no_detections_warn_next_monotonic = 0.0


def _is_playable_video_file(path: str) -> bool:
    if not path or not os.path.isfile(path):
        return False
    try:
        if os.path.getsize(path) <= 1024:
            return False
        import cv2

        cap = cv2.VideoCapture(path)
        try:
            if not cap.isOpened():
                return False
            ok, _frame = cap.read()
            return bool(ok)
        finally:
            cap.release()
    except Exception:
        return False


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
    yolo_passed_count = len(video_detections)
    mqtt_events = []
    if mqtt_aggregator:
        lookback = merge_window
        if yolo_tracks_count == 0:
            triggered_cam = getattr(motion_detector, "get_triggered_camera", lambda: None)()
            if triggered_cam:
                lookback = max(merge_window, 60)
                logging.info(
                    "Frigate trigger, 0 YOLO: extended MQTT lookback to %ds",
                    lookback,
                )
        mqtt_events = mqtt_aggregator.get_events_in_window(
            start_time, end_time, merge_window, lookback_seconds=lookback
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
    spectrogram_path = None
    has_birdnet_event = any(ev.get("source") == "birdnet" for ev in mqtt_events)
    spectrogram_always = bool(app_config.get("processor.generate_spectrogram_always"))
    if spectrogram_always or has_birdnet_event:
        px_per_sec = app_config.get("processor.spectrogram_px_per_sec") or 200
        spectrogram_filename = f"spectrogram_{px_per_sec}.jpg"
        spectrogram_output = os.path.join(output_path_physical, spectrogram_filename)
        if generate_spectrogram(video_output, spectrogram_output, px_per_sec):
            # output_path_logical — каталог сессии (см. get_output_path), файл в нём же.
            spectrogram_path = f"{output_path_logical}/{spectrogram_filename}"
        else:
            logging.warning("Spectrogram generation failed (BirdNET event present)")

    accepted_pre_fusion = list(video_detections)
    video_detections = build_fused_video_detections(
        video_detections,
        mqtt_events,
        start_time=start_time,
        end_time=end_time,
        app_config=app_config,
    )
    try:
        min_conf_store = float(app_config.get("detection.min_confidence_to_store") or 0.05)
    except (TypeError, ValueError):
        min_conf_store = 0.05
    fused_ids = {d.get("track_id") for d in video_detections if d.get("track_id") is not None}
    for item in accepted_pre_fusion:
        tid = item.get("track_id")
        if tid is None:
            continue
        if tid in fused_ids:
            continue
        conf = float(item.get("confidence") or 0.0)
        if conf >= min_conf_store:
            # Should not happen often; keep out of persistence path.
            continue
        rejected_decisions.append(
            {
                **item,
                "accepted": False,
                "decision_reason": "rejected_post_fusion_below_store_threshold",
                "decision_kind": "rejected",
                "outcome_bucket": compute_outcome_bucket(
                    accepted=False,
                    visit_eligible=bool(item.get("visit_eligible", True)),
                    decision_kind="rejected",
                ),
                "trust_band": "red",
                "reject_reason_code": "low_confidence",
            }
        )

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
        now_m = time.monotonic()
        msg = (
            "No detections after merge. YOLO tracks: %s, MQTT events in window: %s",
            len(frame_processor.tracks),
            len(mqtt_events),
        )
        if now_m >= _no_detections_warn_next_monotonic:
            logging.warning(*msg)
            _no_detections_warn_next_monotonic = now_m + _NO_DETECTIONS_WARN_INTERVAL_S
        else:
            logging.debug(*msg)

    video_file_ok = _is_playable_video_file(video_output)
    if len(video_detections) > 0 and not video_file_ok:
        logging.error(
            "Finalize: %s detection(s) but video file missing: %s",
            len(video_detections),
            video_output,
        )
        try:
            if api:
                api.activity_log(
                    type="ingest_gate",
                    data={
                        "reason": "video_file_missing",
                        "stage": "processor_finalize",
                        "video_path": video_path_for_api,
                        "video_output": video_output,
                        "detection_count": len(video_detections),
                    },
                )
        except Exception:
            logging.exception("ingest_gate activity_log failed")

    if len(video_detections) > 0 and video_file_ok:
        scales_delta_kg = None
        has_non_audio = any(d.get("source") != "audio" for d in video_detections)
        scales_on = app_config.get("integrations.scales.enabled")
        weight_est = app_config.get("integrations.scales.weight_estimate_enabled", True)
        if scales_on and weight_est and scales_topic_arg and has_non_audio:
            from scale_sample_log import estimate_weight_delta_kg

            raw_min = app_config.get("integrations.scales.min_delta_kg_for_estimate")
            try:
                min_d = float(raw_min or 0.008)
            except (TypeError, ValueError):
                min_d = 0.008
            require_spike = app_config.get("integrations.scales.estimate_require_consecutive_spike", True)
            est, _n = estimate_weight_delta_kg(
                data_dir,
                start_time,
                end_time,
                min_delta_kg=min_d,
                require_consecutive_spike=bool(require_spike),
            )
            scales_delta_kg = est
            scales_evidence["estimated_delta_kg"] = est
            scales_evidence["sample_count"] = int(_n or 0)
            scales_evidence["min_delta_kg"] = float(min_d)
        resp = api.create_video(
            video_detections,
            audio_detections,
            start_time,
            end_time,
            video_path_for_api,
            spectrogram_path,
            scales_weight_delta_kg=scales_delta_kg,
        )
        video_id = resp.get("video_id") if isinstance(resp, dict) else None
        if video_id is not None:
            try:
                decision_trace["video_id"] = int(video_id)
            except (TypeError, ValueError):
                decision_trace["video_id"] = video_id
        save_crops = app_config.get("processor.save_dataset_crops")
        if video_id is not None and save_crops and video_detections:
            crops_data_dir = get_data_dir()
            raw_mc = app_config.get("processor.dataset_min_confidence", 0.5)
            min_conf = float(raw_mc)
            save_dataset_crops(
                video_detections,
                video_id,
                crops_data_dir,
                min_confidence=min_conf,
            )
        seen = set()
        for d in video_detections:
            sn = d.get("species_name") or d.get("species") or ""
            if sn and sn not in seen:
                seen.add(sn)
                notify_ok = bool(d.get("notification_eligible", True))
                _dk = str(d.get("decision_kind") or "").strip().lower()
                if _dk in ("review_only_generic", "frigate_standalone_excluded"):
                    notify_ok = False
                image_base64, preview_source = encode_notify_preview_base64(d, video_output)
                if not notify_ok:
                    logging.info(
                        "Notify suppressed for %s (eligible=false, kind=%s, reason=%s)",
                        sn,
                        d.get("decision_kind"),
                        d.get("decision_reason"),
                    )
                    continue
                if image_base64 is None:
                    logging.info(
                        "Notify %s without photo: no preview (provider=%s, source=%s)",
                        sn,
                        d.get("detection_provider", "unknown"),
                        preview_source,
                    )
                    continue
                raw_notify = app_config.get("processor.min_confidence_to_notify")
                try:
                    min_notify = (
                        float(raw_notify)
                        if raw_notify is not None and str(raw_notify).strip() != ""
                        else float(app_config.get("processor.min_confidence_to_process") or 0.30)
                    )
                except (TypeError, ValueError):
                    min_notify = float(app_config.get("processor.min_confidence_to_process") or 0.30)
                if float(d.get("confidence") or 0.0) < min_notify:
                    logging.info(
                        "Notify suppressed for %s: confidence=%.3f < processor.min_confidence_to_notify=%.3f",
                        sn,
                        float(d.get("confidence") or 0.0),
                        min_notify,
                    )
                    continue
                else:
                    logging.info(
                        "Notify preview source: %s (%s)",
                        preview_source,
                        sn,
                    )
                try:
                    link = f"videos/{video_id}" if video_id else "live"
                    api.notify_species(
                        sn,
                        image_base64=image_base64,
                        link=link,
                        preview_source=preview_source,
                        notification_eligible=True,
                    )
                    try:
                        api.activity_log(
                            type="notify_preview_generated",
                            data={
                                "species": sn,
                                "video_id": video_id,
                                "preview_source": preview_source,
                                "has_image": bool(image_base64),
                            },
                        )
                    except Exception as e:
                        logging.warning("notify_preview activity_log failed: %s", e)
                except Exception as e:
                    resp_err = getattr(e, "response", None)
                    hint = ""
                    if resp_err is not None:
                        if resp_err.status_code == 403:
                            hint = " (check PROCESSOR_SECRET in app/.env)"
                        hint = f" {resp_err.status_code}{hint}"
                    logging.warning("Notify species failed%s: %s", hint, e)
    try:
        if api and (decision_trace.get("persisted_tracks") or decision_trace.get("rejected_tracks")):
            api.activity_log("decision_trace", decision_trace)
    except Exception:
        logging.exception("Failed to write decision_trace activity log")
    if not video_file_ok:
        try:
            shutil.rmtree(output_path_physical)
        except OSError as e:
            logging.warning("Finalize: could not remove bad session dir %s: %s", output_path_physical, e)
    elif len(video_detections) == 0:
        keep_empty = bool(
            app_config.get(
                "processor.keep_recording_when_no_detections",
            )
        )
        file_src = str(app_config.get("video.source") or "").strip().lower() == "file"
        if keep_empty and file_src:
            logging.info(
                "keep_recording_when_no_detections: retaining session (0 detections, file source): %s",
                output_path_physical,
            )
        else:
            try:
                shutil.rmtree(output_path_physical)
            except OSError as e:
                logging.warning(
                    "Finalize: could not remove empty session dir %s: %s",
                    output_path_physical,
                    e,
                )
