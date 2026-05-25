"""Grouped trigger helpers: ``triggers.*`` is the single source after merge/load."""

from __future__ import annotations

import logging
from typing import Any

from app_config.scales_config import normalize_scales_source, scales_source_uses_mqtt

logger = logging.getLogger(__name__)

TRIGGER_SOURCE_MQTT = "mqtt"
TRIGGER_SOURCE_ESPHOME = "esphome"


def _get_from_config(config_or_get: Any, path: str, default: Any = None) -> Any:
    if callable(config_or_get):
        try:
            return config_or_get(path, default)
        except TypeError:
            return config_or_get(path)  # type: ignore[misc]
    if isinstance(config_or_get, dict):
        cur: Any = config_or_get
        for key in path.split("."):
            if not isinstance(cur, dict):
                return default
            if key not in cur:
                return config_or_get.get(path, default)
            cur = cur[key]
        return cur
    if hasattr(config_or_get, "get") and callable(getattr(config_or_get, "get")):
        try:
            return config_or_get.get(path, default)
        except TypeError:
            return config_or_get.get(path)  # type: ignore[misc]
    return default


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


def _fold_motion_fields_into_triggers(motion: dict[str, Any], triggers: dict[str, Any]) -> None:
    if not motion:
        return
    op = triggers.setdefault("opencv", {})
    fr = triggers.setdefault("frigate", {})
    ms = triggers.setdefault("motion_sensor", {})
    pairs: tuple[tuple[dict[str, Any], str, str], ...] = (
        (fr, "camera_filter", "frigate_camera_filter"),
        (fr, "label_filter", "frigate_label_filter"),
        (fr, "label_exclude", "frigate_label_exclude"),
        (fr, "trigger_on_tracked_object", "frigate_trigger_on_tracked_object"),
        (fr, "min_trigger_score", "frigate_min_trigger_score"),
        (fr, "min_trigger_score_by_camera", "frigate_min_trigger_score_by_camera"),
        (op, "check_every_n_frames", "check_every_n_frames"),
        (op, "diff_threshold", "opencv_diff_threshold"),
        (op, "min_contour_area", "opencv_min_contour_area"),
        (ms, "mqtt_topic", "mqtt_topic"),
        (ms, "esphome_url", "esphome_url"),
        (ms, "esphome_sensor_id", "esphome_sensor_id"),
    )
    for dst, dk, sk in pairs:
        if sk in motion:
            dst[dk] = motion[sk]


def _apply_legacy_motion_source_flags(source_raw: Any, triggers: dict[str, Any]) -> None:
    src = str(source_raw or "").strip().lower()
    if not src:
        return
    op = triggers.setdefault("opencv", {})
    fr = triggers.setdefault("frigate", {})
    ms = triggers.setdefault("motion_sensor", {})
    if src == "frigate":
        fr["enabled"] = True
        op["enabled"] = True
    elif src == "opencv":
        op["enabled"] = True
    elif src == "mqtt":
        ms["enabled"] = True
        ms["source"] = TRIGGER_SOURCE_MQTT
    elif src == "esphome":
        ms["enabled"] = True
        ms["source"] = TRIGGER_SOURCE_ESPHOME


def fold_legacy_motion_out_of_merged_config(merged: dict[str, Any]) -> None:
    """Fold top-level ``motion`` into ``triggers`` and drop ``motion`` from merged YAML snapshot.

    Не вызываем ``_apply_legacy_motion_source_flags`` здесь: при merge с ``default_config``
    старый ``motion.source: frigate`` перезаписывал ``triggers.frigate.enabled`` из user YAML
    на каждом старте. Флаги enabled для legacy остаются только в ``migrate_legacy_motion_block``.
    """
    motion = merged.get("motion")
    if not isinstance(motion, dict) or not motion:
        return
    triggers = merged.setdefault("triggers", {})
    _fold_motion_fields_into_triggers(motion, triggers)
    del merged["motion"]


def fold_motion_settings_patch_into_triggers(updates: dict[str, Any]) -> None:
    """Fold UI ``motion.*`` PATCH fields into ``triggers.*`` and drop ``motion`` (in-place)."""
    motion = updates.get("motion")
    if not isinstance(motion, dict) or not motion:
        return
    triggers = updates.setdefault("triggers", {})
    if not isinstance(triggers, dict):
        triggers = {}
        updates["triggers"] = triggers
    _fold_motion_fields_into_triggers(motion, triggers)
    del updates["motion"]


