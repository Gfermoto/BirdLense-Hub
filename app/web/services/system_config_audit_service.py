"""Сборка ответа GET /api/ui/system/config-audit (#293)."""

from __future__ import annotations

import json
import logging
import os
import yaml

import data_paths
from app_config.deprecated_keys import DEPRECATED_USER_CONFIG_KEYS
from app_config.scales_config import normalize_scales_source, scales_source_uses_mqtt
from app_config.trigger_config import (
    format_motion_source_summary,
    get_active_trigger_names,
    normalize_transport_source,
)

logger = logging.getLogger(__name__)

DOCUMENTED_SCALES_MQTT_PREFIX = "birdlense/scale"

_log = logging.getLogger(__name__)

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

# Ветки с динамическими leaf-ключами: audit не должен помечать их как unknown.
IGNORED_CONFIG_AUDIT_PREFIXES = ("processor.camera_overrides.",)


def _is_known_dynamic_config_key(path: str, *, default_keys: set[str]) -> bool:
    key = str(path or "").strip()
    if not key:
        return False
    if any(key.startswith(prefix) for prefix in IGNORED_CONFIG_AUDIT_PREFIXES):
        suffix = key.split(".", 3)[-1]
        if not suffix:
            return False
        return f"processor.{suffix}" in default_keys
    if key.startswith("processor.adaptive_profiles.") and ".overrides." in key:
        suffix = key.split(".overrides.", 1)[-1].strip()
        if not suffix:
            return False
        return f"processor.{suffix}" in default_keys
    if key.startswith("processor.adaptive_profiles."):
        # profile container itself is dynamic.
        return True
    return False


# Совпадает с `triggers.opencv.*` в `default_config.yaml`.
RECOMMENDED_OPENCV_DIFF_THRESHOLD = 18
RECOMMENDED_OPENCV_MIN_CONTOUR_AREA = 320


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


def _bool_config(value, *, default: bool) -> bool:
    """YAML/формы могут отдать строку; для frigate_standalone важно не считать bool(\"false\") == True."""
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    s = str(value).strip().lower()
    if s in ("false", "0", "no", "off", ""):
        return False
    if s in ("true", "1", "yes", "on"):
        return True
    return default


