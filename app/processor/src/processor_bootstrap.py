"""Сборка зависимостей процессора и главный цикл движения (вынесено из main.py)."""

from __future__ import annotations

import logging
import os
from argparse import ArgumentParser, Namespace
from dataclasses import dataclass

from api import API
from app_config.app_config import app_config
from detection_stack import build_detection_stack
from fps_tracker import FPSTracker
from media_runtime import ProcessorMediaSetup, setup_processor_media
from motion_runtime import build_processor_motion_detector
from mqtt_runtime import (
    frigate_filters_for_cameras,
    load_scales_mqtt_topic_config,
    start_mqtt_aggregator_session,
)
from processor_support import check_restart_flag
from recording_session import MotionRecordingSession


@dataclass(frozen=True)
class ProcessorRunContext:
    """Всё, что нужно главному циклу и корректному закрытию медиа."""

    session: MotionRecordingSession
    media_setup: ProcessorMediaSetup


def parse_processor_args(argv: list[str] | None = None) -> Namespace:
    parser = ArgumentParser(description='Smart bird feeder program')
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
    return parser.parse_args(argv)


def build_processor_run_context(args: Namespace) -> ProcessorRunContext:
    api = API()
    main_size = (
        app_config.get('video.video_width', 1280),
        app_config.get('video.video_height', 720),
    )
    lores_size = (640, 640)

    media_setup = setup_processor_media(args, main_size, lores_size, api)

    mqtt_broker = os.environ.get('MQTT_BROKER') or app_config.get('mqtt.broker')
    mqtt_aggregator = None
    scale_weight_motion_pending = None
    frigate_detector = None
    _data_dir, scales_topic_arg, scales_unit_arg = load_scales_mqtt_topic_config()
    frigate_camera_filter, frigate_label_filter, frigate_label_exclude = (
        frigate_filters_for_cameras(media_setup.cameras)
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
        media_source=media_setup.media_source,
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
        warn_two_stage_fallback=False,
    )
    regional_species = app_config.get('processor.regional_species') or []
    if regional_species:
        api.set_active_species(regional_species)

    tracker = app_config.get('processor.tracker') or 'bytetrack.yaml'
    logging.info('Using tracker: %s', tracker)
    fps_tracker = FPSTracker()

    media_source_ref = [media_setup.media_source]
    session = MotionRecordingSession(
        args=args,
        api=api,
        motion_detector=motion_detector,
        mqtt_aggregator=mqtt_aggregator,
        frame_processor=frame_processor,
        decision_maker=decision_maker,
        merged_overrides=merged_overrides,
        media_source_ref=media_source_ref,
        get_media_source=media_setup.get_media_source,
        default_camera_id=media_setup.default_camera_id,
        scales_topic_arg=scales_topic_arg,
        data_dir=_data_dir,
        fps_tracker=fps_tracker,
    )
    return ProcessorRunContext(session=session, media_setup=media_setup)


def run_motion_loop(ctx: ProcessorRunContext) -> None:
    """Бесконечный цикл движения; выход при ``session.run()`` → True (режим файла) или SystemExit."""
    while True:
        check_restart_flag()
        if not ctx.session.motion_detector.detect():
            continue
        ctx.session.api.notify_motion()
        if ctx.session.run():
            break


def close_processor_media(ctx: ProcessorRunContext) -> None:
    if app_config.get('video.source') == 'go2rtc':
        for src in ctx.media_setup.media_sources_cache.values():
            src.close()
    else:
        ctx.media_setup.media_source.close()
