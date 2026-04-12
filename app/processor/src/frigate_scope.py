"""Правила Frigate для камер и меток из YAML (без импорта MQTT/paho)."""


def frigate_label_resolve_set(motion_key: str, mqtt_key: str, default: list, config) -> set:
    """Пустой список ``[]`` у motion — явный wildcard (любая метка)."""
    motion_raw = config.get(motion_key)
    if motion_raw is not None:
        if isinstance(motion_raw, str):
            s = motion_raw.strip()
            return {s} if s else set(default)
        return set(motion_raw)
    mqtt_raw = config.get(mqtt_key)
    if mqtt_raw is not None:
        if isinstance(mqtt_raw, str):
            s = mqtt_raw.strip()
            return {s} if s else set(default)
        return set(mqtt_raw)
    return set(default)


def frigate_camera_allow_ids(cameras: list, config) -> list:
    """Те же правила, что ``mqtt_runtime._frigate_camera_filter_list``.

    Пустой список в YAML ``[]`` = не задано → id из ``cameras`` (валидные камеры Hub).
    Ключ ``motion.*`` читается отдельно от ``mqtt.*``, чтобы явный ``[]`` не
    подменялся через ``or`` на значение из mqtt.
    """
    raw = config.get("motion.frigate_camera_filter")
    if raw is None:
        raw = config.get("mqtt.frigate_camera_filter")
    if raw is None:
        return [c["id"] for c in cameras]
    if isinstance(raw, str):
        s = raw.strip()
        return [s] if s else [c["id"] for c in cameras]
    if isinstance(raw, (list, tuple)):
        if not raw:
            return [c["id"] for c in cameras]
        return list(raw)
    return [c["id"] for c in cameras]