def _recall_audit(app_config_get) -> tuple[dict, list[str], list[str]]:
    """Возвращает (recall_tuning, recall_hints, recall_blocking).

    ``recall_hints`` — мягкие подсказки по чувствительности (не ошибки конфига).
    ``recall_blocking`` — только сочетания, которые реально ломают поток событий
    (сейчас: Frigate включён без ``mqtt.broker``); попадают в ``config_warnings``.
    """
    mqtt_broker = (app_config_get("mqtt.broker") or "").strip()
    active_triggers = get_active_trigger_names(app_config_get, mqtt_broker=mqtt_broker)
    motion_source = format_motion_source_summary(active_triggers)
    check_every_n_frames = max(1, _safe_int(app_config_get("triggers.opencv.check_every_n_frames", 1), 1))
    opencv_diff_threshold = max(
        5,
        min(
            80,
            _safe_int(
                app_config_get("triggers.opencv.diff_threshold", RECOMMENDED_OPENCV_DIFF_THRESHOLD),
                RECOMMENDED_OPENCV_DIFF_THRESHOLD,
            ),
        ),
    )
    opencv_min_contour_area = max(
        50,
        min(
            20000,
            _safe_int(
                app_config_get("triggers.opencv.min_contour_area", RECOMMENDED_OPENCV_MIN_CONTOUR_AREA),
                RECOMMENDED_OPENCV_MIN_CONTOUR_AREA,
            ),
        ),
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
    binary_imgsz = max(320, _safe_int(app_config_get("processor.binary_imgsz", 640), 640))
    min_center_dist = max(0.0, min(1.0, _safe_float(app_config_get("processor.min_center_dist", 0.06), 0.06)))
    min_box_size_px = max(1, _safe_int(app_config_get("processor.min_box_size_px", 72), 72))

    blocking: list[str] = []
    hints: list[str] = []
    if "frigate" in active_triggers and not mqtt_broker:
        blocking.append(
            "Frigate trigger is enabled but mqtt.broker is empty, so Frigate events will never reach the processor."
        )
    source = str(app_config_get("video.source") or "go2rtc").strip().lower()
    if source == "go2rtc":
        try:
            from app_config.cameras import get_valid_cameras, validate_go2rtc_detect_streams

            video_cfg = app_config_get("video") or {}
            valid = get_valid_cameras(
                video_config=video_cfg if isinstance(video_cfg, dict) else None,
            )
            for issue in validate_go2rtc_detect_streams(valid, video_source=source):
                blocking.append(issue)
        except Exception:
            logger.warning("go2rtc detect_stream audit failed", exc_info=True)
    frigate_standalone = _bool_config(
        app_config_get("detection.frigate_standalone_when_no_yolo"),
        default=True,
    )
    if "frigate" in active_triggers and mqtt_broker and not frigate_standalone:
        hints.append("fusion.FRIGATE_STANDALONE_OFF")
    if check_every_n_frames > 1:
        hints.append(
            f"triggers.opencv.check_every_n_frames={check_every_n_frames} skips frames and can miss brief motion; "
            "1 is the highest-recall setting."
        )
    if opencv_diff_threshold > RECOMMENDED_OPENCV_DIFF_THRESHOLD:
        hints.append(
            f"triggers.opencv.diff_threshold={opencv_diff_threshold} is above the hub default "
            f"({RECOMMENDED_OPENCV_DIFF_THRESHOLD}); higher values react to fewer pixel changes (less motion recall)."
        )
    if opencv_min_contour_area > RECOMMENDED_OPENCV_MIN_CONTOUR_AREA:
        hints.append(
            f"triggers.opencv.min_contour_area={opencv_min_contour_area} is above the hub default "
            f"({RECOMMENDED_OPENCV_MIN_CONTOUR_AREA}); higher values drop smaller motion blobs (e.g. distant birds)."
        )
    if light_gate_enabled and (light_gate_min_brightness > 20 or light_gate_min_contrast > 15):
        hints.append(
            "processor.light_gate_* may skip dusk/night frames before YOLO runs; lower them if you need more recall in low light."
        )
    if binary_imgsz < 640:
        hints.append(f"processor.binary_imgsz={binary_imgsz} is below 640; small feeder birds are easier to miss.")
    if min_center_dist > 0.05:
        hints.append(f"processor.min_center_dist={min_center_dist:.2f} can suppress birds perched near the frame edge.")
    if min_box_size_px > 64:
        hints.append(f"processor.min_box_size_px={min_box_size_px} can drop small tracks; lower it for feeder scenes.")

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
        hints,
        blocking,
    )


def _resolve_scales_transport_source(app_config_get) -> str:
    """Как у `get_effective_trigger_config`: явный `triggers.scales.source` перекрывает integrations."""
    explicit = _get_from_flat_getter(app_config_get, "triggers.scales.source")
    if explicit is not None and str(explicit).strip():
        return normalize_transport_source(str(explicit).strip(), default="mqtt")
    return normalize_scales_source(app_config_get("integrations.scales.source"))


def _get_from_flat_getter(app_config_get, path: str):
    """Тот же контракт, что у ``app_config.get(path)`` (путь с точками)."""
    return app_config_get(path)


