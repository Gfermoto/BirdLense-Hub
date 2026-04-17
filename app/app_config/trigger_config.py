"""Helpers for grouped trigger settings and legacy fallback."""

from __future__ import annotations

from typing import Any, Callable

from app_config.scales_config import normalize_scales_source

TRIGGER_SOURCE_MQTT = "mqtt"
TRIGGER_SOURCE_ESPHOME = "esphome"


def _get_from_config(config_or_get: Any, path: str, default: Any = None) -> Any:
    if callable(config_or_get):
        try:
            return config_or_get(path, default)
        except TypeError:
            return config_or_get(path)  # type: ignore[misc]
    if hasattr(config_or_get, "get") and callable(getattr(config_or_get, "get")):
        try:
            return config_or_get.get(path, default)
        except TypeError:
            return config_or_get.get(path)  # type: ignore[misc]
    current = config_or_get
    for key in path.split("."):
        if not isinstance(current, dict):
            return default
        current = current.get(key)
        if current is None:
            return default
    return current


def _as_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    raw = str(value).strip().lower()
    if raw in {"1", "true", "yes", "on"}:
        return True
    if raw in {"0", "false", "no", "off", ""}:
        return False
    return default


def _as_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _as_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def normalize_transport_source(value: Any, default: str = TRIGGER_SOURCE_MQTT) -> str:
    src = str(value or default).strip().lower()
    if src in {TRIGGER_SOURCE_MQTT, TRIGGER_SOURCE_ESPHOME}:
        return src
    return default


def get_frigate_topic(config_or_get: Any) -> str:
    topic = str(
        _get_from_config(config_or_get, "triggers.frigate.topic")
        or _get_from_config(config_or_get, "mqtt.frigate_topic")
        or "frigate/events"
    ).strip()
    return topic or "frigate/events"


def get_birdnet_topic(config_or_get: Any) -> str:
    topic = str(
        _get_from_config(config_or_get, "integrations.birdnet.mqtt_topic")
        or _get_from_config(config_or_get, "mqtt.birdnet_topic")
        or "birdnet"
    ).strip()
    return topic or "birdnet"


