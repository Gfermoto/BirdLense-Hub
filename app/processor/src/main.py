import threading
import time
from datetime import datetime, timezone
import argparse
import logging
import os
import shutil

import cv2
from frame_processor import FrameProcessor
from detection_strategy import SingleStageStrategy, TwoStageStrategy
from spectrogram import generate_spectrogram
from motion_detectors.fake import FakeMotionDetector
from motion_detectors.opencv_motion import OpenCVMotionDetector
from mqtt_aggregator import MQTTEventAggregator
from species_normalizer import normalize, merge_detections
from decision_maker import DecisionMaker
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


def heartbeat():
    """Отправляет heartbeat в API каждые 60 сек. При ошибке — логирует и повторяет (не падает)."""
    id = None
    api = None
    while True:
        try:
            if api is None:
                api = API()
            id = api.activity_log(type='heartbeat', data={"status": "up"}, id=id)
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
            media_sources_cache[camera_id] = Go2RTCStreamSource(
                stream_url=stream_url,
                main_size=main_size,
                lores_size=lores_size,
                auto_reconnect=app_config.get('video.auto_reconnect', True),
                mjpeg_port=mjpeg_base_port + idx,
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

    # MQTT broker for motion/aggregator
    mqtt_broker = os.environ.get('MQTT_BROKER') or app_config.get('mqtt.broker')
    mqtt_aggregator = None
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
    use_frigate_from_aggregator = (
        app_config.get('motion.source') in ('frigate', 'mqtt')
        and mqtt_broker
        and not (app_config.get('motion.mqtt_topic') or '').strip()
    )
    if mqtt_broker:
        on_frigate_motion = None
        if use_frigate_from_aggregator:
            from motion_detectors.frigate_mqtt import FrigateMotionFromAggregator
            frigate_detector = FrigateMotionFromAggregator(None, frigate_camera_filter, frigate_label_filter)
            on_frigate_motion = frigate_detector.get_on_frigate_motion_tuple()
        mqtt_client_id = None
        if args.input:
            mqtt_client_id = os.environ.get('MQTT_CLIENT_ID') or 'birdlense_aggregator_test'
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
        )
        mqtt_aggregator.start()
        if use_frigate_from_aggregator:
            frigate_detector._aggregator = mqtt_aggregator

    # Motion detector: fake (arg) | mock-mqtt | opencv | mqtt | pir
    if args.fake_motion:
        motion = args.fake_motion.lower() == 'true'
        motion_detector = FakeMotionDetector(motion=motion, wait=10)
    elif args.mock_mqtt:
        motion_detector = FakeMotionDetector(motion=True, wait=5)
        logging.info('Using --mock-mqtt: fake motion for development')
    elif use_frigate_from_aggregator and mqtt_aggregator:
        for _ in range(5):
            if mqtt_aggregator.is_connected():
                break
            time.sleep(1)
        if not mqtt_aggregator.is_connected():
            logging.warning('Frigate MQTT not connected, falling back to OpenCV')
            motion_detector = OpenCVMotionDetector(capture_fn=media_source.capture)
        else:
            logging.info(
                'Motion: Frigate (cameras=%s labels=%s)',
                list(frigate_camera_filter) if frigate_camera_filter else 'any',
                list(frigate_label_filter))
            motion_detector = frigate_detector
    elif app_config.get('motion.source') == 'mqtt' and mqtt_broker and (app_config.get('motion.mqtt_topic') or '').strip():
        mqtt_topic = app_config.get('motion.mqtt_topic', '').strip()
        from motion_detectors.mqtt_binary import MQTTBinaryMotionDetector
        motion_detector = MQTTBinaryMotionDetector(
            broker=mqtt_broker,
            port=app_config.get('mqtt.port', 1883),
            topic=mqtt_topic,
            username=os.environ.get('MQTT_USERNAME') or app_config.get('mqtt.username'),
            password=os.environ.get('MQTT_PASSWORD') or app_config.get('mqtt.password'),
        )
        motion_detector.start()
    elif app_config.get('motion.source') == 'esphome':
        esphome_url = (os.environ.get('MOTION_ESPHOME_URL') or app_config.get('motion.esphome_url', '')).strip()
        esphome_sensor = (os.environ.get('MOTION_ESPHOME_SENSOR') or app_config.get('motion.esphome_sensor_id', '')).strip()
        if esphome_url and esphome_sensor:
            from motion_detectors.esphome_binary import ESPHomeBinaryMotionDetector
            motion_detector = ESPHomeBinaryMotionDetector(
                url=esphome_url,
                sensor_id=esphome_sensor,
            )
        else:
            logging.warning('motion.source=esphome but URL/sensor empty, falling back to OpenCV')
            motion_detector = OpenCVMotionDetector(capture_fn=media_source.capture)
    elif app_config.get('motion.source') == 'opencv':
        logging.info(
            'Motion: OpenCV (Frigate events only for merge, NOT for trigger)')
        motion_detector = OpenCVMotionDetector(capture_fn=media_source.capture)
    elif app_config.get('motion.source') == 'pir':
        from motion_detectors.pir import PIRMotionDetector
        motion_detector = PIRMotionDetector()
    else:
        motion_detector = OpenCVMotionDetector(capture_fn=media_source.capture)

    decision_maker = DecisionMaker(
        max_record_seconds=app_config.get('processor.max_record_seconds'),
        max_inactive_seconds=app_config.get('processor.max_inactive_seconds'),
        min_track_duration=app_config.get('processor.min_track_duration', 1),
        min_confidence_to_process=app_config.get(
            'processor.min_confidence_to_process'),
        species_confidence_overrides=app_config.get(
            'processor.species_confidence_overrides') or {},
    )
    # No local BirdNET — use YOLO + MQTT (Frigate, BirdNET-Pi/Go)
    regional_species = app_config.get('processor.regional_species') or []
    if regional_species:
        api.set_active_species(regional_species)

    # Configure Detection Strategy
    processor_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    strategy_type = app_config.get('processor.detection_strategy', 'single_stage')
    binary_path = app_config.get('processor.models.binary', 'models/detection/weights/best.pt')
    classifier_path = app_config.get('processor.models.classifier', 'models/classification/weights/best.pt')
    if not os.path.isabs(binary_path):
        binary_path = os.path.join(processor_root, binary_path)
    if not os.path.isabs(classifier_path):
        classifier_path = os.path.join(processor_root, classifier_path)

    if strategy_type == 'two_stage' and os.path.isfile(binary_path) and os.path.isfile(classifier_path):
        detection_strategy = TwoStageStrategy(
            binary_model_path=binary_path,
            classifier_model_path=classifier_path,
            regional_species=regional_species
        )
    else:
        if strategy_type == 'two_stage':
            logging.warning(
                f'YOLO two_stage: модели не найдены ({binary_path}, {classifier_path}). '
                'Используем single_stage с yolov8n.pt. Добавьте best.pt в processor/models/ для полной детекции.'
            )
        single_path = app_config.get('processor.models.single_stage', 'yolov8n.pt')
        if not os.path.isabs(single_path):
            single_path = os.path.join(processor_root, single_path)
        # .pt файл или yolov8n.pt (pretrained)
        if not os.path.isfile(single_path):
            single_path = 'yolov8n.pt'
        detection_strategy = SingleStageStrategy(
            model_path=single_path,
            regional_species=regional_species
        )

    tracker = app_config.get('processor.tracker') or 'bytetrack.yaml'
    logging.info(f'Using tracker: {tracker}')
    frame_processor = FrameProcessor(
        detection_strategy=detection_strategy,
        tracker=tracker,
        save_images=app_config.get('processor.save_images')
    )
    fps_tracker = FPSTracker()

    # Main motion detection loop
    while True:
        _check_restart_flag()
        if not motion_detector.detect():
            continue
        api.notify_motion()

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
                # VideoFileSource: use video timestamp for correct track duration
                frame_time = getattr(media_source, 'get_frame_time', lambda: None)()
                with fps_tracker:
                    has_detections = frame_processor.run(
                        frame, frame_time=frame_time)

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
            mqtt_events = []
            if mqtt_aggregator:
                mqtt_events = mqtt_aggregator.get_events_in_window(
                    start_time, end_time, merge_window)
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
            video_detections = merge_detections(
                video_list, mqtt_events, start_time, end_time,
                merge_window, dedup_window)

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
                resp = api.create_video(video_detections, audio_detections, start_time,
                                        end_time, video_path_for_api, spectrogram_path)
                video_id = resp.get('video_id') if isinstance(resp, dict) else None
                if (video_id is not None and app_config.get('processor.save_dataset_crops')
                        and video_detections):
                    data_dir = os.environ.get('DATA_DIR', 'data')
                    min_conf = float(app_config.get('processor.dataset_min_confidence', 0.5))
                    save_dataset_crops(video_detections, video_id, data_dir, min_confidence=min_conf)
                # Уведомления — после merge (Frigate/YOLO), без фото, превью по ссылке
                seen = set()
                for d in video_detections:
                    sn = d.get('species_name') or d.get('species') or ''
                    if sn and sn not in seen:
                        seen.add(sn)
                        try:
                            api.notify_species(sn, image_path=None)
                        except Exception as e:
                            logging.warning("Notify species failed: %s", e)
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
