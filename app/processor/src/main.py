import argparse
import logging
import os
from datetime import datetime, timezone

from api import API
from app_config.app_config import app_config
from birdnet_mqtt_confidence import merge_birdnet_mqtt_bias_into_overrides
from detection_stack import build_detection_stack
from fps_tracker import FPSTracker
from media_runtime import setup_processor_media
from motion_runtime import build_processor_motion_detector
from mqtt_runtime import (
    frigate_filters_for_cameras,
    load_scales_mqtt_topic_config,
    start_mqtt_aggregator_session,
)
from processor_support import (
    check_restart_flag,
    get_output_path,
    processor_status,
    start_heartbeat_daemon,
)
from recording_finalize import finalize_motion_recording


def main():
    start_heartbeat_daemon()

    parser = argparse.ArgumentParser(description='Smart bird feeder program')
    parser.add_argument(
        'input',
        type=str,
        nargs='?',
        help='Input source, camera/video file',
    )
    parser.add_argument(
        '--fake-motion',
        type=str,
        choices=['true', 'false'],
        help='Use fake motion detector with motion or not',
    )
    parser.add_argument(
        '--mock-mqtt',
        action='store_true',
        help='Development: fake motion instead of MQTT (no broker needed)',
    )
    args = parser.parse_args()

    api = API()
    main_size = (
        app_config.get('video.video_width', 1280),
        app_config.get('video.video_height', 720),
    )
    lores_size = (640, 640)

    ms = setup_processor_media(args, main_size, lores_size, api)
    media_source = ms.media_source
    get_media_source = ms.get_media_source
    media_sources_cache = ms.media_sources_cache
    default_camera_id = ms.default_camera_id

    mqtt_broker = os.environ.get('MQTT_BROKER') or app_config.get('mqtt.broker')
    mqtt_aggregator = None
    scale_weight_motion_pending = None
    frigate_detector = None
    _data_dir, scales_topic_arg, scales_unit_arg = load_scales_mqtt_topic_config()
    frigate_camera_filter, frigate_label_filter, frigate_label_exclude = (
        frigate_filters_for_cameras(ms.cameras)
    )
    use_frigate_from_aggregator = bool(mqtt_broker)
    if mqtt_broker:
        mqtt_aggregator, scale_weight_motion_pending, frigate_detector = (
            start_mqtt_aggregator_session(
                args,
                mqtt_broker=mqtt_broker,
                frigate_camera_filter=frigate_camera_filter,
                frigate_label_filter=frigate_label_filter,
                frigate_label_exclude=frigate_label_exclude,
                scales_topic_arg=scales_topic_arg,
                scales_unit_arg=scales_unit_arg,
                data_dir=_data_dir,
            )
        )

    motion_detector = build_processor_motion_detector(
        args,
        media_source=media_source,
        mqtt_broker=mqtt_broker,
        mqtt_aggregator=mqtt_aggregator,
        frigate_detector=frigate_detector,
        scale_weight_motion_pending=scale_weight_motion_pending,
        use_frigate_from_aggregator=use_frigate_from_aggregator,
        frigate_camera_filter=frigate_camera_filter,
        frigate_label_filter=frigate_label_filter,
    )

    frame_processor, decision_maker, merged_overrides = build_detection_stack(
        app_config,
        save_images=bool(app_config.get('processor.save_images')),
        warn_two_stage_fallback=True,
    )
    regional_species = app_config.get('processor.regional_species') or []
    if regional_species:
        api.set_active_species(regional_species)

    tracker = app_config.get('processor.tracker') or 'bytetrack.yaml'
    logging.info('Using tracker: %s', tracker)
    fps_tracker = FPSTracker()

    while True:
        check_restart_flag()
        if not motion_detector.detect():
            continue
        api.notify_motion()

        session_overrides = merge_birdnet_mqtt_bias_into_overrides(
            merged_overrides, app_config, mqtt_aggregator
        )
        decision_maker.species_confidence_overrides = session_overrides

        camera_id = (
            getattr(motion_detector, 'get_triggered_camera', lambda: None)()
            or default_camera_id
        )
        if not args.input and app_config.get('video.source') == 'go2rtc':
            media_source = get_media_source(camera_id)

        output_path_physical, output_path_logical = get_output_path()
        video_output = os.path.join(output_path_physical, 'video.mp4')
        video_path_for_api = f'{output_path_logical}/video.mp4'

        media_source.start_recording(video_output)

        logging.info(
            'Motion detected. Processing started. Recording video and audio to "%s"',
            video_output,
        )
        start_time = datetime.now(timezone.utc)

        try:
            frame_processor.reset()
            decision_maker.reset()
            fps_tracker.reset()
            while True:
                frame = media_source.capture()
                if frame is None:
                    break
                processor_status['last_video_ok_at'] = (
                    datetime.now(timezone.utc).isoformat()
                )
                frame_time = getattr(
                    media_source, 'get_frame_time', lambda: None
                )()
                with fps_tracker:
                    has_detections = frame_processor.run(
                        frame, frame_time=frame_time
                    )
                processor_status['last_yolo_ok_at'] = (
                    datetime.now(timezone.utc).isoformat()
                )

                decision_maker.update_has_detections(has_detections)
                decision_maker.get_first_species_result(
                    frame_processor.tracks,
                )
                if decision_maker.decide_stop_recording():
                    break
            fps_tracker.log_summary()
        finally:
            media_source.stop_recording()
            end_time = datetime.now(timezone.utc)

        try:
            finalize_motion_recording(
                api,
                motion_detector,
                mqtt_aggregator,
                frame_processor,
                decision_maker,
                start_time=start_time,
                end_time=end_time,
                output_path_physical=output_path_physical,
                output_path_logical=output_path_logical,
                video_output=video_output,
                video_path_for_api=video_path_for_api,
                scales_topic_arg=scales_topic_arg,
                data_dir=_data_dir,
            )
        except Exception as e:
            logging.error(e)

        if args.input:
            break

    if app_config.get('video.source') == 'go2rtc':
        for src in media_sources_cache.values():
            src.close()
    else:
        media_source.close()


if __name__ == '__main__':
    main()
