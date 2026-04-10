"""Сборка motion detector для процессора (tech debt #201)."""
from __future__ import annotations

import logging
import os
import time
from typing import Any, Optional

from app_config.app_config import app_config
from motion_detectors.fake import FakeMotionDetector


def build_processor_motion_detector(
    args: Any,
    *,
    media_source: Any,
    mqtt_broker: Optional[str],
    mqtt_aggregator: Any,
    frigate_detector: Any,
    scale_weight_motion_pending: Any,
    use_frigate_from_aggregator: bool,
    frigate_camera_filter: Any,
    frigate_label_filter: Any,
) -> Any:
    """Fake / PIR / Frigate+stack через factory (как в main ранее)."""
    from motion_detectors.factory import build_motion_detector

    # File test mode: no live sensor is required, run processing continuously.
    # Frigate/MQTT wiring still starts in background and can be used for logs/merge.
    if (app_config.get('video.source') or '').strip().lower() == 'file':
        logging.info('Motion: file source mode -> always-on synthetic trigger')
        return FakeMotionDetector(motion=True, wait=1)

    if args.fake_motion:
        motion = args.fake_motion.lower() == 'true'
        return FakeMotionDetector(motion=motion, wait=10)
    if args.mock_mqtt:
        logging.info('Using --mock-mqtt: fake motion for development')
        return FakeMotionDetector(motion=True, wait=5)
    if app_config.get('motion.source') == 'pir':
        from motion_detectors.pir import PIRMotionDetector

        return PIRMotionDetector()

    primary = None
    if use_frigate_from_aggregator and mqtt_aggregator:
        primary = frigate_detector
        for _ in range(5):
            if mqtt_aggregator.is_mqtt_live():
                break
            time.sleep(1)
        if mqtt_aggregator.is_mqtt_live():
            fc = (
                list(frigate_camera_filter) if frigate_camera_filter else 'any'
            )
            logging.info(
                'Motion: Frigate (cameras=%s labels=%s)',
                fc,
                list(frigate_label_filter),
            )
        else:
            logging.warning(
                'Frigate MQTT not live yet after startup wait; '
                'detector will keep retrying',
            )

    add_source = app_config.get('motion.source', 'frigate')
    check_n = app_config.get('motion.check_every_n_frames', 1)
    try:
        oc_thresh = int(app_config.get('motion.opencv_diff_threshold', 25))
    except (TypeError, ValueError):
        oc_thresh = 25
    try:
        oc_area = int(app_config.get('motion.opencv_min_contour_area', 500))
    except (TypeError, ValueError):
        oc_area = 500
    oc_thresh = max(5, min(oc_thresh, 80))
    oc_area = max(50, min(oc_area, 20000))
    esphome_url = (
        os.environ.get('MOTION_ESPHOME_URL')
        or app_config.get('motion.esphome_url', '')
    ).strip()
    esphome_sensor = (
        os.environ.get('MOTION_ESPHOME_SENSOR')
        or app_config.get('motion.esphome_sensor_id', '')
    ).strip()
    or_extras = None
    if scale_weight_motion_pending and primary:
        or_extras = [scale_weight_motion_pending]
    motion_detector = build_motion_detector(
        motion_source=add_source,
        media_source=media_source,
        primary=primary,
        mqtt_broker=mqtt_broker,
        mqtt_topic=app_config.get('motion.mqtt_topic', '').strip(),
        mqtt_port=app_config.get('mqtt.port', 1883),
        mqtt_username=os.environ.get('MQTT_USERNAME')
        or app_config.get('mqtt.username'),
        mqtt_password=os.environ.get('MQTT_PASSWORD')
        or app_config.get('mqtt.password'),
        esphome_url=esphome_url,
        esphome_sensor=esphome_sensor,
        check_every_n_frames=check_n,
        or_extras=or_extras,
        opencv_threshold=oc_thresh,
        opencv_min_contour_area=oc_area,
    )
    if add_source == 'frigate':
        if primary:
            logging.info(
                'Motion: Frigate MQTT + OpenCV parallel/fallback '
                '(check_every_n_frames=%s)',
                check_n,
            )
        else:
            logging.warning(
                'Motion: Frigate selected but MQTT/Frigate client inactive — '
                'using OpenCV only (check_every_n_frames=%s)',
                check_n,
            )
    elif add_source == 'opencv':
        logging.info(
            'Motion: OpenCV (check_every_n_frames=%s)',
            check_n,
        )
    elif (
        add_source == 'mqtt'
        and mqtt_broker
        and (app_config.get('motion.mqtt_topic') or '').strip()
    ):
        logging.info('Motion: + MQTT binary (parallel)')
    elif add_source == 'esphome':
        if esphome_url and esphome_sensor:
            logging.info('Motion: + ESPHome (parallel)')
        else:
            logging.warning('motion.source=esphome but URL/sensor empty')

    return motion_detector
