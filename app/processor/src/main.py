import threading
import time
from datetime import datetime, timezone
import argparse
import logging
import os
import shutil
from frame_processor import FrameProcessor
from detection_strategy import SingleStageStrategy, TwoStageStrategy
from motion_detectors.fake import FakeMotionDetector
from motion_detectors.opencv_motion import OpenCVMotionDetector
from motion_detectors.frigate_mqtt import FrigateMQTTMotionDetector
from mqtt_aggregator import MQTTEventAggregator
from species_normalizer import normalize, merge_detections
from decision_maker import DecisionMaker
from fps_tracker import FPSTracker
from api import API
from sources.video_file_source import VideoFileSource
from sources.go2rtc_stream_source import Go2RTCStreamSource
from sources.go2rtc_stream_source import _build_stream_url
from audio_processor import AudioProcessor
from llm_verifier import LLMVerifier
from app_config.app_config import app_config

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),  # Logs to the console
    ]
)


def get_output_path():
    output_dir = "data/recordings/" + time.strftime("%Y/%m/%d/%H%M%S")
    os.makedirs(output_dir, exist_ok=True)
    return output_dir


RESTART_FLAG = "data/restart_processor.flag"


def _check_restart_flag():
    """If flag exists, exit so docker restarts the container."""
    if os.path.exists(RESTART_FLAG):
        try:
            os.remove(RESTART_FLAG)
        except OSError:
            pass
        logging.info("Restart flag found, exiting for restart")
        raise SystemExit(0)