def build_motion_settings_mirror_for_api(cfg: dict[str, Any]) -> dict[str, Any]:
    """Синтез блока ``motion`` для GET /api/ui/settings (legacy ``motion.*`` в API).

    После merge ``motion`` удаляется из merged-дерева; UI редактирует ``triggers.frigate.*``,
    но зеркало ``motion.frigate_*`` оставляем для старых клиентов и экспорта YAML.
    """
    triggers = cfg.get("triggers") if isinstance(cfg.get("triggers"), dict) else {}
    op = triggers.get("opencv") if isinstance(triggers.get("opencv"), dict) else {}
    fr = triggers.get("frigate") if isinstance(triggers.get("frigate"), dict) else {}
    ms = triggers.get("motion_sensor") if isinstance(triggers.get("motion_sensor"), dict) else {}
    op_on = _as_bool(op.get("enabled"), True)
    fr_on = _as_bool(fr.get("enabled"), False)
    ms_on = _as_bool(ms.get("enabled"), False)
    ms_src = str(ms.get("source") or TRIGGER_SOURCE_MQTT).strip().lower()

    if ms_on and ms_src == TRIGGER_SOURCE_MQTT:
        src = "mqtt"
    elif ms_on and ms_src == TRIGGER_SOURCE_ESPHOME:
        src = "esphome"
    elif fr_on and op_on:
        src = "frigate"
    elif fr_on:
        src = "frigate"
    elif op_on:
        src = "opencv"
    else:
        src = "opencv"

    label_filter = fr.get("label_filter")
    if not isinstance(label_filter, (list, tuple)):
        label_filter = []
    label_exclude = fr.get("label_exclude")
    if not isinstance(label_exclude, (list, tuple)):
        label_exclude = []
    cam_f = fr.get("camera_filter")
    if not isinstance(cam_f, (list, tuple)):
        cam_f = []

    min_score = _as_float(
        _get_from_config(cfg, "triggers.frigate.min_trigger_score", 0.43),
        0.43,
    )

    return {
        "source": src,
        "check_every_n_frames": max(
            1,
            min(
                30,
                _as_int(_get_from_config(cfg, "triggers.opencv.check_every_n_frames", 1), 1),
            ),
        ),
        "opencv_diff_threshold": max(
            5,
            min(
                80,
                _as_int(_get_from_config(cfg, "triggers.opencv.diff_threshold", 18), 18),
            ),
        ),
        "opencv_min_contour_area": max(
            50,
            min(
                20000,
                _as_int(_get_from_config(cfg, "triggers.opencv.min_contour_area", 320), 320),
            ),
        ),
        "frigate_camera_filter": [str(x) for x in cam_f if str(x).strip()],
        "frigate_label_filter": [str(x) for x in label_filter if str(x).strip()],
        "frigate_label_exclude": [str(x) for x in label_exclude if str(x).strip()],
        "frigate_trigger_on_tracked_object": _as_bool(
            _get_from_config(cfg, "triggers.frigate.trigger_on_tracked_object"),
            True,
        ),
        "frigate_min_trigger_score": max(0.0, min_score),
        "mqtt_topic": str(ms.get("mqtt_topic") or "").strip(),
        "esphome_url": str(ms.get("esphome_url") or "").strip(),
        "esphome_sensor_id": str(ms.get("esphome_sensor_id") or "").strip(),
    }


def migrate_legacy_motion_block(user_config: dict[str, Any]) -> bool:
    """Persist: move legacy ``motion:`` into ``triggers`` and remove ``motion`` from user file."""
    if not isinstance(user_config, dict):
        return False
    motion = user_config.get("motion")
    if not isinstance(motion, dict) or not motion:
        return False
    logger.warning(
        "Deprecated: top-level 'motion:' in user_config.yaml — use grouped "
        "'triggers.opencv', 'triggers.frigate', 'triggers.motion_sensor', "
        "'triggers.scales' (see docs/CONFIGURATION.md). Migrating into triggers.* "
        "and removing 'motion'.",
    )
    triggers = user_config.setdefault("triggers", {})
    _fold_motion_fields_into_triggers(motion, triggers)
    _apply_legacy_motion_source_flags(motion.get("source"), triggers)
    del user_config["motion"]
    return True


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


