"""Сборка ответа GET /api/ui/system/config-audit (#293)."""

from __future__ import annotations

import yaml

DEPRECATED_USER_CONFIG_KEYS = (
    'gallery.enabled',
    'gallery.min_confidence',
    'gallery.only_manually_corrected',
    'gallery.upload_url',
    'general.heimdall_url',
    "notifications.enabled",
    "notifications.excluded_species",
    "notifications.rate_limit_per_minute",
    "processor.detection_device",
    "processor.detection_frame_interval",
    "weather.ha_token",
    "weather.ha_url",
)

TERMINAL_CONFIG_MAP_KEYS = frozenset(
    {
        "detection.species_mapping",
        "ebird.species_mapping",
        "processor.species_confidence_overrides",
    }
)

IGNORED_CONFIG_AUDIT_KEYS = frozenset(
    {
        "camera",
        "secrets.zip",
        "weather.ha_token",
        "weather.ha_url",
    }
)


def _safe_int(value, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_float(value, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _recall_audit(app_config_get) -> tuple[dict, list[str]]:
    motion_source = str(app_config_get("motion.source", "opencv") or "opencv").strip().lower()
    mqtt_broker = (app_config_get("mqtt.broker") or "").strip()
    check_every_n_frames = max(1, _safe_int(app_config_get("motion.check_every_n_frames", 1), 1))
    opencv_diff_threshold = max(5, min(80, _safe_int(app_config_get("motion.opencv_diff_threshold", 25), 25)))
    opencv_min_contour_area = max(
        50,
        min(20000, _safe_int(app_config_get("motion.opencv_min_contour_area", 500), 500)),
    )
    light_gate_enabled = bool(app_config_get("processor.light_gate_enabled", True))
    light_gate_min_brightness = max(
        0,
        min(255, _safe_int(app_config_get("processor.light_gate_min_brightness", 25), 25)),
    )
    light_gate_min_contrast = max(
        0,
        min(255, _safe_int(app_config_get("processor.light_gate_min_contrast", 20), 20)),
    )
    binary_imgsz = max(320, _safe_int(app_config_get("processor.binary_imgsz", 512), 512))
    min_center_dist = max(0.0, min(1.0, _safe_float(app_config_get("processor.min_center_dist", 0.06), 0.06)))
    min_box_size_px = max(1, _safe_int(app_config_get("processor.min_box_size_px", 72), 72))

    warnings: list[str] = []
    if motion_source == "opencv" and not mqtt_broker:
        warnings.append(
            "motion.source=opencv without mqtt.broker means Frigate never becomes a trigger; "
            "use motion.source=frigate or configure MQTT if Frigate sees more objects."
        )
    if check_every_n_frames > 1:
        warnings.append(
            f"motion.check_every_n_frames={check_every_n_frames} skips frames and can miss brief motion; "
            "1 is the highest-recall setting."
        )
    if opencv_diff_threshold > 20:
        warnings.append(
            f"motion.opencv_diff_threshold={opencv_diff_threshold} is conservative; lower values are more sensitive."
        )
    if opencv_min_contour_area > 250:
        warnings.append(f"motion.opencv_min_contour_area={opencv_min_contour_area} can miss small distant birds.")
    if light_gate_enabled and (light_gate_min_brightness > 20 or light_gate_min_contrast > 15):
        warnings.append(
            "processor.light_gate_* may skip dusk/night frames before YOLO runs; lower them if you need more recall in low light."
        )
    if binary_imgsz < 640:
        warnings.append(f"processor.binary_imgsz={binary_imgsz} is below 640; small feeder birds are easier to miss.")
    if min_center_dist > 0.05:
        warnings.append(
            f"processor.min_center_dist={min_center_dist:.2f} can suppress birds perched near the frame edge."
        )
    if min_box_size_px > 64:
        warnings.append(
            f"processor.min_box_size_px={min_box_size_px} can drop small tracks; lower it for feeder scenes."
        )

    return (
        {
            "motion_source": motion_source,
            "mqtt_broker_configured": bool(mqtt_broker),
            "check_every_n_frames": check_every_n_frames,
            "opencv_diff_threshold": opencv_diff_threshold,
            "opencv_min_contour_area": opencv_min_contour_area,
            "light_gate_enabled": light_gate_enabled,
            "light_gate_min_brightness": light_gate_min_brightness,
            "light_gate_min_contrast": light_gate_min_contrast,
            "binary_imgsz": binary_imgsz,
            "min_center_dist": min_center_dist,
            "min_box_size_px": min_box_size_px,
        },
        warnings,
    )


def flatten_config_keys(d: dict, prefix: str = "") -> set[str]:
    out: set[str] = set()
    if not isinstance(d, dict):
        return out
    if prefix in TERMINAL_CONFIG_MAP_KEYS:
        return {prefix} if prefix else set()
    for k, v in d.items():
        p = f"{prefix}.{k}" if prefix else str(k)
        out.add(p)
        if isinstance(v, dict):
            out |= flatten_config_keys(v, p)
    return out


def load_yaml_mapping(path: str) -> dict:
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
            return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def build_system_config_audit_payload(
    *,
    user_config_file: str,
    default_config_file: str,
    app_config_get,
) -> dict:
    user_cfg = load_yaml_mapping(user_config_file)
    default_only = load_yaml_mapping(default_config_file)
    user_keys = flatten_config_keys(user_cfg)
    default_keys = flatten_config_keys(default_only)
    unknown_keys = sorted(
        [
            k
            for k in user_keys
            if k not in default_keys and k not in IGNORED_CONFIG_AUDIT_KEYS and not k.startswith("camera.")
        ]
    )
    deprecated_present = sorted([k for k in DEPRECATED_USER_CONFIG_KEYS if k in user_keys])

    notif = app_config_get("notifications", {}) or {}
    detection_map = app_config_get("detection.species_mapping") or {}
    ebird_map = app_config_get("ebird.species_mapping") or {}
    combined_map = {**detection_map, **ebird_map}
    gray_pairs = {
        "Gray-headed Woodpecker": combined_map.get("Gray-headed Woodpecker"),
        "Great Gray Shrike": combined_map.get("Great Gray Shrike"),
    }
    gray_to_grey_ok = (
        gray_pairs.get("Gray-headed Woodpecker") == "Grey-headed Woodpecker"
        and gray_pairs.get("Great Gray Shrike") == "Great Grey Shrike"
    )
    recall_tuning, recall_warnings = _recall_audit(app_config_get)
    return {
        "deprecated_keys_present": deprecated_present,
        "unknown_keys": unknown_keys,
        "telegram": {
            "proxy_type": (notif.get("telegram_proxy_type") or "none"),
            "send_photo": bool(notif.get("send_photo")),
        },
        "recall_tuning": recall_tuning,
        "recall_warnings": recall_warnings,
        "mapping": {
            "gray_to_grey_ok": gray_to_grey_ok,
            "pairs": gray_pairs,
        },
    }
