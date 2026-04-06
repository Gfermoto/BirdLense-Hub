"""Финал сессии записи: merge, spectrogram, API, MQTT, уведомления (tech debt #201)."""
from __future__ import annotations

import logging
import os
import shutil
from datetime import datetime
from typing import Any, Optional

from api import API
from app_config.app_config import app_config
from dataset_saver import save_dataset_crops
from multi_camera_confidence import apply_multi_camera_confidence_boost
from notify_preview_encode import encode_notify_preview_base64
from species_normalizer import merge_detections, normalize
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
    video_detections = decision_maker.get_results(frame_processor.tracks)
    yolo_passed_count = len(video_detections)
    species_mapping = app_config.get('detection.species_mapping') or {}
    merge_window = app_config.get('detection.merge_window_seconds', 5)
    dedup_window = app_config.get('detection.dedup_window_seconds', 45)
    one_per_species = app_config.get('detection.one_per_species', True)
    source_priority = app_config.get('detection.source_priority') or [
        'yolo',
        'frigate',
        'birdnet',
    ]
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
            for tid, t in frame_processor.tracks.items():
                dur = t.get('end_time', 0) - t.get('start_time', 0)
                preds = len(t.get('preds', []))
                logging.info(
                    '  track %s: duration=%.2fs, preds=%s',
                    tid,
                    dur,
                    preds,
                )
    elif mqtt_events:
        logging.warning(
            'ByteTrack: 0 YOLO tracks but %s MQTT events. '
            'YOLO не детектирует — треки пустые (только вид из Frigate).',
            len(mqtt_events),
        )

    audio_detections: list = []
    spectrogram_path = None
    has_birdnet_event = any(
        ev.get('source') == 'birdnet' for ev in mqtt_events
    )
    if has_birdnet_event:
        px_per_sec = app_config.get('processor.spectrogram_px_per_sec') or 200
        spectrogram_filename = f'spectrogram_{px_per_sec}.jpg'
        spectrogram_output = os.path.join(
            output_path_physical, spectrogram_filename
        )
        if generate_spectrogram(video_output, spectrogram_output, px_per_sec):
            parent = output_path_logical.rsplit('/', 1)[0]
            spectrogram_path = f'{parent}/{spectrogram_filename}'
        else:
            logging.warning(
                'Spectrogram generation failed (BirdNET event present)'
            )

    video_list = []
    for d in video_detections:
        sn = normalize(
            d.get('species_name')
            or d.get('species')
            or d.get('name', 'unknown'),
            species_mapping,
        )
        video_list.append(
            {
                **d,
                'species_name': sn,
                'species': sn,
                'source': 'video',
                'detection_provider': 'yolo',
            }
        )
    cross_bonus = float(
        app_config.get('detection.cross_source_confidence_bonus') or 0
    )
    video_detections = merge_detections(
        video_list,
        mqtt_events,
        start_time,
        end_time,
        merge_window,
        dedup_window,
        one_per_species=one_per_species,
        source_priority=source_priority,
        cross_source_confidence_bonus=cross_bonus,
        species_mapping=species_mapping,
    )
    video_detections = apply_multi_camera_confidence_boost(
        video_detections, mqtt_events, app_config
    )

    min_conf_store = float(
        app_config.get('detection.min_confidence_to_store') or 0.05
    )
    video_detections = [
        d
        for d in video_detections
        if float(d.get('confidence') or 0) >= min_conf_store
    ]

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
            crops_data_dir = os.environ.get('DATA_DIR', 'data')
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