def get_effective_trigger_config(
    config_or_get: Any,
    *,
    mqtt_broker: str | None = None,
) -> dict[str, dict[str, Any]]:
    broker = str(
        mqtt_broker
        if mqtt_broker is not None
        else (_get_from_config(config_or_get, "mqtt.broker") or "")
    ).strip()
    legacy_motion_source = str(
        _get_from_config(config_or_get, "motion.source", "opencv") or "opencv"
    ).strip().lower()
    has_triggers = bool(_get_from_config(config_or_get, "triggers", {}))

    opencv_enabled = _as_bool(
        _get_from_config(config_or_get, "triggers.opencv.enabled"),
        default=(legacy_motion_source in {"opencv", "frigate"} if not has_triggers else False),
    )
    frigate_enabled = _as_bool(
        _get_from_config(config_or_get, "triggers.frigate.enabled"),
        default=(bool(broker) and legacy_motion_source in {"opencv", "frigate", "mqtt", "esphome"}),
    )
    motion_sensor_enabled = _as_bool(
        _get_from_config(config_or_get, "triggers.motion_sensor.enabled"),
        default=(legacy_motion_source in {"mqtt", "esphome"} if not has_triggers else False),
    )
    motion_sensor_source = normalize_transport_source(
        _get_from_config(config_or_get, "triggers.motion_sensor.source")
        or (legacy_motion_source if legacy_motion_source in {"mqtt", "esphome"} else TRIGGER_SOURCE_MQTT),
        default=TRIGGER_SOURCE_MQTT,
    )
    scales_enabled = _as_bool(
        _get_from_config(config_or_get, "triggers.scales.enabled"),
        default=_as_bool(
            _get_from_config(config_or_get, "integrations.scales.motion_trigger_enabled"),
            False,
        ),
    )
    explicit_scales_source = _get_from_config(config_or_get, "triggers.scales.source")
    if explicit_scales_source is not None and str(explicit_scales_source).strip():
        scales_source = normalize_transport_source(
            explicit_scales_source,
            default=TRIGGER_SOURCE_MQTT,
        )
    else:
        scales_source = normalize_scales_source(
            _get_from_config(config_or_get, "integrations.scales.source")
        )

    return {
        "opencv": {
            "enabled": opencv_enabled,
            "check_every_n_frames": max(
                1,
                min(
                    30,
                    _as_int(
                        _get_from_config(config_or_get, "triggers.opencv.check_every_n_frames")
                        or _get_from_config(config_or_get, "motion.check_every_n_frames", 1),
                        1,
                    ),
                ),
            ),
            "diff_threshold": max(
                5,
                min(
                    80,
                    _as_int(
                        _get_from_config(config_or_get, "triggers.opencv.diff_threshold")
                        or _get_from_config(config_or_get, "motion.opencv_diff_threshold", 18),
                        18,
                    ),
                ),
            ),
            "min_contour_area": max(
                50,
                min(
                    20000,
                    _as_int(
                        _get_from_config(config_or_get, "triggers.opencv.min_contour_area")
                        or _get_from_config(config_or_get, "motion.opencv_min_contour_area", 240),
                        240,
                    ),
                ),
            ),
        },
        "frigate": {
            "enabled": frigate_enabled,
            "topic": get_frigate_topic(config_or_get),
            "camera_filter": _get_from_config(config_or_get, "motion.frigate_camera_filter", []) or [],
            "label_filter": _get_from_config(config_or_get, "motion.frigate_label_filter", []) or [],
            "label_exclude": _get_from_config(config_or_get, "motion.frigate_label_exclude", []) or [],
            "trigger_on_tracked_object": _as_bool(
                _get_from_config(config_or_get, "motion.frigate_trigger_on_tracked_object"),
                True,
            ),
            "min_trigger_score": max(
                0.0,
                _as_float(
                    _get_from_config(config_or_get, "motion.frigate_min_trigger_score", 0.5),
                    0.5,
                ),
            ),
        },
        "motion_sensor": {
            "enabled": motion_sensor_enabled,
            "source": motion_sensor_source,
            "mqtt_topic": str(
                _get_from_config(config_or_get, "triggers.motion_sensor.mqtt_topic")
                or _get_from_config(config_or_get, "motion.mqtt_topic")
                or ""
            ).strip(),
            "esphome_url": str(
                _get_from_config(config_or_get, "triggers.motion_sensor.esphome_url")
                or _get_from_config(config_or_get, "motion.esphome_url")
                or ""
            ).strip(),
            "esphome_sensor_id": str(
                _get_from_config(config_or_get, "triggers.motion_sensor.esphome_sensor_id")
                or _get_from_config(config_or_get, "motion.esphome_sensor_id")
                or ""
            ).strip(),
        },
        "scales": {
            "enabled": scales_enabled,
            "source": scales_source,
            "motion_trigger_min_delta_kg": max(
                0.001,
                _as_float(
                    _get_from_config(config_or_get, "triggers.scales.motion_trigger_min_delta_kg")
                    or _get_from_config(
                        config_or_get, "integrations.scales.motion_trigger_min_delta_kg", 0.02
                    ),
                    0.02,
                ),
            ),
            "motion_trigger_debounce_seconds": max(
                0.2,
                _as_float(
                    _get_from_config(config_or_get, "triggers.scales.motion_trigger_debounce_seconds")
                    or _get_from_config(
                        config_or_get, "integrations.scales.motion_trigger_debounce_seconds", 1.5
                    ),
                    1.5,
                ),
            ),
            "mqtt_topic_prefix": str(
                _get_from_config(config_or_get, "integrations.scales.mqtt_topic_prefix") or ""
            ).strip(),
            "mqtt_topic": str(
                _get_from_config(config_or_get, "integrations.scales.mqtt_topic") or ""
            ).strip(),
            "mqtt_bird_present_topic": str(
                _get_from_config(config_or_get, "integrations.scales.mqtt_bird_present_topic") or ""
            ).strip(),
            "mqtt_command_topic": str(
                _get_from_config(config_or_get, "integrations.scales.mqtt_command_topic") or ""
            ).strip(),
            "esphome_url": str(
                _get_from_config(config_or_get, "integrations.scales.esphome_url") or ""
            ).strip(),
            "esphome_weight_sensor_id": str(
                _get_from_config(config_or_get, "integrations.scales.esphome_weight_sensor_id") or ""
            ).strip(),
            "esphome_bird_present_sensor_id": str(
                _get_from_config(config_or_get, "integrations.scales.esphome_bird_present_sensor_id") or ""
            ).strip(),
            "esphome_tare_button_id": str(
                _get_from_config(config_or_get, "integrations.scales.esphome_tare_button_id") or ""
            ).strip(),
        },
    }


def get_active_trigger_names(
    config_or_get: Any,
    *,
    mqtt_broker: str | None = None,
) -> list[str]:
    cfg = get_effective_trigger_config(config_or_get, mqtt_broker=mqtt_broker)
    active: list[str] = []
    for name in ("opencv", "frigate", "motion_sensor", "scales"):
        if cfg[name]["enabled"]:
            active.append(name)
    return active


def format_trigger_display_line(active_names: list[str]) -> str:
    """Строка как в recording_context / API ``trigger_display``: id через `` + ``."""
    if not active_names:
        return ""
    return " + ".join(active_names)


def format_motion_source_summary(active_names: list[str]) -> str:
    """Поле ``motion_source`` в статусе/трейсах: id через запятую или ``none``."""
    if not active_names:
        return "none"
    return ",".join(active_names)


def get_legacy_motion_source_label(
    config_or_get: Any,
    *,
    mqtt_broker: str | None = None,
) -> str:
    """Сводка по эффективным триггерам (без ``motion.source`` из YAML как истины)."""
    return format_motion_source_summary(
        get_active_trigger_names(config_or_get, mqtt_broker=mqtt_broker),
    )


def copy_legacy_topic_if_missing(
    dst_parent: dict[str, Any],
    dst_key: str,
    src_parent: dict[str, Any],
    src_key: str,
) -> bool:
    src_val = str(src_parent.get(src_key) or "").strip()
    dst_val = str(dst_parent.get(dst_key) or "").strip()
    if not src_val or dst_val:
        return False
    dst_parent[dst_key] = src_val
    return True