def heartbeat():
    api = API()
    id = None
    while True:
        _check_restart_flag()
        # keep updating activity_log record until restart
        id = api.activity_log(type='heartbeat', data={"status": "up"}, id=id)
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
        app_config.get('video.video_width') or app_config.get('camera.video_width', 1280),
        app_config.get('video.video_height') or app_config.get('camera.video_height', 720),
    )
    lores_size = (640, 640)

    # Build camera map for multi-camera (go2rtc)
    cameras_config = app_config.get('video.cameras')
    if cameras_config:
        cameras = [
            {
                'id': c.get('id') or c.get('stream_name', ''),
                'stream_name': c.get('stream_name', c.get('id', '')),
            }
            for c in cameras_config
        ]
    else:
        stream_name = app_config.get('video.stream_name', 'bird_cam')
        cameras = [{'id': stream_name, 'stream_name': stream_name}]
    go2rtc_url = os.environ.get('GO2RTC_URL') or app_config.get('video.go2rtc_url', 'http://go2rtc:1984')
    default_camera_id = cameras[0]['id'] if cameras else 'bird_cam'
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

    # Media source: file (arg) | go2rtc | pi_camera
    if args.input:
        media_source = VideoFileSource(args.input, main_size=main_size, lores_size=lores_size)
    elif app_config.get('video.source') == 'go2rtc':
        media_source = get_media_source(default_camera_id)
        # Pre-create all camera sources for multi-camera live streams
        for cam in cameras:
            get_media_source(cam['id'])
    else:
        # Pi Camera (RPi only, requires picamera2)
        from sources.media_source import MediaSource
        camera_config = app_config.get('camera') or {}
        media_source = MediaSource(main_size=main_size, lores_size=lores_size, camera_config=camera_config)

    # MQTT broker for motion/aggregator
    mqtt_broker = os.environ.get('MQTT_BROKER') or app_config.get('mqtt.broker')
    mqtt_aggregator = None
    if mqtt_broker:
        mqtt_aggregator = MQTTEventAggregator(
            broker=mqtt_broker,
            port=app_config.get('mqtt.port', 1883),
            frigate_topic=app_config.get('mqtt.frigate_topic', 'frigate/events'),
            birdnet_topic=app_config.get('mqtt.birdnet_topic', 'birdnet/sightings'),
            publish_topic=app_config.get('mqtt.publish_topic', 'birdlense/detections'),
            username=os.environ.get('MQTT_USERNAME') or app_config.get('mqtt.username'),
            password=os.environ.get('MQTT_PASSWORD') or app_config.get('mqtt.password'),
        )
        mqtt_aggregator.start()

    # Motion detector: fake (arg) | mock-mqtt | opencv | mqtt | pir
    if args.fake_motion:
        motion = args.fake_motion.lower() == 'true'
        motion_detector = FakeMotionDetector(motion=motion, wait=10)
    elif args.mock_mqtt:
        motion_detector = FakeMotionDetector(motion=True, wait=5)
        logging.info('Using --mock-mqtt: fake motion for development')
    elif app_config.get('motion.source') == 'mqtt' and mqtt_broker:
        frigate_camera_filter = (
            app_config.get('motion.frigate_camera_filter')
            or app_config.get('mqtt.frigate_camera_filter')
            or [c['id'] for c in cameras]
        )
        frigate_detector = FrigateMQTTMotionDetector(
            broker=mqtt_broker,
            port=app_config.get('mqtt.port', 1883),
            topic=app_config.get('mqtt.frigate_topic', 'frigate/events'),
            camera_filter=frigate_camera_filter,
            label_filter=set(app_config.get('motion.frigate_label_filter') or app_config.get('mqtt.frigate_label_filter') or ['bird', 'Bird']),
        )
        try:
            frigate_detector.start()
            for _ in range(5):
                if frigate_detector._connected:
                    break
                time.sleep(1)
            if not frigate_detector._connected:
                logging.warning('Frigate MQTT not connected, falling back to OpenCV')
                motion_detector = OpenCVMotionDetector(capture_fn=media_source.capture)
            else:
                motion_detector = frigate_detector
        except Exception as e:
            logging.warning(f'Frigate MQTT failed ({e}), falling back to OpenCV')
            motion_detector = OpenCVMotionDetector(capture_fn=media_source.capture)
    elif app_config.get('motion.source') == 'opencv':
        motion_detector = OpenCVMotionDetector(capture_fn=media_source.capture)
    elif app_config.get('motion.source') == 'pir':
        from motion_detectors.pir import PIRMotionDetector
        motion_detector = PIRMotionDetector()
    else:
        motion_detector = OpenCVMotionDetector(capture_fn=media_source.capture)

    decision_maker = DecisionMaker(max_record_seconds=app_config.get(
        'processor.max_record_seconds'), max_inactive_seconds=app_config.get('processor.max_inactive_seconds'))
    audio_processor = AudioProcessor(lat=app_config.get(
        'secrets.latitude'), lon=app_config.get('secrets.longitude'), spectrogram_px_per_sec=app_config.get('processor.spectrogram_px_per_sec'))
    regional_species = audio_processor.get_regional_species() + ["Squirrel"]
    regional_species = api.set_active_species(regional_species)

    # Initialize LLM verifier if API key is configured
    gemini_api_key = app_config.get('ai.gemini_api_key')
    llm_verifier = None
    if gemini_api_key:
        llm_verifier = LLMVerifier(
            api_key=gemini_api_key,
            model=app_config.get('ai.model'),
            min_confidence=app_config.get('ai.llm_verification.min_confidence'),
            max_calls_per_hour=app_config.get('ai.llm_verification.max_calls_per_hour'),
            max_calls_per_day=app_config.get('ai.llm_verification.max_calls_per_day'),
            latitude=app_config.get('secrets.latitude'),
            longitude=app_config.get('secrets.longitude'),
            log_dir=os.path.join('data', 'llm_verification_logs'),
        )

    # Configure Detection Strategy
    strategy_type = app_config.get('processor.detection_strategy', 'single_stage')
    if strategy_type == 'two_stage':
        detection_strategy = TwoStageStrategy(
            binary_model_path=app_config.get('processor.models.binary'),
            classifier_model_path=app_config.get('processor.models.classifier'),
            regional_species=regional_species
        )
    else:
        detection_strategy = SingleStageStrategy(
            model_path=app_config.get('processor.models.single_stage'),
            regional_species=regional_species
        )

    frame_processor = FrameProcessor(
        detection_strategy=detection_strategy,
        tracker=app_config.get('processor.tracker'), 
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
        if app_config.get('video.source') == 'go2rtc':
            media_source = get_media_source(camera_id)

        # Configure video sources
        output_path = get_output_path()
        video_output = f"{output_path}/video.mp4"

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
                with fps_tracker:
                    has_detections = frame_processor.run(frame)

                # Decision making
                decision_maker.update_has_detections(has_detections)
                species = decision_maker.decide_species(frame_processor.tracks)
                if species is not None:
                    api.notify_species(species)
                if decision_maker.decide_stop_recording():
                    break
            fps_tracker.log_summary()
        finally:
            media_source.stop_recording()
            end_time = datetime.now(timezone.utc)

        try:
            video_detections = decision_maker.get_results(
                frame_processor.tracks)
            audio_detections, spectrogram_path = [], None
            if video_detections:
                audio_detections, spectrogram_path = audio_processor.run(
                    video_output)
                
                # LLM validation (if enabled)
                if llm_verifier:
                    video_detections = llm_verifier.validate_detections(video_detections, start_time)

            # Merge with MQTT events (Frigate/BirdNET)
            species_mapping = app_config.get('detection.species_mapping') or {}
            merge_window = app_config.get('detection.merge_window_seconds', 5)
            dedup_window = app_config.get('detection.dedup_window_seconds', 45)
            mqtt_events = []
            if mqtt_aggregator:
                mqtt_events = mqtt_aggregator.get_events_in_window(start_time, end_time, merge_window)
            video_list = []
            for d in video_detections:
                sn = normalize(d.get('species_name') or d.get('species') or d.get('name', 'unknown'), species_mapping)
                video_list.append({**d, 'species_name': sn, 'species': sn, 'source': 'video'})
            video_detections = merge_detections(video_list, mqtt_events, start_time, end_time, merge_window, dedup_window)

            # MQTT publish for HA automations
            if mqtt_aggregator and video_detections:
                mqtt_aggregator.publish_detections(video_detections, start_time, end_time)
                    
            # Log summary without best_frame arrays
            video_summary = [{k: v for k, v in d.items() if k != 'best_frame'} for d in video_detections]
            logging.info(
                f'Processing stopped. Video Result: {video_summary}; Audio Result: {audio_detections}')
            if len(video_detections) > 0:
                api.create_video(video_detections, audio_detections, start_time,
                                 end_time, video_output, spectrogram_path)
            else:
                # no detections, delete folder
                shutil.rmtree(output_path)
        except Exception as e:
            logging.error(e)

    # Close all media sources (multi-camera cache)
    if app_config.get('video.source') == 'go2rtc':
        for src in media_sources_cache.values():
            src.close()
    else:
        media_source.close()


if __name__ == "__main__":
    main()
