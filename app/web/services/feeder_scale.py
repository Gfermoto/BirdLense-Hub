"""Последний вес с весов (MQTT → файл в DATA_DIR или сущность Home Assistant)."""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from urllib.parse import quote

import requests

from app_config.app_config import app_config
from app_config.scales_config import (
    SCALES_SOURCE_ESPHOME,
    SCALES_SOURCE_HOMEASSISTANT,
    normalize_scales_source,
    scales_source_uses_mqtt,
)
from services.feed_service import mqtt_publish_once
from services.homeassistant_config import (
    get_homeassistant_token,
    get_homeassistant_url,
)

logger = logging.getLogger(__name__)

FEEDER_SCALE_STATE_FILE = "feeder_scale_state.json"


def _data_dir() -> str:
    return os.environ.get("DATA_DIR") or os.path.join(
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")),
        "data",
    )


def _read_scale_file() -> dict | None:
    path = os.path.join(_data_dir(), FEEDER_SCALE_STATE_FILE)
    if not os.path.isfile(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        logger.debug("feeder scale file: %s", e)
        return None


def _parse_bool_state(raw) -> bool | None:
    if isinstance(raw, bool):
        return raw
    if raw is None:
        return None
    s = str(raw).strip().lower()
    if s in ("true", "1", "on", "yes"):
        return True
    if s in ("false", "0", "off", "no"):
        return False
    return None


def _fetch_ha_entity_state(entity_id: str) -> dict | None:
    ha_url = get_homeassistant_url()
    token = get_homeassistant_token()
    if not ha_url or not token or not entity_id:
        return None
    url = f"{ha_url}/api/states/{entity_id}"
    try:
        r = requests.get(
            url,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            timeout=5,
        )
        r.raise_for_status()
        return r.json()
    except (requests.RequestException, ValueError, TypeError) as e:
        logger.debug("HA scale fetch: %s", e)
        return None


def _fetch_ha_scale(entity_id: str) -> dict | None:
    body = _fetch_ha_entity_state(entity_id)
    if not body:
        return None
    state = body.get("state")
    if state in (None, "unknown", "unavailable"):
        return None
    try:
        val = float(str(state).replace(",", "."))
    except (ValueError, TypeError):
        return None
    attrs = body.get("attributes") or {}
    unit = attrs.get("unit_of_measurement") or app_config.get("integrations.scales.unit") or "g"
    unit = str(unit).strip().lower()[:8] or "g"
    return {
        "weight": val,
        "unit": unit,
        "updated_at": body.get("last_changed") or datetime.now(timezone.utc).isoformat(),
        "source": "homeassistant",
    }


def _fetch_esphome_json(base_url: str, path: str) -> dict | None:
    if not base_url or not path:
        return None
    try:
        r = requests.get(f"{base_url.rstrip('/')}/{path.lstrip('/')}", timeout=5)
        r.raise_for_status()
        body = r.json()
        return body if isinstance(body, dict) else None
    except (requests.RequestException, ValueError, TypeError) as e:
        logger.debug("ESPHome scale fetch %s failed: %s", path, e)
        return None


def _fetch_esphome_scale() -> dict | None:
    base_url = (app_config.get("integrations.scales.esphome_url") or "").strip()
    weight_sensor_id = (app_config.get("integrations.scales.esphome_weight_sensor_id") or "").strip()
    bird_sensor_id = (app_config.get("integrations.scales.esphome_bird_present_sensor_id") or "").strip()
    if not base_url or not (weight_sensor_id or bird_sensor_id):
        return None

    out: dict = {
        "unit": str(app_config.get("integrations.scales.unit") or "g").strip().lower()[:8] or "g",
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "source": SCALES_SOURCE_ESPHOME,
    }

    if weight_sensor_id:
        body = _fetch_esphome_json(base_url, f"sensor/{quote(weight_sensor_id, safe='')}")
        if body:
            state = body.get("state")
            if state not in (None, "", "unknown", "unavailable"):
                try:
                    out["weight"] = float(str(state).replace(",", "."))
                except (ValueError, TypeError):
                    pass
            unit = body.get("unit_of_measurement") or body.get("unit") or body.get("uom")
            if unit:
                out["unit"] = str(unit).strip().lower()[:8] or out["unit"]
    if bird_sensor_id:
        body = _fetch_esphome_json(base_url, f"binary_sensor/{quote(bird_sensor_id, safe='')}")
        if body:
            bp = _parse_bool_state(body.get("state"))
            if bp is not None:
                out["bird_present"] = bp

    if "weight" not in out and "bird_present" not in out:
        return None
    return out


def _weight_trend_from_grams(grams: float, *, noise_threshold_g: float = 5.0) -> str:
    if abs(grams) <= float(noise_threshold_g):
        return "stable"
    return "up" if grams > 0 else "down"


def video_scales_estimate_payload(video) -> dict | None:
    """Блок для карточки записи: дельта массы в единицах из настроек (#167)."""
    val = getattr(video, "scales_weight_delta_kg", None)
    if val is None:
        return None
    try:
        kg = float(val)
    except (TypeError, ValueError):
        return None
    if abs(kg) > 50:
        return None
    unit = (app_config.get("integrations.scales.unit") or "g").strip().lower() or "g"
    grams = round(kg * 1000.0, 1) if unit == "g" else round(kg * 1000.0, 1)
    trend = _weight_trend_from_grams(grams)
    if unit == "g":
        return {
            "delta_kg": kg,
            "display_value": round(abs(kg * 1000.0), 1),
            "display_unit": "g",
            "weight_change_grams": round(kg * 1000.0, 1),
            "weight_trend": trend,
        }
    return {
        "delta_kg": kg,
        "display_value": round(abs(kg), 4),
        "display_unit": "kg",
        "weight_change_grams": grams,
        "weight_trend": trend,
    }


def scale_mqtt_command_topic() -> str | None:
    """Топик команд (тара): явный или ``{mqtt_topic_prefix}/command``."""
    explicit = (app_config.get("integrations.scales.mqtt_command_topic") or "").strip()
    if explicit:
        return explicit
    prefix = (app_config.get("integrations.scales.mqtt_topic_prefix") or "").strip().strip("/")
    return f"{prefix}/command" if prefix else None


def scale_tare_available() -> bool:
    """Можно ли отправить тару в активный источник весов."""
    if not app_config.get("integrations.scales.enabled"):
        return False
    src = normalize_scales_source(app_config.get("integrations.scales.source"))
    if scales_source_uses_mqtt(src):
        return scale_mqtt_command_topic() is not None
    if src == SCALES_SOURCE_ESPHOME:
        base_url = (app_config.get("integrations.scales.esphome_url") or "").strip()
        button_id = (app_config.get("integrations.scales.esphome_tare_button_id") or "").strip()
        return bool(base_url and button_id)
    return False


def scale_tare_mqtt_available() -> bool:
    """Backward-compatible alias: now means any tare-capable source."""
    return scale_tare_available()


def trigger_scale_tare() -> tuple[bool, str]:
    """Send tare command via active scales source."""
    src = normalize_scales_source(app_config.get("integrations.scales.source"))
    if scales_source_uses_mqtt(src):
        topic = scale_mqtt_command_topic()
        if not topic:
            return False, "no_command_topic"
        payload = (app_config.get("integrations.scales.mqtt_tare_payload") or "TARE").strip() or "TARE"
        return mqtt_publish_once(topic, payload, qos=1)
    if src == SCALES_SOURCE_ESPHOME:
        base_url = (app_config.get("integrations.scales.esphome_url") or "").strip()
        button_id = (app_config.get("integrations.scales.esphome_tare_button_id") or "").strip()
        if not base_url or not button_id:
            return False, "no_tare_button"
        try:
            r = requests.post(
                f"{base_url.rstrip('/')}/button/{quote(button_id, safe='')}/press",
                timeout=5,
            )
            r.raise_for_status()
            return True, "ok"
        except requests.RequestException as e:
            logger.warning("ESPHome tare failed: %s", e)
            return False, str(e)
    return False, "tare_not_supported"


def publish_scale_tare_via_mqtt() -> tuple[bool, str]:
    """Backward-compatible alias: now routes tare by active source."""
    return trigger_scale_tare()


def get_feeder_scale_snapshot() -> dict | None:
    """{ weight?, unit, updated_at, bird_present?, source? } или None."""
    if not app_config.get("integrations.scales.enabled"):
        return None
    src = normalize_scales_source(app_config.get("integrations.scales.source"))
    if src == SCALES_SOURCE_HOMEASSISTANT:
        eid = (app_config.get("integrations.scales.homeassistant_entity_id") or "").strip()
        return _fetch_ha_scale(eid)
    if src == SCALES_SOURCE_ESPHOME:
        return _fetch_esphome_scale()
    raw = _read_scale_file()
    if not raw:
        return None
    weight_f = None
    try:
        w = raw.get("weight")
        if w is not None and str(w).strip() != "":
            weight_f = float(w)
    except (TypeError, ValueError):
        weight_f = None
    bp_raw = raw.get("bird_present")
    bp_out = None
    bp_out = _parse_bool_state(bp_raw)
    if weight_f is None and bp_out is None:
        return None
    out: dict = {
        "unit": str(raw.get("unit") or "g").lower()[:8],
        "updated_at": raw.get("updated_at"),
        "source": src,
    }
    if weight_f is not None:
        out["weight"] = weight_f
    if bp_out is not None:
        out["bird_present"] = bp_out
    return out