def _scales_mqtt_audit(app_config_get, user_cfg: dict) -> tuple[dict, list[str]]:
    """Проверки MQTT-весов: брокер, префикс/топик, явный '' в user YAML."""
    warnings: list[str] = []
    enabled = bool(app_config_get("integrations.scales.enabled"))
    src = _resolve_scales_transport_source(app_config_get)
    mqtt_broker = (app_config_get("mqtt.broker") or "").strip()
    raw_scales = {}
    if isinstance(user_cfg.get("integrations"), dict):
        raw_scales = user_cfg.get("integrations", {}).get("scales") or {}
    if not isinstance(raw_scales, dict):
        raw_scales = {}

    out: dict[str, object] = {
        "enabled": enabled,
        "source": src,
        "mqtt_broker_configured": bool(mqtt_broker),
    }

    if not enabled:
        out["mqtt_weight_topic_resolved"] = None
        return out, warnings

    if not scales_source_uses_mqtt(src):
        out["mqtt_weight_topic_resolved"] = None
        out["mqtt_note"] = "esphome_or_ha"
        return out, warnings

    prefix = (app_config_get("integrations.scales.mqtt_topic_prefix") or "").strip().strip("/")
    mq_topic = (app_config_get("integrations.scales.mqtt_topic") or "").strip()
    effective = mq_topic or (f"{prefix}/weight" if prefix else "")

    out["mqtt_topic_prefix"] = prefix or None
    out["mqtt_topic_explicit"] = bool(mq_topic)
    out["mqtt_weight_topic_resolved"] = effective or None

    if raw_scales.get("mqtt_topic_prefix") == "":
        warnings.append(
            'user_config: integrations.scales.mqtt_topic_prefix is explicitly empty (""): '
            "this overrides the default prefix and the processor will not subscribe to "
            f"{DOCUMENTED_SCALES_MQTT_PREFIX}/weight unless mqtt_topic is set. Remove the key or set a real prefix."
        )
    # При непустом mqtt_topic_prefix явные "" для этих ключей в user YAML эквивалентны
    # отсутствию ключа: рантайм всё равно выводит {prefix}/weight|bird_present|command.
    if not prefix:
        for key in (
            "mqtt_topic",
            "mqtt_bird_present_topic",
            "mqtt_command_topic",
        ):
            if raw_scales.get(key) == "":
                warnings.append(
                    f'user_config: integrations.scales.{key} is explicitly "" — empty string overrides defaults; '
                    "omit the key if you want derived topics from mqtt_topic_prefix."
                )

    if not mqtt_broker:
        warnings.append(
            "integrations.scales use MQTT, but mqtt.broker is empty: the processor cannot subscribe; "
            "weight and bird_present will not update via MQTT."
        )

    if not effective:
        warnings.append(
            "integrations.scales: both mqtt_topic and mqtt_topic_prefix are empty — no weight MQTT topic to subscribe."
        )

    if prefix and prefix.replace("\\", "/") != DOCUMENTED_SCALES_MQTT_PREFIX and not mq_topic:
        warnings.append(
            f'integrations.scales.mqtt_topic_prefix is "{prefix}"; the stock BirdLense ESPHome example uses '
            f'"{DOCUMENTED_SCALES_MQTT_PREFIX}" for derived topics. If weight never updates, align this prefix '
            "with the device publish prefix (or set integrations.scales.mqtt_topic to the full weight topic)."
        )

    return out, warnings


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
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as exc:
        _log.debug("load_yaml_mapping failed path=%r: %s", path, exc, exc_info=True)
        return {}


def _processor_runtime_hints(app_config_get) -> list[str]:
    """Подсказки из data/diagnostics/processor_runtime_stats.json (совпадает с логами VPS)."""
    hints: list[str] = []
    warn_ms = max(0.0, _safe_float(app_config_get("processor.frame_processing_warn_ms", 450), 450))
    snap = _load_processor_runtime_snapshot()
    if not snap:
        return hints
    counters = snap.get("counters") if isinstance(snap.get("counters"), dict) else {}
    try:
        slow = int(counters.get("slow_frame_processor_detect_total") or 0)
    except (TypeError, ValueError):
        slow = 0
    if slow > 0 and warn_ms > 0:
        hints.append(f"processor.runtime.SLOW_FRAMES total={slow} warn_ms={int(warn_ms)}")
    try:
        clf_rev = int(counters.get("classifier_needs_review_total") or 0)
    except (TypeError, ValueError):
        clf_rev = 0
    if clf_rev > 0:
        hints.append(
            "processor.runtime.CLASSIFIER_NEEDS_REVIEW "
            f"total={clf_rev} (entropy/margin thresholds in processor.classifier_uncertainty_*)"
        )
    lat = snap.get("latency_ms") if isinstance(snap.get("latency_ms"), dict) else {}
    p95_raw = lat.get("frame_processor_detect_p95")
    try:
        p95 = float(p95_raw) if p95_raw is not None else None
    except (TypeError, ValueError):
        p95 = None
    if warn_ms > 0 and p95 is not None and p95 >= warn_ms * 0.95:
        hints.append(f"processor.runtime.DETECT_P95 p95_ms={p95:.1f} warn_ms={int(warn_ms)}")
    return hints


