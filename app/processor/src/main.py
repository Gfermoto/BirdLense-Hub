import threading
import time
from datetime import datetime, timezone
import argparse
import logging
import os
import shutil

import cv2
from detection_stack import build_detection_stack
from spectrogram import generate_spectrogram
from motion_detectors.fake import FakeMotionDetector
from mqtt_aggregator import MQTTEventAggregator
from species_normalizer import normalize, merge_detections
from birdnet_mqtt_confidence import merge_birdnet_mqtt_bias_into_overrides
from multi_camera_confidence import apply_multi_camera_confidence_boost
from fps_tracker import FPSTracker
from api import API
from dataset_saver import save_dataset_crops
from sources.video_file_source import VideoFileSource
from sources.go2rtc_stream_source import Go2RTCStreamSource
from sources.go2rtc_stream_source import _build_stream_url
from app_config.app_config import app_config

# Set up logging: console + file for remote diagnostics (System page)
def _setup_logging():
    fmt = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    if not root.handlers:
        h = logging.StreamHandler()
        h.setFormatter(logging.Formatter(fmt))
        root.addHandler(h)
    data_dir = os.environ.get('DATA_DIR', 'data')
    log_path = os.path.join(data_dir, 'processor.log')
    try:
        from logging.handlers import RotatingFileHandler
        fh = RotatingFileHandler(
            log_path, maxBytes=5 * 1024 * 1024, backupCount=2,
            encoding='utf-8')
        fh.setFormatter(logging.Formatter(fmt))
        root.addHandler(fh)
    except OSError:
        pass


_setup_logging()

# Состояние для честной проверки Video/YOLO в статусе (обновляется в main loop)
_processor_status = {'last_video_ok_at': None, 'last_yolo_ok_at': None}


def get_output_path():
    data_dir = os.environ.get('DATA_DIR', 'data')
    subpath = time.strftime("%Y/%m/%d/%H%M%S")
    output_dir = os.path.join(data_dir, 'recordings', subpath)
    os.makedirs(output_dir, exist_ok=True)
    return output_dir, f"data/recordings/{subpath}"


def _restart_flag_path():
    data_dir = os.environ.get('DATA_DIR', 'data')
    return os.path.join(data_dir, 'restart_processor.flag')


def _check_restart_flag():
    """If flag exists, exit so docker restarts the container."""
    flag_path = _restart_flag_path()
    if os.path.exists(flag_path):
        try:
            os.remove(flag_path)
        except OSError:
            pass
        logging.info("Restart flag found, exiting for restart")
        raise SystemExit(0)