def build_opencv_trigger_runtime_config(config_or_get: Any) -> dict[str, Any]:
    """Полный ``triggers.opencv`` для процессора (не только 4 legacy-ключа UI)."""

    def _oc(path: str, default: Any) -> Any:
        return _get_from_config(config_or_get, f"triggers.opencv.{path}", default)

    detection_method = str(_oc("detection_method", "frame_diff") or "frame_diff").strip().lower()
    if detection_method not in {"frame_diff", "mog2", "hybrid"}:
        detection_method = "frame_diff"

    diff_threshold = max(5, min(80, _as_int(_oc("diff_threshold", 18), 18)))
    min_contour_area = max(50, min(20000, _as_int(_oc("min_contour_area", 320), 320)))

    return {
        "enabled": _as_bool(_oc("enabled", True), True),
        "check_every_n_frames": max(1, min(30, _as_int(_oc("check_every_n_frames", 1), 1))),
        "check_interval_seconds": max(0.05, min(2.0, _as_float(_oc("check_interval_seconds", 0.12), 0.12))),
        "motion_max_side_px": max(160, min(1280, _as_int(_oc("motion_max_side_px", 512), 512))),
        "diff_threshold": diff_threshold,
        "min_contour_area": min_contour_area,
        "detection_method": detection_method,
        "suppress_warmup_frames": max(0, min(600, _as_int(_oc("suppress_warmup_frames", 0), 0))),
        "auto_profile_enabled": _as_bool(_oc("auto_profile_enabled", True), True),
        "auto_profile_night_luma_threshold": max(
            1.0,
            min(255.0, _as_float(_oc("auto_profile_night_luma_threshold", 58.0), 58.0)),
        ),
        "smart_trigger_enabled": _as_bool(_oc("smart_trigger_enabled", True), True),
        "global_motion_mean_absdiff": max(
            0.1, min(64.0, _as_float(_oc("global_motion_mean_absdiff", 2.5), 2.5))
        ),
        "min_motion_pixel_fraction": max(
            0.0, min(1.0, _as_float(_oc("min_motion_pixel_fraction", 0.0008), 0.0008))
        ),
        "max_contour_area_frac": max(0.01, min(0.99, _as_float(_oc("max_contour_area_frac", 0.38), 0.38))),
        "day_diff_threshold": max(5, min(80, _as_int(_oc("day_diff_threshold", diff_threshold), diff_threshold))),
        "day_min_contour_area": max(
            50, min(20000, _as_int(_oc("day_min_contour_area", min_contour_area), min_contour_area))
        ),
        "day_global_motion_mean_absdiff": max(
            0.1,
            min(64.0, _as_float(_oc("day_global_motion_mean_absdiff", 2.5), 2.5)),
        ),
        "day_min_motion_pixel_fraction": max(
            0.0,
            min(1.0, _as_float(_oc("day_min_motion_pixel_fraction", 0.0008), 0.0008)),
        ),
        "day_max_contour_area_frac": max(
            0.01, min(0.99, _as_float(_oc("day_max_contour_area_frac", 0.38), 0.38))
        ),
        "night_diff_threshold": max(5, min(80, _as_int(_oc("night_diff_threshold", diff_threshold), diff_threshold))),
        "night_min_contour_area": max(
            50, min(20000, _as_int(_oc("night_min_contour_area", min_contour_area), min_contour_area))
        ),
        "night_global_motion_mean_absdiff": max(
            0.1,
            min(64.0, _as_float(_oc("night_global_motion_mean_absdiff", 2.2), 2.2)),
        ),
        "night_min_motion_pixel_fraction": max(
            0.0,
            min(1.0, _as_float(_oc("night_min_motion_pixel_fraction", 0.0006), 0.0006)),
        ),
        "night_max_contour_area_frac": max(
            0.01, min(0.99, _as_float(_oc("night_max_contour_area_frac", 0.45), 0.45))
        ),
        "mog2_history": max(16, min(2000, _as_int(_oc("mog2_history", 300), 300))),
        "mog2_var_threshold": max(1.0, min(256.0, _as_float(_oc("mog2_var_threshold", 24.0), 24.0))),
        "mog2_detect_shadows": _as_bool(_oc("mog2_detect_shadows", False), False),
        "mog2_min_motion_pixel_fraction": max(
            0.0,
            min(1.0, _as_float(_oc("mog2_min_motion_pixel_fraction", 0.0006), 0.0006)),
        ),
        "mog2_min_contour_area": max(
            50, min(20000, _as_int(_oc("mog2_min_contour_area", min_contour_area), min_contour_area))
        ),
        "min_consecutive_motion_frames": max(
            1, min(30, _as_int(_oc("min_consecutive_motion_frames", 2), 2))
        ),
        "scene_change_motion_fraction": max(
            0.1, min(1.0, _as_float(_oc("scene_change_motion_fraction", 0.8), 0.8))
        ),
        "improve_contrast": _as_bool(_oc("improve_contrast", False), False),
        "morphology_open_iterations": max(0, min(5, _as_int(_oc("morphology_open_iterations", 1), 1))),
    }


