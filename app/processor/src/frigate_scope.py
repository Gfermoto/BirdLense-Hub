"""Правила Frigate для камер и меток из YAML (без импорта MQTT/paho)."""

from __future__ import annotations

from typing import Any

from app_config.trigger_config import _get_from_config


def frigate_label_resolve_set(
    triggers_key: str,
    mqtt_key: str,
    default: list,
    config: Any,
) -> set:
    """Пустой список ``[]`` у ``triggers.frigate.*`` — wildcard (любая метка)."""
    triggers_raw = _get_from_config(config, triggers_key)
    if triggers_raw is not None:
        if isinstance(triggers_raw, str):
            s = triggers_raw.strip()
            return {s} if s else set(default)
        return set(triggers_raw)
    mqtt_raw = _get_from_config(config, mqtt_key)
    if mqtt_raw is not None:
        if isinstance(mqtt_raw, str):
            s = mqtt_raw.strip()
            return {s} if s else set(default)
        return set(mqtt_raw)
    return set(default)


def frigate_camera_allow_ids(cameras: list, config: Any) -> list:
    """Те же правила, что ``mqtt_runtime._frigate_camera_filter_list``.

    Пустой ``[]`` в YAML = не задано → stream_name из ``cameras`` (имя Frigate/Go2RTC камеры).
    Сначала ``triggers.frigate.camera_filter``,
    затем ``mqtt.frigate_camera_filter``.
    """
    raw = _get_from_config(config, "triggers.frigate.camera_filter")
    if raw is None:
        raw = _get_from_config(config, "mqtt.frigate_camera_filter")
    if raw is None:
        return [c.get("stream_name") or c["id"] for c in cameras]
    if isinstance(raw, str):
        s = raw.strip()
        return [s] if s else [c.get("stream_name") or c["id"] for c in cameras]
    if isinstance(raw, (list, tuple)):
        if not raw:
            return [c.get("stream_name") or c["id"] for c in cameras]
        return list(raw)
    return [c.get("stream_name") or c["id"] for c in cameras]