def _load_processor_runtime_snapshot() -> dict | None:
    path = os.path.join(data_paths.data_dir(), "diagnostics", "processor_runtime_stats.json")
    if not os.path.isfile(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            snap = json.load(f)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(snap, dict):
        return None
    return snap


def _preflight_config_safety(app_config_get) -> dict:
    checks: list[dict[str, object]] = []
    video_encoding = str(app_config_get("video.encoding") or "cpu").strip().lower()
    mqtt_broker = str(app_config_get("mqtt.broker") or "").strip()
    detector_backend = str(app_config_get("processor.inference_backend") or "auto").strip().lower()
    detector_device = str(app_config_get("processor.inference_device") or "auto").strip().lower()
    frigate_enabled = bool(app_config_get("triggers.frigate.enabled", False))
    min_recording_gap = _safe_float(app_config_get("processor.min_seconds_between_recordings", 0), 0.0)
    binary_imgsz = _safe_int(app_config_get("processor.binary_imgsz", 640), 640)
    light_gate_enabled = bool(app_config_get("processor.light_gate_enabled", True))
    light_gate_brightness = _safe_int(app_config_get("processor.light_gate_min_brightness", 25), 25)
    light_gate_contrast = _safe_int(app_config_get("processor.light_gate_min_contrast", 20), 20)

    checks.append(
        {
            "id": "frigate_requires_mqtt",
            "status": "fail" if frigate_enabled and not mqtt_broker else "ok",
            "severity": "error",
            "message": "Frigate trigger needs mqtt.broker; events are dropped when broker is empty.",
        }
    )
    checks.append(
        {
            "id": "gpu_split_pipeline",
            "status": (
                "warn"
                if video_encoding == "cpu"
                and detector_backend in {"onnxruntime", "auto", "torch"}
                and detector_device.startswith("cuda")
                else "ok"
            ),
            "severity": "warning",
            "message": "Detector on GPU with CPU video encoding may hide regressions in split runtime path.",
        }
    )
    checks.append(
        {
            "id": "recording_gap_guardrail",
            "status": "warn" if min_recording_gap > 4.0 else "ok",
            "severity": "warning",
            "message": "High min_seconds_between_recordings can suppress short repeated visits.",
        }
    )
    checks.append(
        {
            "id": "binary_imgsz_floor",
            "status": "warn" if binary_imgsz < 512 else "ok",
            "severity": "warning",
            "message": "Very low binary_imgsz can reduce recall for small birds.",
        }
    )
    checks.append(
        {
            "id": "light_gate_recall",
            "status": "warn"
            if light_gate_enabled and (light_gate_brightness > 35 or light_gate_contrast > 35)
            else "ok",
            "severity": "warning",
            "message": "Aggressive light gate can block dusk/night detections before YOLO.",
        }
    )
    status = (
        "fail"
        if any(c["status"] == "fail" for c in checks)
        else ("warn" if any(c["status"] == "warn" for c in checks) else "ok")
    )
    return {
        "status": status,
        "checks": checks,
    }


def _runtime_parity_snapshot(app_config_get) -> dict:
    snap = _load_processor_runtime_snapshot() or {}
    gauges = snap.get("gauges") if isinstance(snap.get("gauges"), dict) else {}
    configured_paths = max(0.0, _safe_float(gauges.get("trigger_configured_paths_count"), 0.0))
    effective_paths = max(0.0, _safe_float(gauges.get("trigger_effective_paths_count"), 0.0))
    degraded = int(_safe_float(gauges.get("trigger_degraded_effective_lt_configured"), 0.0)) == 1
    trigger_cfg_frigate = int(_safe_float(gauges.get("trigger_cfg_frigate_enabled"), 0.0)) == 1
    trigger_frigate_degraded = int(_safe_float(gauges.get("trigger_frigate_degraded_no_mqtt"), 0.0)) == 1
    mqtt_live = int(_safe_float(gauges.get("trigger_mqtt_live"), 0.0)) == 1
    return {
        "configured": {
            "triggers_frigate_enabled": bool(app_config_get("triggers.frigate.enabled", False)),
            "mqtt_broker_configured": bool(str(app_config_get("mqtt.broker") or "").strip()),
            "inference_backend": str(app_config_get("processor.inference_backend") or "auto"),
            "inference_device": str(app_config_get("processor.inference_device") or "auto"),
            "video_encoding": str(app_config_get("video.encoding") or "cpu"),
        },
        "runtime": {
            "trigger_cfg_frigate_enabled": trigger_cfg_frigate,
            "trigger_configured_paths_count": configured_paths,
            "trigger_effective_paths_count": effective_paths,
            "trigger_degraded_effective_lt_configured": degraded,
            "trigger_frigate_degraded_no_mqtt": trigger_frigate_degraded,
            "trigger_mqtt_live": mqtt_live,
            "last_session_runtime_profile": gauges.get("last_session_runtime_profile"),
        },
        "parity_alerts": {
            "frigate_config_runtime_mismatch": bool(
                bool(app_config_get("triggers.frigate.enabled", False)) != trigger_cfg_frigate
            ),
            "effective_trigger_paths_dropped": bool(degraded),
            "frigate_degraded_no_mqtt": bool(trigger_frigate_degraded),
        },
    }


def _config_presets() -> list[dict]:
    return [
        {
            "id": "stability",
            "title": "Stability first",
            "overrides": {
                "processor.inference_backend": "auto",
                "video.encoding": "cpu",
                "processor.min_seconds_between_recordings": 0.0,
                "processor.binary_imgsz": 640,
            },
        },
        {
            "id": "balanced",
            "title": "Balanced",
            "overrides": {
                "processor.inference_backend": "onnxruntime",
                "video.encoding": "cpu",
                "processor.binary_imgsz": 640,
                "processor.min_seconds_between_recordings": 0.0,
            },
        },
        {
            "id": "recall",
            "title": "Recall priority",
            "overrides": {
                "processor.binary_imgsz": 640,
                "processor.light_gate_enabled": False,
                "processor.min_center_dist": 0.04,
                "processor.min_box_size_px": 48,
            },
        },
    ]


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
            if k not in default_keys
            and k not in IGNORED_CONFIG_AUDIT_KEYS
            and not k.startswith("camera.")
            and not _is_known_dynamic_config_key(k, default_keys=default_keys)
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
    recall_tuning, recall_hints, recall_blocking = _recall_audit(app_config_get)
    scales_tuning, scales_warnings = _scales_mqtt_audit(app_config_get, user_cfg)
    scales_blocking = [w for w in scales_warnings if "mqtt.broker is empty" in w or "no weight MQTT topic" in w]
    combined_warnings = [*recall_blocking, *scales_blocking]
    processor_runtime_hints = _processor_runtime_hints(app_config_get)
    preflight = _preflight_config_safety(app_config_get)
    runtime_parity = _runtime_parity_snapshot(app_config_get)
    from services.system_operational_status import filter_runtime_parity_alerts

    if isinstance(runtime_parity.get("parity_alerts"), dict):
        runtime_parity = {
            **runtime_parity,
            "parity_alerts": filter_runtime_parity_alerts(
                runtime_parity["parity_alerts"],
                app_config_get=app_config_get,
            ),
        }
    return {
        "deprecated_keys_present": deprecated_present,
        "unknown_keys": unknown_keys,
        "telegram": {
            "proxy_type": (notif.get("telegram_proxy_type") or "none"),
            "send_photo": bool(notif.get("send_photo")),
        },
        "recall_tuning": recall_tuning,
        "recall_warnings": recall_hints,
        "processor_runtime_hints": processor_runtime_hints,
        "scales_mqtt": scales_tuning,
        "scales_warnings": scales_warnings,
        "scales_blocking_warnings": scales_blocking,
        "config_warnings": combined_warnings,
        "config_presets": _config_presets(),
        "preflight": preflight,
        "runtime_parity": runtime_parity,
        "mapping": {
            "gray_to_grey_ok": gray_to_grey_ok,
            "pairs": gray_pairs,
        },
    }
