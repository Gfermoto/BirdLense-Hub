"""Старт MQTT-агрегатора, Frigate-from-aggregator и опций весов (вынесено из main.py, tech debt #201)."""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING, Any, Optional, Tuple

from app_config.app_config import app_config
from app_config.scales_config import normalize_scales_source, scales_source_uses_mqtt
from app_config.trigger_config import get_birdnet_topic, get_effective_trigger_config, get_frigate_topic
from frigate_scope import frigate_camera_allow_ids, frigate_label_resolve_set
from processor_support import get_data_dir, heartbeat_mqtt_ref

if TYPE_CHECKING:
    from argparse import Namespace

    from mqtt_aggregator import MQTTEventAggregator


def load_scales_mqtt_topic_config() -> tuple[str, Optional[str], str]:
    """DATA_DIR, MQTT topic веса (если source MQTT-backed), unit.

    Вес: явный ``mqtt_topic`` или, если пусто, ``{mqtt_topic_prefix}/weight``.
    ``bird_present``: явный ``mqtt_bird_present_topic`` или ``{mqtt_topic_prefix}/bird_present`` при непустом префиксе.
    """
    data_dir = get_data_dir()
    scales_topic_arg: Optional[str] = None
    scales_unit_arg = "g"
    trigger_cfg = get_effective_trigger_config(app_config)
    scales_cfg = trigger_cfg.get("scales") or {}
    if app_config.get("integrations.scales.enabled"):
        scales_unit_arg = (app_config.get("integrations.scales.unit") or "g").strip().lower() or "g"
        src = normalize_scales_source(scales_cfg.get("source") or app_config.get("integrations.scales.source"))
        if scales_source_uses_mqtt(src):
            mq_st = (app_config.get("integrations.scales.mqtt_topic") or "").strip()
            prefix = (app_config.get("integrations.scales.mqtt_topic_prefix") or "").strip().strip("/")
            if mq_st:
                scales_topic_arg = mq_st
            elif prefix:
                scales_topic_arg = f"{prefix}/weight"
    return data_dir, scales_topic_arg, scales_unit_arg


def scales_mqtt_bird_present_topic() -> Optional[str]:
    """Топик присутствия птицы: явный ``mqtt_bird_present_topic`` или ``{prefix}/bird_present``."""
    if not app_config.get("integrations.scales.enabled"):
        return None
    scales_cfg = get_effective_trigger_config(app_config).get("scales") or {}
    if not scales_source_uses_mqtt(scales_cfg.get("source") or app_config.get("integrations.scales.source")):
        return None
    explicit = (app_config.get("integrations.scales.mqtt_bird_present_topic") or "").strip()
    if explicit:
        return explicit
    prefix = (app_config.get("integrations.scales.mqtt_topic_prefix") or "").strip().strip("/")
    if not prefix:
        return None
    return f"{prefix}/bird_present"


def _frigate_camera_filter_list(
    cameras: list,
    *,
    config: Optional[Any] = None,
) -> list:
    """Список id камер; скаляр YAML (str) → один элемент, не посимвольный iterable.

    Пустой список в YAML ``[]`` трактуется как «не задано» — те же id, что и при
    ``None``: только камеры из ``video.cameras`` (не «любая камера на брокере»).
    """
    cfg = config if config is not None else app_config
    return frigate_camera_allow_ids(cameras, cfg)


def _frigate_label_set(triggers_key: str, mqtt_key: str, default: list) -> set:
    """Resolve label set. Empty list ``[]`` is explicit (wildcard: match any label), not falsy.

    Precedence: ``triggers.frigate.*`` if the key resolves in merged config (including ``[]``),
    else ``mqtt.*``, else ``default``.
    """
    return frigate_label_resolve_set(triggers_key, mqtt_key, default, app_config)


def frigate_filters_for_cameras(cameras: list) -> tuple[Any, set, set]:
    camera_filter = _frigate_camera_filter_list(cameras)
    label_filter = _frigate_label_set(
        "triggers.frigate.label_filter",
        "mqtt.frigate_label_filter",
        [],
    )
    label_exclude = _frigate_label_set(
        "triggers.frigate.label_exclude",
        "mqtt.frigate_label_exclude",
        [],
    )
    return camera_filter, label_filter, label_exclude


