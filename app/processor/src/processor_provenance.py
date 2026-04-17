"""Pipeline provenance helpers for reproducible processor decisions."""

from __future__ import annotations

import hashlib
import json
import os
from typing import Any

from app_config.trigger_config import get_active_trigger_names

_MODEL_DIGEST_CACHE: dict[tuple[str, int, int], str] = {}

_CONFIG_DIGEST_KEYS = (
    "motion.source",
    "triggers.opencv.enabled",
    "triggers.opencv.check_every_n_frames",
    "triggers.opencv.diff_threshold",
    "triggers.opencv.min_contour_area",
    "triggers.frigate.enabled",
    "triggers.frigate.topic",
    "triggers.motion_sensor.enabled",
    "triggers.motion_sensor.source",
    "triggers.motion_sensor.mqtt_topic",
    "triggers.motion_sensor.esphome_url",
    "triggers.motion_sensor.esphome_sensor_id",
    "triggers.scales.enabled",
    "triggers.scales.source",
    "triggers.scales.motion_trigger_min_delta_kg",
    "triggers.scales.motion_trigger_debounce_seconds",
    "video.source",
    "processor.min_seconds_between_recordings",
    "processor.min_track_duration",
    "processor.min_confidence_to_process",
    "processor.min_confidence_to_notify",
    "processor.classifier_fallback_bird",
    "processor.models.binary",
    "processor.models.classifier",
    "detection.merge_window_seconds",
    "detection.dedup_window_seconds",
    "detection.min_confidence_to_store",
    "detection.use_learned_fusion",
    "detection.fusion_alpha",
    "detection.fusion_model_path",
    "integrations.scales.enabled",
    "integrations.birdnet.mqtt_topic",
    "integrations.scales.weight_estimate_enabled",
    "integrations.scales.min_delta_kg_for_estimate",
    "integrations.scales.estimate_require_consecutive_spike",
)


def _processor_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _resolve_model_path(rel_or_abs: str | None) -> str | None:
    raw = str(rel_or_abs or "").strip()
    if not raw:
        return None
    if os.path.isabs(raw):
        return raw
    return os.path.join(_processor_root(), raw)


def _sha256_for_path(path: str) -> str | None:
    if not path or not os.path.isfile(path):
        return None
    stat = os.stat(path)
    cache_key = (path, int(stat.st_mtime_ns), int(stat.st_size))
    cached = _MODEL_DIGEST_CACHE.get(cache_key)
    if cached:
        return cached
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while True:
            chunk = fh.read(1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
    digest = h.hexdigest()
    _MODEL_DIGEST_CACHE[cache_key] = digest
    return digest


def _model_record(path: str | None) -> dict[str, Any]:
    resolved = _resolve_model_path(path)
    exists = bool(resolved and os.path.isfile(resolved))
    rec: dict[str, Any] = {
        "path": resolved,
        "exists": exists,
    }
    if exists and resolved:
        stat = os.stat(resolved)
        rec["size_bytes"] = int(stat.st_size)
        rec["mtime_epoch_seconds"] = float(stat.st_mtime)
        rec["sha256"] = _sha256_for_path(resolved)
    return rec


def resolve_processor_version() -> tuple[str, str]:
    """Return the processor version string and where it came from."""
    for key in (
        "PROCESSOR_VERSION",
        "BIRDLENSE_PROCESSOR_VERSION",
        "GIT_COMMIT",
        "SOURCE_VERSION",
    ):
        value = str(os.environ.get(key) or "").strip()
        if value:
            return value, f"env:{key}"
    return "1", "legacy_default"


def build_pipeline_fingerprint(app_config) -> dict[str, Any]:
    """Build a compact reproducibility snapshot for the active pipeline."""
    processor_version, version_source = resolve_processor_version()
    config_slice = {key: app_config.get(key) for key in _CONFIG_DIGEST_KEYS}
    _mqtt = str(os.environ.get("MQTT_BROKER") or app_config.get("mqtt.broker") or "").strip()
    config_slice["_resolved_active_triggers"] = ",".join(
        get_active_trigger_names(app_config, mqtt_broker=_mqtt or None),
    )
    config_digest = hashlib.sha256(json.dumps(config_slice, sort_keys=True, default=str).encode("utf-8")).hexdigest()
    fusion_model_path = app_config.get("detection.fusion_model_path") or None
    return {
        "processor_version": processor_version,
        "version_source": version_source,
        "config_digest": config_digest,
        "binary_model": _model_record(app_config.get("processor.models.binary")),
        "classifier_model": _model_record(app_config.get("processor.models.classifier")),
        "fusion": {
            "enabled": bool(app_config.get("detection.use_learned_fusion") or False),
            "alpha": float(app_config.get("detection.fusion_alpha") or 0.6),
            "model": _model_record(fusion_model_path),
        },
    }