def _encode_notify_preview_base64(detection: dict, video_file_path: str) -> tuple[str | None, str]:
    """Return (image_base64, source): best_frame | bbox_crop | full_frame | none."""
    try:
        import base64
        import numpy as np

        bf = detection.get('best_frame')
        if isinstance(bf, np.ndarray):
            ok, buf = cv2.imencode('.jpg', bf)
            if ok and buf is not None:
                return base64.b64encode(buf.tobytes()).decode('ascii'), 'best_frame'
    except Exception as e:
        logging.warning("Encode best_frame for notify failed: %s", e)

    frames = detection.get('frames') or []
    if not video_file_path:
        return None, 'none'

    def _pick_timestamp() -> float:
        try:
            st = float(detection.get('start_time') or 0)
            et = float(detection.get('end_time') or st)
            if et > st:
                return st + (et - st) * 0.5
            return st
        except Exception:
            return 0.0

    mid = frames[len(frames) // 2] if isinstance(frames, list) and frames else None
    bbox = mid.get('bbox') if isinstance(mid, dict) else None
    t = float(mid.get('t') or _pick_timestamp()) if isinstance(mid, dict) else _pick_timestamp()

    def _read_frame_with_retries(ts: float):
        retry_delays = (0.0, 0.2, 0.5)
        for idx, delay in enumerate(retry_delays):
            cap = cv2.VideoCapture(video_file_path)
            try:
                if not cap.isOpened():
                    frame = None
                else:
                    fps = cap.get(cv2.CAP_PROP_FPS) or 0.0
                    if fps > 0.01:
                        cap.set(cv2.CAP_PROP_POS_FRAMES, max(0, int(ts * fps)))
                    else:
                        cap.set(cv2.CAP_PROP_POS_MSEC, max(0.0, ts * 1000.0))
                    ok_local, frame = cap.read()
                    if not ok_local:
                        frame = None
                    if frame is None and ts > 0:
                        cap.set(cv2.CAP_PROP_POS_MSEC, 0.0)
                        ok_local, frame = cap.read()
                        if not ok_local:
                            frame = None
                if frame is not None:
                    return frame
            finally:
                cap.release()
            if idx + 1 < len(retry_delays):
                time.sleep(delay)
        return None

    try:
        frame = _read_frame_with_retries(t)
        if frame is None:
            return None, 'none'
        h, w = frame.shape[:2]
        # Primary fallback: bbox crop when available.
        if isinstance(bbox, (list, tuple)) and len(bbox) == 4:
            x1 = max(0, min(w - 1, int(float(bbox[0]) * w)))
            y1 = max(0, min(h - 1, int(float(bbox[1]) * h)))
            x2 = max(x1 + 1, min(w, int(float(bbox[2]) * w)))
            y2 = max(y1 + 1, min(h, int(float(bbox[3]) * h)))
            crop = frame[y1:y2, x1:x2]
            if crop.size > 0:
                ok, buf = cv2.imencode('.jpg', crop, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
                if ok and buf is not None:
                    import base64
                    return base64.b64encode(buf.tobytes()).decode('ascii'), 'bbox_crop'

        # Secondary fallback: full frame (avoid empty notifications even without bbox).
        ok, buf = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 88])
        if not ok or buf is None:
            return None, 'none'
        import base64
        return base64.b64encode(buf.tobytes()).decode('ascii'), 'full_frame'
    except Exception as e:
        logging.warning("Encode video crop for notify failed: %s", e)
        return None, 'none'


# Ссылка на MQTT-агрегатор для heartbeat (устанавливается в main() при создании)
_heartbeat_mqtt_ref = [None]


def heartbeat():
    """Отправляет heartbeat в API каждые 60 сек. Включает last_video_ok_at, last_yolo_ok_at, mqtt_connected, encoding_used."""
    id = None
    api = None
    while True:
        try:
            if api is None:
                api = API()
            data = {"status": "up"}
            if _processor_status.get('last_video_ok_at'):
                data['last_video_ok_at'] = _processor_status['last_video_ok_at']
            if _processor_status.get('last_yolo_ok_at'):
                data['last_yolo_ok_at'] = _processor_status['last_yolo_ok_at']
            mqtt_aggregator_ref = _heartbeat_mqtt_ref[0] if _heartbeat_mqtt_ref else None
            if mqtt_aggregator_ref is not None:
                try:
                    data['mqtt_connected'] = (
                        mqtt_aggregator_ref.is_mqtt_ok_for_heartbeat()
                    )
                except Exception:
                    data['mqtt_connected'] = False
            try:
                from encoding_status import get_last_encoding_used
                enc = get_last_encoding_used()
                if enc:
                    data['encoding_used'] = enc
            except Exception:
                pass
            id = api.activity_log(type='heartbeat', data=data, id=id)
        except Exception as e:
            logging.error("Heartbeat failed: %s (will retry in 60s)", e)
        _check_restart_flag()
        time.sleep(60)