def start_mqtt_aggregator_session(
    args: Namespace,
    *,
    mqtt_broker: str,
    frigate_camera_filter,
    frigate_label_filter: set,
    frigate_label_exclude: set,
    scales_topic_arg: Optional[str],
    scales_unit_arg: str,
    data_dir: str,
) -> Tuple[MQTTEventAggregator, Optional[Any], Any]:
    """Поднимает MQTTEventAggregator и связывает FrigateMotionFromAggregator. Возвращает (aggregator, scale_pending, frigate_detector)."""
    from motion_detectors.frigate_mqtt import FrigateMotionFromAggregator
    from motion_detectors.scale_weight_motion import ScaleWeightMotionPending
    from mqtt_aggregator import MQTTEventAggregator

    trigger_cfg = get_effective_trigger_config(app_config, mqtt_broker=mqtt_broker)
    scales_cfg = trigger_cfg.get("scales") or {}
    frigate_detector = FrigateMotionFromAggregator(None, frigate_camera_filter, frigate_label_filter)
    on_frigate_motion = frigate_detector.get_on_frigate_motion_tuple()

    mqtt_client_id = None
    if args.input:
        mqtt_client_id = os.environ.get("MQTT_CLIENT_ID") or "birdlense_aggregator_test"

    _raw_hist = app_config.get("integrations.scales.history_max_lines")
    try:
        scales_hist_lines = int(_raw_hist) if _raw_hist not in (None, "") else 10000
    except (TypeError, ValueError):
        scales_hist_lines = 10000
    if scales_hist_lines < 100:
        scales_hist_lines = 100

    scale_weight_motion_pending = None
    scale_motion_cb = None
    scale_motion_min = None
    scale_motion_debounce = 1.5
    if scales_topic_arg and bool(scales_cfg.get("enabled")):
        scale_weight_motion_pending = ScaleWeightMotionPending()
        scale_motion_cb = scale_weight_motion_pending.fire
        try:
            scale_motion_min = float(scales_cfg.get("motion_trigger_min_delta_kg") or 0.02)
        except (TypeError, ValueError):
            scale_motion_min = 0.02
        if scale_motion_min <= 0:
            scale_motion_min = None
            scale_motion_cb = None
            scale_weight_motion_pending = None
        try:
            scale_motion_debounce = float(scales_cfg.get("motion_trigger_debounce_seconds") or 1.5)
        except (TypeError, ValueError):
            scale_motion_debounce = 1.5
        if scale_weight_motion_pending:
            logging.info(
                "Scales: motion trigger on weight delta >= %s kg (debounce %ss)",
                scale_motion_min,
                scale_motion_debounce,
            )

    bird_present_topic = scales_mqtt_bird_present_topic()
    scales_data_for_file = data_dir if (scales_topic_arg or bird_present_topic) else None
    try:
        mqtt_max_events = int(app_config.get("mqtt.max_events", 500) or 500)
    except (TypeError, ValueError):
        mqtt_max_events = 500
    try:
        mqtt_publish_queue_max = int(app_config.get("mqtt.publish_queue_max", 2000) or 2000)
    except (TypeError, ValueError):
        mqtt_publish_queue_max = 2000
    try:
        mqtt_feeder_scale_queue_max = int(app_config.get("mqtt.feeder_scale_queue_max", 200) or 200)
    except (TypeError, ValueError):
        mqtt_feeder_scale_queue_max = 200
    try:
        mqtt_reconnect_jitter_ratio = float(app_config.get("mqtt.reconnect_jitter_ratio", 0.15) or 0.15)
    except (TypeError, ValueError):
        mqtt_reconnect_jitter_ratio = 0.15

    mqtt_aggregator = MQTTEventAggregator(
        broker=mqtt_broker,
        port=app_config.get("mqtt.port", 1883),
        frigate_topic=get_frigate_topic(app_config),
        birdnet_topic=get_birdnet_topic(app_config),
        publish_topic=app_config.get("mqtt.publish_topic", "birdlense/detections"),
        username=os.environ.get("MQTT_USERNAME") or app_config.get("mqtt.username"),
        password=os.environ.get("MQTT_PASSWORD") or app_config.get("mqtt.password"),
        max_events=mqtt_max_events,
        publish_queue_max=mqtt_publish_queue_max,
        feeder_scale_queue_max=mqtt_feeder_scale_queue_max,
        on_frigate_motion=on_frigate_motion,
        frigate_label_exclude=list(frigate_label_exclude),
        client_id=mqtt_client_id,
        ha_discovery=app_config.get("mqtt.ha_discovery", True),
        base_url=app_config.get("notifications.base_url", ""),
        reconnect_min_delay=app_config.get("mqtt.reconnect_min_delay", 5),
        reconnect_max_delay=app_config.get("mqtt.reconnect_max_delay", 300),
        reconnect_jitter_ratio=mqtt_reconnect_jitter_ratio,
        scales_topic=scales_topic_arg,
        scales_bird_present_topic=bird_present_topic,
        scales_data_dir=scales_data_for_file,
        fifo_snapshot_data_dir=data_dir,
        scales_unit=scales_unit_arg,
        scales_history_max_lines=scales_hist_lines,
        scale_motion_trigger_cb=scale_motion_cb,
        scale_motion_min_delta_kg=scale_motion_min,
        scale_motion_debounce_seconds=scale_motion_debounce,
    )
    frigate_detector._aggregator = mqtt_aggregator
    mqtt_aggregator.start()
    heartbeat_mqtt_ref[0] = mqtt_aggregator

    return mqtt_aggregator, scale_weight_motion_pending, frigate_detector
