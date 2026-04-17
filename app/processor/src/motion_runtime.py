"""Сборка motion detector для процессора (tech debt #201)."""

from __future__ import annotations

import logging
import os
import time
from typing import Any, Optional

from app_config.app_config import app_config
from app_config.trigger_config import get_active_trigger_names, get_effective_trigger_config
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
    if (app_config.get("video.source") or "").strip().lower() == "file":
        logging.info("Motion: file source mode -> always-on synthetic trigger")
        return FakeMotionDetector(motion=True, wait=1)

    if args.fake_motion:
        motion = args.fake_motion.lower() == "true"
        return FakeMotionDetector(motion=motion, wait=10)
    if args.mock_mqtt:
        logging.info("Using --mock-mqtt: fake motion for development")
        return FakeMotionDetector(motion=True, wait=5)
    trigger_config = get_effective_trigger_config(app_config, mqtt_broker=mqtt_broker)
    frigate_cfg = trigger_config.get("frigate") or {}
    motion_sensor_cfg = trigger_config.get("motion_sensor") or {}
    scales_cfg = trigger_config.get("scales") or {}

    active_frigate_detector = None
    if bool(frigate_cfg.get("enabled")) and use_frigate_from_aggregator and mqtt_aggregator:
        active_frigate_detector = frigate_detector
        for _ in range(5):
            if mqtt_aggregator.is_mqtt_live():
                break
            time.sleep(1)
        if mqtt_aggregator.is_mqtt_live():
            fc = list(frigate_camera_filter) if frigate_camera_filter else "any"
            logging.info(
                "Motion: Frigate (cameras=%s labels=%s)",
                fc,
                list(frigate_label_filter),
            )
        else:
            logging.warning(
                "Frigate MQTT not live yet after startup wait; detector will keep retrying",
            )

    if bool(scales_cfg.get("enabled")) and str(scales_cfg.get("source") or "") == "esphome":
        scale_weight_motion_pending = _build_esphome_scale_motion_detector(scales_cfg)

    motion_detector = build_motion_detector(
        trigger_config=trigger_config,
        media_source=media_source,
        frigate_detector=active_frigate_detector,
        mqtt_broker=mqtt_broker,
        mqtt_port=app_config.get("mqtt.port", 1883),
        mqtt_username=os.environ.get("MQTT_USERNAME") or app_config.get("mqtt.username"),
        mqtt_password=os.environ.get("MQTT_PASSWORD") or app_config.get("mqtt.password"),
        scales_detector=scale_weight_motion_pending,
    )

    active_names = get_active_trigger_names(app_config, mqtt_broker=mqtt_broker)
    if active_names:
        logging.info("Motion grouped triggers active: %s", ", ".join(active_names))
    if bool(motion_sensor_cfg.get("enabled")) and str(motion_sensor_cfg.get("source") or "") == "esphome":
        sensor_id = str(motion_sensor_cfg.get("esphome_sensor_id") or "").strip()
        esphome_url = str(motion_sensor_cfg.get("esphome_url") or "").strip()
        if not (sensor_id and esphome_url):
            logging.warning("Grouped motion sensor=esphome but URL/sensor empty")
    if bool(scales_cfg.get("enabled")) and str(scales_cfg.get("source") or "") == "esphome":
        scale_url = str(scales_cfg.get("esphome_url") or "").strip()
        scale_sensor = str(scales_cfg.get("esphome_weight_sensor_id") or "").strip()
        if not (scale_url and scale_sensor):
            logging.warning("Grouped scales=esphome but URL/weight sensor empty")

    return motion_detector


def _build_esphome_scale_motion_detector(scales_cfg: dict[str, Any]) -> Any:
    from motion_detectors.esphome_scale import ESPHomeScaleMotionDetector

    esphome_url = str(scales_cfg.get("esphome_url") or "").strip()
    weight_sensor_id = str(scales_cfg.get("esphome_weight_sensor_id") or "").strip()
    if not (esphome_url and weight_sensor_id):
        return None

    unit = str(app_config.get("integrations.scales.unit") or "g").strip().lower() or "g"
    min_delta_kg = float(scales_cfg.get("motion_trigger_min_delta_kg") or 0.02)
    if unit == "g":
        min_delta = min_delta_kg * 1000.0
    else:
        min_delta = min_delta_kg
    return ESPHomeScaleMotionDetector(
        url=esphome_url,
        sensor_id=weight_sensor_id,
        min_delta=min_delta,
        debounce_seconds=float(scales_cfg.get("motion_trigger_debounce_seconds") or 1.5),
    )
