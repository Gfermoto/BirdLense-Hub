"""Сборка ответа GET /api/ui/system/config-audit (#293)."""

from __future__ import annotations

import yaml

from services.heimdall_service import probe_heimdall

DEPRECATED_USER_CONFIG_KEYS = (
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
    gallery_enabled = bool(app_config_get("gallery.enabled"))
    gallery_url = (app_config_get("gallery.upload_url") or "").strip()
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
    heimdall_url = (app_config_get("general.heimdall_url") or "").strip()
    return {
        "deprecated_keys_present": deprecated_present,
        "unknown_keys": unknown_keys,
        "telegram": {
            "proxy_type": (notif.get("telegram_proxy_type") or "none"),
            "send_photo": bool(notif.get("send_photo")),
        },
        "gallery": {
            "enabled": gallery_enabled,
            "upload_url": gallery_url or None,
            "min_confidence": app_config_get("gallery.min_confidence"),
        },
        "mapping": {
            "gray_to_grey_ok": gray_to_grey_ok,
            "pairs": gray_pairs,
        },
        "heimdall": {
            "url": heimdall_url or None,
            "configured": bool(heimdall_url),
            "probe": probe_heimdall(heimdall_url),
        },
    }