def main():
    heartbeat_thread = threading.Thread(target=heartbeat, daemon=True)
    heartbeat_thread.start()

    parser = argparse.ArgumentParser(description="Smart bird feeder program")
    parser.add_argument('input', type=str, nargs='?',
                        help='Input source, camera/video file')
    parser.add_argument('--fake-motion', type=str, choices=['true', 'false'],
                        help='Use fake motion detector with motion or not')
    parser.add_argument('--mock-mqtt', action='store_true',
                        help='Development: fake motion instead of MQTT (no broker needed)')
    args = parser.parse_args()

    # Instantiate all helper classes
    api = API()
    main_size = (
        app_config.get('video.video_width', 1280),
        app_config.get('video.video_height', 720),
    )
    lores_size = (640, 640)

    # Build camera map — только из video.cameras, без default
    from app_config.cameras import get_valid_cameras, cameras_for_processor
    cameras_config = app_config.get('video.cameras') or []
    valid = get_valid_cameras(cameras_config)
    cameras = cameras_for_processor(valid)
    go2rtc_url = (os.environ.get('GO2RTC_URL') or app_config.get('video.go2rtc_url') or '').strip()
    if not go2rtc_url:
        logging.warning('video.go2rtc_url не задан. Укажите в Настройках: http://IP:1984')
    if (not cameras or not go2rtc_url) and app_config.get('video.source') == 'go2rtc':
        logging.warning("video.cameras или video.go2rtc_url не заданы. Добавьте в Настройках. Processor будет ждать перезапуска.")
        hb_id = None
        while True:
            _check_restart_flag()
            try:
                hb_id = api.activity_log(type='heartbeat', data={'status': 'waiting_cameras'}, id=hb_id)
            except Exception as e:
                logging.error("Heartbeat (waiting_cameras) failed: %s", e)
            time.sleep(60)
    default_camera_id = cameras[0]['id']
    media_sources_cache = {}
    mjpeg_base_port = 8082

    def get_media_source(camera_id):
        if camera_id not in media_sources_cache:
            cam = next((c for c in cameras if c['id'] == camera_id), cameras[0])
            stream_url = _build_stream_url(
                go2rtc_url, cam['stream_name'],
                username=app_config.get('video.go2rtc_username'),
                password=app_config.get('video.go2rtc_password'),
            )
            idx = next((i for i, c in enumerate(cameras) if c['id'] == camera_id), 0)
            encoding = (app_config.get('video.encoding') or 'cpu').strip().lower()
            if encoding not in ('cpu', 'intel'):
                encoding = 'cpu'
            media_sources_cache[camera_id] = Go2RTCStreamSource(
                stream_url=stream_url,
                main_size=main_size,
                lores_size=lores_size,
                auto_reconnect=app_config.get('video.auto_reconnect', True),
                mjpeg_port=mjpeg_base_port + idx,
                encoding_mode=encoding,
            )
        return media_sources_cache[camera_id]

    # Media source: file (arg) | go2rtc
    if args.input:
        media_source = VideoFileSource(args.input, main_size=main_size, lores_size=lores_size)
    else:
        if app_config.get('video.source') != 'go2rtc':
            logging.warning("video.source must be go2rtc; falling back")
        media_source = get_media_source(default_camera_id)
        for cam in cameras:
            get_media_source(cam['id'])

        # Подпитка MJPEG для всех камер (иначе в Live только активная камера показывает картинку)
        def _mjpeg_feeder():
            while True:
                time.sleep(0.5)
                for _cid, src in list(media_sources_cache.items()):
                    try:
                        if getattr(src, 'push_one_frame_to_mjpeg', None):
                            src.push_one_frame_to_mjpeg()
                    except Exception as e:
                        logging.debug("MJPEG feeder: %s", e)

        _mjpeg_thread = threading.Thread(target=_mjpeg_feeder, daemon=True)
        _mjpeg_thread.start()

    # MQTT broker for motion/aggregator
    mqtt_broker = os.environ.get('MQTT_BROKER') or app_config.get('mqtt.broker')
    mqtt_aggregator = None
    _data_dir = os.environ.get('DATA_DIR', 'data')
    scales_topic_arg = None
    scales_unit_arg = 'kg'
    if app_config.get('integrations.scales.enabled'):
        scales_unit_arg = (app_config.get('integrations.scales.unit') or 'kg').strip().lower() or 'kg'
        src = (app_config.get('integrations.scales.source') or 'mqtt').strip().lower()
        mq_st = (app_config.get('integrations.scales.mqtt_topic') or '').strip()
        if src == 'mqtt' and mq_st:
            scales_topic_arg = mq_st
    frigate_camera_filter = (
        app_config.get('motion.frigate_camera_filter')
        or app_config.get('mqtt.frigate_camera_filter')
        or [c['id'] for c in cameras]
    )
    frigate_label_filter = set(app_config.get('motion.frigate_label_filter') or app_config.get('mqtt.frigate_label_filter') or ['bird', 'Bird'])
    frigate_label_exclude = set(
        app_config.get('motion.frigate_label_exclude')
        or app_config.get('mqtt.frigate_label_exclude')
        or ['cat', 'dog']
    )
    # Frigate + BirdNET: always active when MQTT configured (merge + trigger)
    use_frigate_from_aggregator = bool(mqtt_broker)
    if mqtt_broker:
        on_frigate_motion = None
        if use_frigate_from_aggregator:
            from motion_detectors.frigate_mqtt import FrigateMotionFromAggregator
            frigate_detector = FrigateMotionFromAggregator(None, frigate_camera_filter, frigate_label_filter)
            on_frigate_motion = frigate_detector.get_on_frigate_motion_tuple()
        mqtt_client_id = None
        if args.input:
            mqtt_client_id = os.environ.get('MQTT_CLIENT_ID') or 'birdlense_aggregator_test'
        _scales_hist_lines = int(
            app_config.get('integrations.scales.history_max_lines') or 10000
        )
        mqtt_aggregator = MQTTEventAggregator(
            broker=mqtt_broker,
            port=app_config.get('mqtt.port', 1883),
            frigate_topic=app_config.get('mqtt.frigate_topic', 'frigate/events'),
            birdnet_topic=app_config.get('mqtt.birdnet_topic', 'birdnet'),
            publish_topic=app_config.get('mqtt.publish_topic', 'birdlense/detections'),
            username=os.environ.get('MQTT_USERNAME') or app_config.get('mqtt.username'),
            password=os.environ.get('MQTT_PASSWORD') or app_config.get('mqtt.password'),
            on_frigate_motion=on_frigate_motion,
            frigate_label_exclude=list(frigate_label_exclude),
            client_id=mqtt_client_id,
            ha_discovery=app_config.get('mqtt.ha_discovery', True),
            base_url=app_config.get('notifications.base_url', ''),
            reconnect_min_delay=app_config.get('mqtt.reconnect_min_delay', 5),
            reconnect_max_delay=app_config.get('mqtt.reconnect_max_delay', 300),
            scales_topic=scales_topic_arg,
            scales_data_dir=_data_dir if scales_topic_arg else None,
            scales_unit=scales_unit_arg,
            scales_history_max_lines=_scales_hist_lines,
        )
        mqtt_aggregator.start()
        _heartbeat_mqtt_ref[0] = mqtt_aggregator
        if use_frigate_from_aggregator:
            frigate_detector._aggregator = mqtt_aggregator

    # Motion detector: fake (arg) | mock-mqtt | Frigate + local/OpenCV fallback | opencv | pir
    from motion_detectors.factory import build_motion_detector

    if args.fake_motion:
        motion = args.fake_motion.lower() == 'true'
        motion_detector = FakeMotionDetector(motion=motion, wait=10)
    elif args.mock_mqtt:
        motion_detector = FakeMotionDetector(motion=True, wait=5)
        logging.info('Using --mock-mqtt: fake motion for development')
    elif app_config.get('motion.source') == 'pir':
        from motion_detectors.pir import PIRMotionDetector
        motion_detector = PIRMotionDetector()
    else:
        # Frigate + BirdNET: always when MQTT configured
        primary = None
        if use_frigate_from_aggregator and mqtt_aggregator:
            primary = frigate_detector
            for _ in range(5):
                if mqtt_aggregator.is_mqtt_live():
                    break
                time.sleep(1)
            if mqtt_aggregator.is_mqtt_live():
                logging.info(
                    'Motion: Frigate (cameras=%s labels=%s)',
                    list(frigate_camera_filter) if frigate_camera_filter else 'any',
                    list(frigate_label_filter))
            else:
                logging.warning(
                    'Frigate MQTT not live yet after startup wait; detector will keep retrying',
                )

        add_source = app_config.get('motion.source', 'frigate')
        check_n = app_config.get('motion.check_every_n_frames', 1)
        esphome_url = (
            os.environ.get('MOTION_ESPHOME_URL')
            or app_config.get('motion.esphome_url', '')
        ).strip()
        esphome_sensor = (
            os.environ.get('MOTION_ESPHOME_SENSOR')
            or app_config.get('motion.esphome_sensor_id', '')
        ).strip()
        motion_detector = build_motion_detector(
            motion_source=add_source,
            media_source=media_source,
            primary=primary,
            mqtt_broker=mqtt_broker,
            mqtt_topic=app_config.get('motion.mqtt_topic', '').strip(),
            mqtt_port=app_config.get('mqtt.port', 1883),
            mqtt_username=os.environ.get('MQTT_USERNAME') or app_config.get('mqtt.username'),
            mqtt_password=os.environ.get('MQTT_PASSWORD') or app_config.get('mqtt.password'),
            esphome_url=esphome_url,
            esphome_sensor=esphome_sensor,
            check_every_n_frames=check_n,
        )
        if add_source == 'frigate':
            logging.info(
                'Motion: Frigate with local OpenCV fallback (check_every_n_frames=%s)',
                check_n,
            )
        elif add_source == 'opencv':
            logging.info('Motion: + OpenCV (parallel, check_every_n_frames=%s)', check_n)
        elif add_source == 'mqtt' and mqtt_broker and (app_config.get('motion.mqtt_topic') or '').strip():
            logging.info('Motion: + MQTT binary (parallel)')
        elif add_source == 'esphome':
            if esphome_url and esphome_sensor:
                logging.info('Motion: + ESPHome (parallel)')
            else:
                logging.warning('motion.source=esphome but URL/sensor empty')

    frame_processor, decision_maker, merged_overrides = build_detection_stack(
        app_config,
        save_images=bool(app_config.get('processor.save_images')),
        warn_two_stage_fallback=True,
    )
    # No local BirdNET — use YOLO + MQTT (Frigate, BirdNET-Pi/Go)
    regional_species = app_config.get('processor.regional_species') or []
    if regional_species:
        api.set_active_species(regional_species)

    tracker = app_config.get('processor.tracker') or 'bytetrack.yaml'
    logging.info('Using tracker: %s', tracker)
    fps_tracker = FPSTracker()

    # Main motion detection loop
    while True:
        _check_restart_flag()
        if not motion_detector.detect():
            continue
        api.notify_motion()

        session_overrides = merge_birdnet_mqtt_bias_into_overrides(
            merged_overrides, app_config, mqtt_aggregator
        )
        decision_maker.species_confidence_overrides = session_overrides

        # Multi-camera: use triggered camera (MQTT) or default (OpenCV)
        camera_id = (
            getattr(motion_detector, 'get_triggered_camera', lambda: None)()
            or default_camera_id
        )
        if not args.input and app_config.get('video.source') == 'go2rtc':
            media_source = get_media_source(camera_id)

        # Configure video sources
        output_path_physical, output_path_logical = get_output_path()
        video_output = os.path.join(output_path_physical, "video.mp4")
        video_path_for_api = f"{output_path_logical}/video.mp4"

        media_source.start_recording(video_output)

        logging.info(
            f'Motion detected. Processing started. Recording video and audio to "{video_output}"')
        start_time = datetime.now(timezone.utc)

        # Video processing loop
        try:
            frame_processor.reset()
            decision_maker.reset()
            fps_tracker.reset()
            while True:
                frame = media_source.capture()
                if frame is None:
                    break
                _processor_status['last_video_ok_at'] = datetime.now(timezone.utc).isoformat()
                # VideoFileSource: use video timestamp for correct track duration
                frame_time = getattr(media_source, 'get_frame_time', lambda: None)()
                with fps_tracker:
                    has_detections = frame_processor.run(
                        frame, frame_time=frame_time)
                _processor_status['last_yolo_ok_at'] = datetime.now(timezone.utc).isoformat()

                # Decision making
                decision_maker.update_has_detections(has_detections)
                decision_maker.get_first_species_result(
                    frame_processor.tracks)  # для decide_stop_recording
                if decision_maker.decide_stop_recording():
                    break
            fps_tracker.log_summary()
        finally:
            media_source.stop_recording()
            end_time = datetime.now(timezone.utc)

        try:
            yolo_tracks_count = len(frame_processor.tracks)
            video_detections = decision_maker.get_results(
                frame_processor.tracks)
            yolo_passed_count = len(video_detections)
            species_mapping = app_config.get('detection.species_mapping') or {}
            merge_window = app_config.get('detection.merge_window_seconds', 5)
            dedup_window = app_config.get('detection.dedup_window_seconds', 45)
            one_per_species = app_config.get('detection.one_per_species', True)
            source_priority = app_config.get('detection.source_priority') or ["yolo", "frigate", "birdnet"]
            mqtt_events = []
            if mqtt_aggregator:
                lookback = merge_window
                if yolo_tracks_count == 0:
                    triggered_cam = getattr(
                        motion_detector, 'get_triggered_camera', lambda: None
                    )()
                    if triggered_cam:
                        # Pending trigger: событие было до start_time, расширяем lookback
                        lookback = max(merge_window, 60)
                        logging.info(
                            "Frigate trigger, 0 YOLO: extended MQTT lookback to %ds",
                            lookback)
                mqtt_events = mqtt_aggregator.get_events_in_window(
                    start_time, end_time, merge_window, lookback_seconds=lookback)
            if yolo_tracks_count > 0:
                min_dur = app_config.get('processor.min_track_duration', 1)
                logging.info(
                    f"ByteTrack: {yolo_tracks_count} tracks, {yolo_passed_count} passed "
                    f"min_track_duration={min_dur}s (species with frames)")
                if yolo_passed_count == 0 and yolo_tracks_count > 0:
                    for tid, t in frame_processor.tracks.items():
                        dur = t.get('end_time', 0) - t.get('start_time', 0)
                        preds = len(t.get('preds', []))
                        logging.info(
                            f"  track {tid}: duration={dur:.2f}s, preds={preds}")
            elif mqtt_events:
                logging.warning(
                    f"ByteTrack: 0 YOLO tracks but {len(mqtt_events)} MQTT events. "
                    "YOLO не детектирует — треки будут пустые (только вид из Frigate).")
            # Merge YOLO + MQTT (Frigate, BirdNET-Pi/Go)
            audio_detections, spectrogram_path = [], None
            has_birdnet_event = any(ev.get('source') == 'birdnet' for ev in mqtt_events)
            if has_birdnet_event:
                px_per_sec = app_config.get('processor.spectrogram_px_per_sec') or 200
                spectrogram_filename = f'spectrogram_{px_per_sec}.jpg'
                spectrogram_output = os.path.join(output_path_physical, spectrogram_filename)
                if generate_spectrogram(video_output, spectrogram_output, px_per_sec):
                    spectrogram_path = f"{output_path_logical.rsplit('/', 1)[0]}/{spectrogram_filename}"
                else:
                    logging.warning("Spectrogram generation failed (BirdNET event present)")
            video_list = []
            for d in video_detections:
                sn = normalize(
                    d.get('species_name') or d.get('species') or d.get('name', 'unknown'),
                    species_mapping)
                video_list.append({
                    **d, 'species_name': sn, 'species': sn,
                    'source': 'video', 'detection_provider': 'yolo'
                })
            cross_bonus = float(
                app_config.get('detection.cross_source_confidence_bonus') or 0)
            video_detections = merge_detections(
                video_list, mqtt_events, start_time, end_time,
                merge_window, dedup_window, one_per_species=one_per_species,
                source_priority=source_priority,
                cross_source_confidence_bonus=cross_bonus,
                species_mapping=species_mapping,
            )
            video_detections = apply_multi_camera_confidence_boost(
                video_detections, mqtt_events, app_config)

            # Отсечь детекции с низким confidence (4% и т.п.)
            min_conf_store = float(app_config.get('detection.min_confidence_to_store') or 0.05)
            video_detections = [d for d in video_detections if float(d.get('confidence') or 0) >= min_conf_store]

            # Log track/frames info for debugging
            for i, d in enumerate(video_detections):
                n_frames = len(d.get('frames') or [])
                if n_frames > 0:
                    logging.info(f"Detection {i}: {d.get('species_name')} has {n_frames} track frames")
                else:
                    logging.debug(f"Detection {i}: {d.get('species_name')} has no frames (source={d.get('source')})")

            # MQTT publish for HA automations
            if mqtt_aggregator and video_detections:
                mqtt_aggregator.publish_detections(video_detections, start_time, end_time)
                    
            # Log summary without best_frame arrays
            video_summary = [{k: v for k, v in d.items() if k != 'best_frame'} for d in video_detections]
            logging.info(
                f'Processing stopped. Video Result: {video_summary}; Audio Result: {audio_detections}')
            if len(video_detections) == 0 and mqtt_aggregator:
                logging.warning(
                    f'No detections after merge. YOLO tracks: {len(frame_processor.tracks)}, '
                    f'MQTT events in window: {len(mqtt_events)}')
            if len(video_detections) > 0:
                scales_delta_kg = None
                if (
                    app_config.get('integrations.scales.enabled')
                    and app_config.get('integrations.scales.weight_estimate_enabled', True)
                    and scales_topic_arg
                    and any(d.get('source') != 'audio' for d in video_detections)
                ):
                    from scale_sample_log import estimate_weight_delta_kg
                    try:
                        min_d = float(
                            app_config.get('integrations.scales.min_delta_kg_for_estimate')
                            or 0.008
                        )
                    except (TypeError, ValueError):
                        min_d = 0.008
                    est, _n = estimate_weight_delta_kg(
                        _data_dir, start_time, end_time, min_delta_kg=min_d
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
                if (video_id is not None and app_config.get('processor.save_dataset_crops')
                        and video_detections):
                    data_dir = os.environ.get('DATA_DIR', 'data')
                    min_conf = float(app_config.get('processor.dataset_min_confidence', 0.5))
                    save_dataset_crops(video_detections, video_id, data_dir, min_confidence=min_conf)
                # Уведомления — после merge, с превью best_frame в TG
                # Отправляем image_base64 (надёжнее, чем путь — не зависит от общего FS)
                seen = set()
                for d in video_detections:
                    sn = d.get('species_name') or d.get('species') or ''
                    if sn and sn not in seen:
                        seen.add(sn)
                        image_base64, preview_source = _encode_notify_preview_base64(d, video_output)
                        if image_base64 is None:
                            logging.info(
                                "Notify %s without photo: no preview (provider=%s, source=%s)",
                                sn, d.get('detection_provider', 'unknown'), preview_source)
                        else:
                            logging.info("Notify preview source: %s (%s)", preview_source, sn)
                        try:
                            link = f"videos/{video_id}" if video_id else "live"
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
                                logging.warning("notify_preview activity_log failed: %s", e)
                        except Exception as e:
                            resp = getattr(e, 'response', None)
                            hint = ''
                            if resp is not None:
                                if resp.status_code == 403:
                                    hint = ' (check PROCESSOR_SECRET in app/.env)'
                                hint = f' {resp.status_code}{hint}'
                            logging.warning("Notify species failed%s: %s", hint, e)
            else:
                # no detections, delete folder
                shutil.rmtree(output_path_physical)
        except Exception as e:
            logging.error(e)

        if args.input:
            break

    # Close all media sources (multi-camera cache)
    if app_config.get('video.source') == 'go2rtc':
        for src in media_sources_cache.values():
            src.close()
    else:
        media_source.close()


if __name__ == "__main__":
    main()
