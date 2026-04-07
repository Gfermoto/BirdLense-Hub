"""Финал сессии записи: merge, spectrogram, API, MQTT, уведомления (tech debt #201)."""
from __future__ import annotations

import logging
import os
import shutil
from collections import Counter
from datetime import datetime
from typing import Any, Optional

from api import API
from app_config.app_config import app_config
from dataset_saver import save_dataset_crops
from detection_fusion import build_fused_video_detections
from notify_preview_encode import encode_notify_preview_base64
from processor_support import get_data_dir
from spectrogram import generate_spectrogram


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
) -> None:
    """Свести YOLO+MQTT, сохранить видео в API, уведомления; без детекций — удалить папку."""
    yolo_tracks_count = len(frame_processor.tracks)
    decisions = decision_maker.get_decisions(frame_processor.tracks)
    video_detections = [
        item for item in decisions if item.get('accepted', False)
    ]
    rejected_decisions = [
        item for item in decisions if not item.get('accepted', False)
    ]
    yolo_passed_count = len(video_detections)
    mqtt_events = []
    if mqtt_aggregator:
        lookback = merge_window
        if yolo_tracks_count == 0:
            triggered_cam = getattr(
                motion_detector, 'get_triggered_camera', lambda: None
            )()
            if triggered_cam:
                lookback = max(merge_window, 60)
                logging.info(
                    'Frigate trigger, 0 YOLO: extended MQTT lookback to %ds',
                    lookback,
                )
        mqtt_events = mqtt_aggregator.get_events_in_window(
            start_time, end_time, merge_window, lookback_seconds=lookback
        )
    if yolo_tracks_count > 0:
        min_dur = app_config.get('processor.min_track_duration', 1)
        logging.info(
            'ByteTrack: %s tracks, %s passed '
            'min_track_duration=%ss (species with frames)',
            yolo_tracks_count,
            yolo_passed_count,
            min_dur,
        )
        if yolo_passed_count == 0 and yolo_tracks_count > 0:
            logging.warning(
                'YOLO: %s ByteTrack row(s) but none passed DecisionMaker '
                '(duration < processor.min_track_duration, confidence below '
                'processor.min_confidence_to_process / overrides, or below '
                'detection.min_confidence_to_store when falling back to detector label). '
                'Final result will stay empty unless YOLO detector/classifier produce a valid track — lower min_track_duration '
                'or thresholds if you expect video tracks.',
                yolo_tracks_count,
            )
            for tid, t in frame_processor.tracks.items():
                dur = t.get('end_time', 0) - t.get('start_time', 0)
                detector_events = len(t.get('detector_events', []))
                classifier_events = len(t.get('classifier_events', []))
                logging.info(
                    '  track %s: duration=%.2fs, detector_events=%s, classifier_events=%s',
                    tid,
                    dur,
                    detector_events,
                    classifier_events,
                )
        if rejected_decisions:
            rejected_summary = Counter(
                str(item.get('decision_reason') or 'rejected_unknown')
                for item in rejected_decisions
            )
            logging.info(
                'DecisionMaker rejected tracks: %s',
                dict(sorted(rejected_summary.items())),
            )
    elif mqtt_events:
        logging.warning(
            'ByteTrack: 0 YOLO tracks but %s MQTT events. '
            'Trigger/MQTT alone no longer creates final detections without YOLO confirmation.',
            len(mqtt_events),
        )

    audio_detections: list = []
    spectrogram_path = None
    has_birdnet_event = any(
        ev.get('source') == 'birdnet' for ev in mqtt_events
    )
    spectrogram_always = bool(app_config.get('processor.generate_spectrogram_always'))
    if spectrogram_always or has_birdnet_event:
        px_per_sec = app_config.get('processor.spectrogram_px_per_sec') or 200
        spectrogram_filename = f'spectrogram_{px_per_sec}.jpg'
        spectrogram_output = os.path.join(
            output_path_physical, spectrogram_filename
        )
        if generate_spectrogram(video_output, spectrogram_output, px_per_sec):
            # output_path_logical — каталог сессии (см. get_output_path), файл в нём же.
            spectrogram_path = f'{output_path_logical}/{spectrogram_filename}'
        else:
            logging.warning(
                'Spectrogram generation failed (BirdNET event present)'
            )

    video_detections = build_fused_video_detections(
        video_detections,
        mqtt_events,
        start_time=start_time,
        end_time=end_time,
        app_config=app_config,
    )

    for i, d in enumerate(video_detections):
        n_frames = len(d.get('frames') or [])
        if n_frames > 0:
            logging.info(
                'Detection %s: %s has %s track frames',
                i,
                d.get('species_name'),
                n_frames,
            )
        else:
            logging.debug(
                'Detection %s: %s has no frames (source=%s)',
                i,
                d.get('species_name'),
                d.get('source'),
            )

    if mqtt_aggregator and video_detections:
        mqtt_aggregator.publish_detections(
            video_detections, start_time, end_time
        )

    video_summary = [
        {k: v for k, v in d.items() if k != 'best_frame'}
        for d in video_detections
    ]
    logging.info(
        'Processing stopped. Video Result: %s; Audio Result: %s',
        video_summary,
        audio_detections,
    )
    if len(video_detections) == 0 and mqtt_aggregator:
        logging.warning(
            'No detections after merge. YOLO tracks: %s, '
            'MQTT events in window: %s',
            len(frame_processor.tracks),
            len(mqtt_events),
        )

    if len(video_detections) > 0:
        scales_delta_kg = None
        has_non_audio = any(
            d.get('source') != 'audio' for d in video_detections
        )
        scales_on = app_config.get('integrations.scales.enabled')
        weight_est = app_config.get(
            'integrations.scales.weight_estimate_enabled', True
        )
        if scales_on and weight_est and scales_topic_arg and has_non_audio:
            from scale_sample_log import estimate_weight_delta_kg

            raw_min = app_config.get(
                'integrations.scales.min_delta_kg_for_estimate'
            )
            try:
                min_d = float(raw_min or 0.008)
            except (TypeError, ValueError):
                min_d = 0.008
            require_spike = app_config.get(
                'integrations.scales.estimate_require_consecutive_spike', True
            )
            est, _n = estimate_weight_delta_kg(
                data_dir,
                start_time,
                end_time,
                min_delta_kg=min_d,
                require_consecutive_spike=bool(require_spike),
            )
            scales_delta_kg = est
        resp = api.create_video(
            video_detections,
            audio_detections,
            start_time,
            end_time,
            video_path_for_api,
            spectrogram_path,
            scales_weight_delta_kg=scales_delta_kg,
        )
        video_id = resp.get('video_id') if isinstance(resp, dict) else None
        save_crops = app_config.get('processor.save_dataset_crops')
        if video_id is not None and save_crops and video_detections:
            crops_data_dir = get_data_dir()
            raw_mc = app_config.get('processor.dataset_min_confidence', 0.5)
            min_conf = float(raw_mc)
            save_dataset_crops(
                video_detections,
                video_id,
                crops_data_dir,
                min_confidence=min_conf,
            )
        seen = set()
        for d in video_detections:
            sn = d.get('species_name') or d.get('species') or ''
            if sn and sn not in seen:
                seen.add(sn)
                image_base64, preview_source = encode_notify_preview_base64(
                    d, video_output
                )
                if image_base64 is None:
                    logging.info(
                        'Notify %s without photo: no preview '
                        '(provider=%s, source=%s)',
                        sn,
                        d.get('detection_provider', 'unknown'),
                        preview_source,
                    )
                else:
                    logging.info(
                        'Notify preview source: %s (%s)',
                        preview_source,
                        sn,
                    )
                try:
                    link = f'videos/{video_id}' if video_id else 'live'
                    api.notify_species(
                        sn,
                        image_base64=image_base64,
                        link=link,
                        preview_source=preview_source,
                    )
                    try:
                        api.activity_log(
                            type='notify_preview_generated',
                            data={
                                'species': sn,
                                'video_id': video_id,
                                'preview_source': preview_source,
                                'has_image': bool(image_base64),
                            },
                        )
                    except Exception as e:
                        logging.warning(
                            'notify_preview activity_log failed: %s', e
                        )
                except Exception as e:
                    resp_err = getattr(e, 'response', None)
                    hint = ''
                    if resp_err is not None:
                        if resp_err.status_code == 403:
                            hint = ' (check PROCESSOR_SECRET in app/.env)'
                        hint = f' {resp_err.status_code}{hint}'
                    logging.warning('Notify species failed%s: %s', hint, e)
    else:
        shutil.rmtree(output_path_physical)