def get_effective_trigger_config(
    config_or_get: Any,
    *,
    mqtt_broker: str | None = None,
) -> dict[str, dict[str, Any]]:
    # Совместимость сигнатуры: раньше broker влиял на дефолты Frigate — больше нет.
    _ = mqtt_broker
    opencv_enabled = _as_bool(_get_from_config(config_or_get, "triggers.opencv.enabled"), True)
    frigate_enabled = _as_bool(_get_from_config(config_or_get, "triggers.frigate.enabled"), False)
    motion_sensor_enabled = _as_bool(
        _get_from_config(config_or_get, "triggers.motion_sensor.enabled"),
        False,
    )
    motion_sensor_source = normalize_transport_source(
        _get_from_config(config_or_get, "triggers.motion_sensor.source"),
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

    raw_per_cam = _get_from_config(config_or_get, "triggers.frigate.min_trigger_score_by_camera")
    per_cam: dict[str, Any] = raw_per_cam if isinstance(raw_per_cam, dict) else {}

    opencv_runtime = build_opencv_trigger_runtime_config(config_or_get)
    opencv_runtime["enabled"] = opencv_enabled

    return {
        "opencv": opencv_runtime,
        "frigate": {
            "enabled": frigate_enabled,
            "topic": get_frigate_topic(config_or_get),
            "camera_filter": _get_from_config(config_or_get, "triggers.frigate.camera_filter") or [],
            "label_filter": _get_from_config(config_or_get, "triggers.frigate.label_filter") or [],
            "label_exclude": _get_from_config(config_or_get, "triggers.frigate.label_exclude") or [],
            "trigger_on_tracked_object": _as_bool(
                _get_from_config(config_or_get, "triggers.frigate.trigger_on_tracked_object"),
                True,
            ),
            "min_trigger_score": max(
                0.0,
                _as_float(
                    _get_from_config(config_or_get, "triggers.frigate.min_trigger_score", 0.5),
                    0.5,
                ),
            ),
            "min_trigger_score_by_camera": per_cam,
            "trigger_on_update": _as_bool(
                _get_from_config(config_or_get, "triggers.frigate.trigger_on_update"),
                False,
            ),
        },
        "motion_sensor": {
            "enabled": motion_sensor_enabled,
            "source": motion_sensor_source,
            "mqtt_topic": str(
                _get_from_config(config_or_get, "triggers.motion_sensor.mqtt_topic") or ""
            ).strip(),
            "esphome_url": str(
                _get_from_config(config_or_get, "triggers.motion_sensor.esphome_url") or ""
            ).strip(),
            "esphome_sensor_id": str(
                _get_from_config(config_or_get, "triggers.motion_sensor.esphome_sensor_id") or ""
            ).strip(),
            "pir_pin": max(
                0,
                _as_int(_get_from_config(config_or_get, "triggers.motion_sensor.pir_pin"), 4),
            ),
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


def effective_active_trigger_names_for_mqtt_status(
    configured_active: list[str],
    trigger_cfg: dict[str, dict[str, Any]],
    *,
    mqtt_display: str,
) -> list[str]:
    """Подпись в UI/readiness: без живого MQTT Frigate и MQTT-зависимые триггеры не участвуют.

    Совпадает с поведением ``build_motion_detector``: при недоступном брокере остаётся
    OpenCV (и ESPHome-датчик при прямом URL). См. ``motion_detectors/factory.py``.
    """
    if str(mqtt_display or "").strip().lower() == "ok":
        return list(configured_active)
    out: list[str] = []
    for name in configured_active:
        if name == "frigate":
            continue
        if name == "motion_sensor":
            src = str(
                (trigger_cfg.get("motion_sensor") or {}).get("source") or TRIGGER_SOURCE_MQTT,
            ).strip().lower()
            if src == TRIGGER_SOURCE_MQTT:
                continue
        if name == "scales":
            sc_src = (trigger_cfg.get("scales") or {}).get("source")
            if scales_source_uses_mqtt(sc_src):
                continue
        out.append(name)
    if not out:
        return ["opencv"]
    return out


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
    """Сводка по эффективным триггерам из ``triggers.*`` / enabled-флагов."""
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
