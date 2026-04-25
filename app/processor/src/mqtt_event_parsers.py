"""Pure MQTT payload parsers used by the processor MQTT aggregator."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def _parse_iso8601_utc(value) -> datetime | None:
    if not value:
        return None
    try:
        ts = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(timezone.utc)


def _parse_bird_present_payload(payload: bytes) -> bool | None:
    """ON/OFF, 1/0, true/false — as HA binary_sensor / ESPHome."""
    if not payload:
        return None
    try:
        raw = payload.decode("utf-8", errors="replace").strip().lower()
    except Exception:
        return None
    if raw in ("on", "true", "1", "yes"):
        return True
    if raw in ("off", "false", "0", "no"):
        return False
    return None


def _parse_scale_payload(payload: bytes) -> float | None:
    """Parse weight from plain text, JSON {value|weight|state}, or HA state string."""
    if not payload:
        return None
    try:
        raw = payload.decode("utf-8", errors="replace").strip()
    except Exception:
        return None
    if not raw:
        return None
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            for key in ("value", "weight", "state", "Weight"):
                value = data.get(key)
                if value is not None and str(value).strip() != "":
                    return float(str(value).replace(",", "."))
        return float(data)
    except (json.JSONDecodeError, TypeError, ValueError):
        pass
    try:
        return float(raw.replace(",", "."))
    except ValueError:
        return None


def _frigate_labels_match_exclude(labels: set, exclude: set) -> bool:
    """True if any non-empty label matches ``exclude`` case-insensitively."""
    if not exclude:
        return False
    excluded = {str(item).strip().lower() for item in exclude if item is not None and str(item).strip()}
    if not excluded:
        return False
    for label in labels:
        if label is None:
            continue
        normalized = str(label).strip().lower()
        if normalized and normalized in excluded:
            return True
    return False


def _frigate_dict_has_box_or_region(obj: dict) -> bool:
    """True if Frigate object state has box or region coordinates."""
    box = obj.get("box")
    if isinstance(box, (list, tuple)) and len(box) >= 4:
        return True
    if box is not None and box != "":
        return True
    region = obj.get("region")
    if isinstance(region, (list, tuple)) and len(region) >= 2:
        return True
    if region is not None and region != "":
        return True
    return False


def _frigate_after_has_tracked_geometry(after: dict) -> bool:
    """True if Frigate ``after`` carries a tracked box/region."""
    if not isinstance(after, dict):
        return False
    if _frigate_dict_has_box_or_region(after):
        return True
    snap = after.get("snapshot")
    if isinstance(snap, dict) and _frigate_dict_has_box_or_region(snap):
        return True
    return False


def _parse_frigate_event_dict(data: dict) -> dict | None:
    """Parse Frigate JSON object (already decoded). Uses after for final state."""
    if not isinstance(data, dict):
        return None
    after = data.get("after") or data
    before = data.get("before") or {}
    camera = after.get("camera") or before.get("camera", "")
    label = after.get("label") or before.get("label", "")
    sub_label_raw = after.get("sub_label") or before.get("sub_label")
    sub_label = ""
    if isinstance(sub_label_raw, str):
        sub_label = sub_label_raw
    elif isinstance(sub_label_raw, (list, tuple)) and sub_label_raw:
        sub_label = str(sub_label_raw[0]) if sub_label_raw else ""
    score = after.get("top_score") or after.get("score") or before.get("top_score") or before.get("score", 0)
    try:
        confidence = float(score)
    except (TypeError, ValueError):
        confidence = 0.0
    frame_time = after.get("frame_time") or before.get("frame_time") or data.get("frame_time")
    if frame_time is not None:
        try:
            ts = datetime.fromtimestamp(float(frame_time), tz=timezone.utc)
            timestamp = ts.isoformat()
        except (ValueError, TypeError, OSError):
            timestamp = datetime.now(timezone.utc).isoformat()
    else:
        timestamp = datetime.now(timezone.utc).isoformat()
    return {
        "source": "frigate",
        "species": sub_label or label or "unknown",
        "label": label,
        "sub_label": sub_label,
        "confidence": confidence,
        "camera": camera,
        "timestamp": timestamp,
    }


def _parse_frigate_event(payload):
    """Parse Frigate event bytes (MQTT payload)."""
    try:
        data = json.loads(payload.decode())
    except (json.JSONDecodeError, UnicodeDecodeError) as err:
        logger.warning("Frigate parse error: %s", err)
        return None
    return _parse_frigate_event_dict(data)


def _parse_frigate_snapshot_topic(topic: str) -> tuple[str, str] | None:
    """Parse topic ``<prefix>/<camera>/<label>/snapshot`` -> (camera, label)."""
    parts = [part for part in str(topic or "").split("/") if part]
    if len(parts) < 4:
        return None
    if parts[-1].lower() != "snapshot":
        return None
    camera = parts[-3].strip()
    label = parts[-2].strip()
    if not camera or not label:
        return None
    return camera, label


def _parse_birdnet_event_with_reason(payload):
    """Return ``(event, reason_code)`` for BirdNET-Pi/BirdNET-Go MQTT payloads."""
    try:
        data = json.loads(payload.decode())
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None, "parse_json_error"
    if not isinstance(data, dict):
        return None, "payload_not_object"

    species = (
        data.get("Common_Name")
        or data.get("CommonName")
        or data.get("comname")
        or data.get("species")
        or data.get("common_name")
        or data.get("label")
        or data.get("Com_Name")
        or "unknown"
    )
    species = str(species).strip() if species is not None else "unknown"
    if not species:
        species = "unknown"
    conf_raw = (
        data.get("Confidence_Score") or data.get("confidence") or data.get("score") or data.get("Confidence") or 0
    )
    try:
        confidence = float(str(conf_raw).replace(",", "."))
    except (ValueError, TypeError):
        confidence = 0.0

    source_obj = data.get("Source")
    audio_source = None
    if isinstance(source_obj, dict):
        audio_source = (
            source_obj.get("displayName")
            or source_obj.get("safeString")
            or source_obj.get("name")
            or source_obj.get("id")
        )
    elif source_obj not in (None, ""):
        audio_source = str(source_obj)
    if not audio_source:
        audio_source = data.get("SourceNode") or data.get("source_node") or data.get("audio_source")

    ts_str = data.get("BeginTime") or data.get("Date") or data.get("timestamp")
    ts = _parse_iso8601_utc(ts_str)
    ts_reason = "provided"
    if ts is None:
        ts = datetime.now(timezone.utc)
        ts_reason = "fallback_now"
    timestamp = ts.isoformat()

    ev = {
        "source": "birdnet",
        "species": species,
        "common_name": species,
        "confidence": confidence,
        "timestamp": timestamp,
        "_ts_epoch": ts.timestamp(),
    }
    if data.get("ScientificName"):
        ev["scientific_name"] = data["ScientificName"]
    if data.get("SpeciesCode"):
        ev["species_code"] = data["SpeciesCode"]
    if audio_source:
        ev["audio_source"] = str(audio_source)
    if data.get("camera") or data.get("CameraId") or data.get("camera_id"):
        ev["camera_id"] = data.get("camera") or data.get("CameraId") or data.get("camera_id")
    if data.get("site_id") or data.get("SiteId"):
        ev["site_id"] = data.get("site_id") or data.get("SiteId")
    bird_img = data.get("BirdImage")
    if isinstance(bird_img, dict) and bird_img.get("URL"):
        ev["bird_image_url"] = bird_img["URL"]
    if species.lower() == "unknown":
        return ev, f"ok_unknown_species_timestamp_{ts_reason}"
    return ev, f"ok_timestamp_{ts_reason}"


def _parse_birdnet_event(payload):
    """Back-compatible helper returning event only."""
    ev, _ = _parse_birdnet_event_with_reason(payload)
    return ev
