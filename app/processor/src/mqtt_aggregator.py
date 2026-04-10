"""
MQTT event aggregator: subscribes to Frigate and BirdNET, stores events for merging,
publishes to birdlense/detections for HA.
Supports Home Assistant MQTT Autodiscovery when ha_discovery=true.

Outbound publishes from the processor main thread go through ``_publish_queue`` and are
sent only from the MQTT network loop thread (single writer to ``Client.publish``).
On broker disconnect the queue is **retained** (and new publishes still enqueue if the
broker is configured) so messages flush after reconnect; ``stop()`` clears the queue.

Feeder-scale JSON state + JSONL history are written from a **dedicated daemon thread**
(queued from ``_on_message``) so disk I/O does not block the MQTT client loop (#265).
"""
import json
import logging
import os
import queue
import threading
import time
from collections import deque
from datetime import datetime, timezone

import paho.mqtt.client as mqtt

from app_config.app_config import app_config
from scale_sample_log import append_feeder_scale_sample, weight_reading_to_kg

logger = logging.getLogger(__name__)

# After TCP drop, still report "connected" to heartbeat/UI for this many seconds.
MQTT_DISCONNECT_DISPLAY_GRACE_SEC = 120

FEEDER_SCALE_STATE_FILE = "feeder_scale_state.json"


def _normalize_obs_level(raw) -> str:
    v = str(raw or "info").strip().lower()
    if v in ("off", "info", "debug"):
        return v
    return "info"


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
    """ON/OFF, 1/0, true/false — как HA binary_sensor / ESPHome."""
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
    """Число веса из plain text, JSON {value|weight|state} или HA state string."""
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
            for k in ("value", "weight", "state", "Weight"):
                v = data.get(k)
                if v is not None and str(v).strip() != "":
                    return float(str(v).replace(",", "."))
        return float(data)
    except (json.JSONDecodeError, TypeError, ValueError):
        pass
    try:
        return float(raw.replace(",", "."))
    except ValueError:
        return None


def write_feeder_scale_state(
    data_dir: str,
    weight: float | None = None,
    unit: str | None = None,
    *,
    bird_present: bool | None = None,
    history_max_lines: int = 10000,
) -> None:
    """Сохранить вес и/или bird_present для UI; журнал JSONL только при новом весе."""
    try:
        os.makedirs(data_dir, exist_ok=True)
        path = os.path.join(data_dir, FEEDER_SCALE_STATE_FILE)
        now = datetime.now(timezone.utc).isoformat()
        prev: dict = {}
        if os.path.isfile(path):
            try:
                with open(path, encoding="utf-8") as f:
                    prev = json.load(f)
            except (OSError, json.JSONDecodeError):
                prev = {}
        rec = dict(prev)
        rec["updated_at"] = now
        if weight is not None:
            u = (unit or rec.get("unit") or "kg")
            u = str(u).strip().lower()[:8] or "kg"
            rec["weight"] = float(weight)
            rec["unit"] = u
            append_feeder_scale_sample(data_dir, float(weight), u, max_lines=history_max_lines)
        if bird_present is not None:
            rec["bird_present"] = bool(bird_present)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(rec, f, ensure_ascii=False)
    except OSError as e:
        logger.debug("write_feeder_scale_state: %s", e)


# HA Discovery state topics (we publish state here)
HA_TOPIC_LAST_SPECIES = "birdlense/sensor/last_species/state"
HA_TOPIC_LAST_CONFIDENCE = "birdlense/sensor/last_confidence/state"
HA_TOPIC_LAST_TIME = "birdlense/sensor/last_detection_time/state"
HA_TOPIC_BIRD_DETECTED = "birdlense/binary_sensor/bird_detected/state"


def _frigate_labels_match_exclude(labels: set, exclude: set) -> bool:
    """True if any non-empty label matches ``exclude`` (case-insensitive)."""
    if not exclude:
        return False
    ex = {str(x).strip().lower() for x in exclude if x is not None and str(x).strip()}
    if not ex:
        return False
    for lab in labels:
        if lab is None:
            continue
        s = str(lab).strip().lower()
        if s and s in ex:
            return True
    return False


def _frigate_dict_has_box_or_region(obj: dict) -> bool:
    """True if Frigate object state has box or region (coordinates may be nested)."""
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
    """True if Frigate ``after`` carries a tracked box/region (incl. ``snapshot.box`` on newer Frigate)."""
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
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        logger.warning("Frigate parse error: %s", e)
        return None
    return _parse_frigate_event_dict(data)


def _parse_frigate_snapshot_topic(topic: str) -> tuple[str, str] | None:
    """Parse topic ``<prefix>/<camera>/<label>/snapshot`` -> (camera, label)."""
    parts = [p for p in str(topic or '').split('/') if p]
    if len(parts) < 4:
        return None
    if parts[-1].lower() != 'snapshot':
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
    # BirdNET-Pi: Common_Name, Confidence_Score
    # BirdNET-Go: CommonName, Confidence
    species = (
        data.get("Common_Name") or data.get("CommonName") or
        data.get("comname") or data.get("species") or
        data.get("common_name") or data.get("label") or
        data.get("Com_Name") or "unknown"
    )
    species = str(species).strip() if species is not None else "unknown"
    if not species:
        species = "unknown"
    conf_raw = (
        data.get("Confidence_Score") or data.get("confidence") or
        data.get("score") or data.get("Confidence") or 0
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
        audio_source = (
            data.get("SourceNode")
            or data.get("source_node")
            or data.get("audio_source")
        )

    # BirdNET-Go: BeginTime — точное время детекции для слияния с YOLO/Frigate
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
    # BirdNET-Go: ScientificName для маппинга, BirdImage.URL для UI
    if data.get("ScientificName"):
        ev["scientific_name"] = data["ScientificName"]
    if data.get("SpeciesCode"):
        ev["species_code"] = data["SpeciesCode"]
    if audio_source:
        ev["audio_source"] = str(audio_source)
    if data.get("camera") or data.get("CameraId") or data.get("camera_id"):
        ev["camera_id"] = (
            data.get("camera")
            or data.get("CameraId")
            or data.get("camera_id")
        )
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


class MQTTEventAggregator:
    """
    Subscribes to frigate/events and birdnet/sightings.
    Stores events for merging, publishes to birdlense/detections.
    """

    def __init__(
        self,
        broker: str,
        port: int = 1883,
        frigate_topic: str = "frigate/events",
        birdnet_topic: str = "birdnet",
        publish_topic: str = "birdlense/detections",
        username=None,
        password=None,
        max_events: int = 500,
        on_frigate_motion=None,
        frigate_label_exclude=None,
        client_id: str | None = None,
        ha_discovery: bool = True,
        base_url: str = "",
        reconnect_min_delay: int = 5,
        reconnect_max_delay: int = 300,
        scales_topic: str | None = None,
        scales_data_dir: str | None = None,
        fifo_snapshot_data_dir: str | None = None,
        scales_unit: str = "kg",
        scales_history_max_lines: int = 10000,
        scale_motion_trigger_cb=None,
        scale_motion_min_delta_kg: float | None = None,
        scale_motion_debounce_seconds: float = 1.5,
        scales_bird_present_topic: str | None = None,
    ):
        """on_frigate_motion: (camera_filter, label_filter, callback). frigate_label_exclude: labels to ignore (e.g. cat, dog).
        client_id: MQTT client ID; use different ID when running test (args.input) to avoid conflict with main processor.
        ha_discovery: publish Home Assistant MQTT Autodiscovery configs on connect.
        base_url: URL for device configuration_url (e.g. http://birdlense.local:8085)."""
        base_id = client_id or os.environ.get("MQTT_CLIENT_ID", "birdlense_aggregator")
        self.client_id = f"{base_id}_{os.getpid()}"
        self.broker = broker
        self.port = port
        self.frigate_topic = frigate_topic
        fp = [x for x in (self.frigate_topic or '').split('/') if x]
        prefix = fp[0] if fp else 'frigate'
        self._frigate_snapshot_topic = f"{prefix}/+/+/snapshot"
        # Support comma-separated topics and subtree subscriptions.
        # Example: "birdnet/sightings" will also match "birdnet/sightings/#".
        self.birdnet_topics = []
        raw_birdnet = (birdnet_topic or "").strip()
        if raw_birdnet:
            parts = [p.strip() for p in raw_birdnet.split(",") if p.strip()]
            for p in parts:
                if p not in self.birdnet_topics:
                    self.birdnet_topics.append(p)
        self.publish_topic = publish_topic
        self.username = username or os.environ.get("MQTT_USERNAME")
        self.password = password or os.environ.get("MQTT_PASSWORD")
        self.max_events = max_events
        self._events = deque(maxlen=max_events)
        self._birdnet_events = deque()
        self._birdnet_event_cap = max(1000, int(max_events or 500) * 20)
        self._birdnet_obs_level = _normalize_obs_level(
            app_config.get('processor.birdnet_mqtt_observability_level', 'info')
        )
        self._birdnet_obs_debug = bool(
            app_config.get('processor.birdnet_mqtt_observability_debug', False)
        )
        self._lock = threading.Lock()
        self._publish_queue: queue.Queue[tuple[str, str | bytes, int, bool]] = queue.Queue(
            maxsize=2000
        )
        self._client = None
        self._thread = None
        self._connected = False
        self._last_connected_at = None  # for heartbeat: ok if connected or recently was
        self._stopped = False
        self._on_frigate_motion = on_frigate_motion  # (camera_filter, label_filter, callback)
        self._frigate_label_exclude = set(frigate_label_exclude or [])
        self.ha_discovery = ha_discovery
        self.base_url = (base_url or "").strip().rstrip("/")
        self.reconnect_min_delay = max(1, int(reconnect_min_delay))
        self.reconnect_max_delay = max(self.reconnect_min_delay, int(reconnect_max_delay))
        st = (scales_topic or "").strip()
        self.scales_topic = st if st else None
        sbp = (scales_bird_present_topic or "").strip()
        self.scales_bird_present_topic = sbp if sbp else None
        self.scales_data_dir = (scales_data_dir or "").strip() or None
        fs_dir = (fifo_snapshot_data_dir or "").strip()
        self._fifo_snapshot_dir = fs_dir or None
        self._fifo_snapshot_last_monotonic = 0.0
        self.scales_unit = (scales_unit or "kg").strip().lower() or "kg"
        self.scales_history_max_lines = max(100, int(scales_history_max_lines or 10000))
        self._scale_motion_trigger_cb = scale_motion_trigger_cb
        try:
            md = float(scale_motion_min_delta_kg) if scale_motion_min_delta_kg is not None else None
        except (TypeError, ValueError):
            md = None
        self._scale_motion_min_delta_kg = md if md and md > 0 else None
        try:
            self._scale_motion_debounce_seconds = max(0.2, float(scale_motion_debounce_seconds or 1.5))
        except (TypeError, ValueError):
            self._scale_motion_debounce_seconds = 1.5
        self._prev_scale_kg: float | None = None
        self._last_scale_motion_ts = 0.0
        self._feeder_scale_queue: queue.Queue | None = None

    def _ensure_feeder_scale_worker(self) -> None:
        if self._feeder_scale_queue is not None:
            return
        q: queue.Queue = queue.Queue(maxsize=200)
        self._feeder_scale_queue = q

        def _loop() -> None:
            while True:
                item = q.get()
                try:
                    if item is None:
                        break
                    write_feeder_scale_state(
                        item["data_dir"],
                        item.get("weight"),
                        item.get("unit"),
                        bird_present=item.get("bird_present"),
                        history_max_lines=item["history_max_lines"],
                    )
                except Exception as e:
                    logger.debug("feeder scale worker: %s", e)
                finally:
                    q.task_done()

        threading.Thread(
            target=_loop,
            daemon=True,
            name="birdlense-feeder-scale-io",
        ).start()

    def _enqueue_feeder_scale_write(
        self,
        *,
        weight: float | None,
        unit: str | None,
        bird_present: bool | None,
    ) -> None:
        ddir = self.scales_data_dir
        if not ddir:
            return
        self._ensure_feeder_scale_worker()
        assert self._feeder_scale_queue is not None
        try:
            self._feeder_scale_queue.put_nowait(
                {
                    "data_dir": ddir,
                    "weight": weight,
                    "unit": unit,
                    "bird_present": bird_present,
                    "history_max_lines": self.scales_history_max_lines,
                }
            )
        except queue.Full:
            logger.warning(
                "feeder scale write queue full; dropping MQTT scale update",
            )

    def _birdnet_log(self, level: str, message: str, *args) -> None:
        level_norm = str(level or 'info').strip().lower()
        if self._birdnet_obs_level == 'off':
            return
        if level_norm == 'debug':
            if self._birdnet_obs_level == 'debug' or self._birdnet_obs_debug:
                logger.info(message, *args)
            return
        if level_norm == 'info' and self._birdnet_obs_level in ('info', 'debug'):
            logger.info(message, *args)

    def _validate_normalized_event(self, ev: dict) -> None:
        """Сверка нормализованного события с Pydantic-схемой (``schemas.events``)."""
        try:
            from schemas.events import validate_mqtt_detection_dict
        except ImportError:
            return
        _, err = validate_mqtt_detection_dict(ev)
        if err:
            logger.warning(
                "MQTT normalized event failed schema check: %s | keys=%s | source=%s",
                err,
                sorted(ev.keys()),
                ev.get("source"),
            )

    def _prune_birdnet_events_locked(self, now=None, ttl_hours: float = 25.0) -> None:
        now = now or datetime.now(timezone.utc)
        try:
            ttl_hours = float(ttl_hours)
        except (TypeError, ValueError):
            ttl_hours = 25.0
        ttl_hours = max(1.0, min(ttl_hours, 168.0))
        low_epoch = now.timestamp() - (ttl_hours * 3600.0)
        kept = deque()
        for ev in self._birdnet_events:
            ts_epoch = ev.get("_ts_epoch")
            if ts_epoch is None:
                ts = _parse_iso8601_utc(ev.get("timestamp"))
                if ts is None:
                    continue
                ts_epoch = ts.timestamp()
                ev["_ts_epoch"] = ts_epoch
            else:
                # If timestamp string is missing/unparseable, still honor explicit epoch.
                ts = _parse_iso8601_utc(ev.get("timestamp"))
                if ts is not None:
                    parsed_epoch = ts.timestamp()
                    # Prefer parsed string if it disagrees materially with stored epoch.
                    if abs(float(parsed_epoch) - float(ts_epoch)) > 1.0:
                        ts_epoch = parsed_epoch
                        ev["_ts_epoch"] = ts_epoch
            if ts_epoch >= low_epoch:
                kept.append(ev)
        # FIFO cap: drop oldest *within TTL window* only. Previously this could
        # remove still-valid history when transient spam arrived, collapsing support_count.
        overflow = max(0, len(kept) - int(self._birdnet_event_cap))
        if overflow:
            kept = deque(list(kept)[overflow:])
        before_count = len(self._birdnet_events)
        after_count = len(kept)
        self._birdnet_events = kept
        expired_dropped = max(0, before_count - after_count - overflow)
        if expired_dropped or overflow:
            self._birdnet_log(
                'info',
                'BirdNET FIFO prune: reason=ttl_or_fifo cap=%s before=%s after=%s '
                'expired_dropped=%s fifo_dropped=%s ttl_hours=%.2f',
                self._birdnet_event_cap,
                before_count,
                after_count,
                expired_dropped,
                overflow,
                ttl_hours,
            )
        self._maybe_write_birdnet_fifo_snapshot_locked()

    def _maybe_write_birdnet_fifo_snapshot_locked(self) -> None:
        """Обновить JSON-снимок FIFO (только под lock; дешёвый no-op если рано для throttle)."""
        if not self._fifo_snapshot_dir:
            return
        if not bool(app_config.get("processor.birdnet_fifo_snapshot_enabled", True)):
            return
        try:
            interval = float(app_config.get("processor.birdnet_fifo_snapshot_interval_sec") or 3)
        except (TypeError, ValueError):
            interval = 3.0
        interval = max(1.0, min(interval, 300.0))
        now_m = time.monotonic()
        if now_m - self._fifo_snapshot_last_monotonic < interval:
            return
        from birdnet_fifo_snapshot import write_birdnet_fifo_snapshot

        try:
            write_birdnet_fifo_snapshot(
                data_dir=self._fifo_snapshot_dir,
                events=list(self._birdnet_events),
                fifo_cap=self._birdnet_event_cap,
                mqtt_connected=bool(self._connected),
                processor_pid=os.getpid(),
            )
            self._fifo_snapshot_last_monotonic = now_m
        except Exception:
            logger.debug("BirdNET FIFO snapshot failed", exc_info=True)

    def _remember_birdnet_event(self, ev: dict) -> None:
        with self._lock:
            # Prefer parsing the canonical timestamp string when available; otherwise
            # keep caller-provided epoch (tests / edge MQTT payloads).
            ts = _parse_iso8601_utc(ev.get("timestamp"))
            if ts is not None:
                ev["_ts_epoch"] = ts.timestamp()
                ts_reason = 'timestamp_parse_ok'
            elif ev.get("_ts_epoch") is None:
                self._birdnet_log(
                    'info',
                    'BirdNET FIFO ingest: reason=drop_no_timestamp species=%s confidence=%s',
                    ev.get('species', 'unknown'),
                    ev.get('confidence', 0.0),
                )
                return
            else:
                ts_reason = 'timestamp_epoch_fallback'
            self._birdnet_events.append(ev)
            self._birdnet_log(
                'debug',
                'BirdNET FIFO ingest: reason=accepted_%s species=%s confidence=%.3f queue_len=%s cap=%s',
                ts_reason,
                ev.get('species', 'unknown'),
                float(ev.get('confidence') or 0.0),
                len(self._birdnet_events),
                self._birdnet_event_cap,
            )
            # Prune relative to the newest event time, not wall clock: unit tests and
            # offline replays may inject historical timestamps while host time differs.
            prune_now = ts or datetime.fromtimestamp(float(ev["_ts_epoch"]), tz=timezone.utc)
            self._prune_birdnet_events_locked(now=prune_now)

    def _on_connect(self, client, userdata, flags, reason_code, properties=None):
        if reason_code == 0:
            self._connected = True
            self._last_connected_at = time.time()
            logger.info("MQTT aggregator connected")
            if self.ha_discovery:
                time.sleep(0.3)
                self._publish_ha_discovery()
        else:
            self._connected = False
            logger.warning(f"MQTT aggregator connect failed: {reason_code}")

    def _publish_ha_discovery(self):
        """Publish Home Assistant MQTT Autodiscovery configs."""
        if not self._client or not self._connected:
            return
        prefix = "homeassistant"
        device = {
            "identifiers": ["birdlense_hub"],
            "name": "BirdLense Hub",
            "manufacturer": "BirdLense",
            "model": "Hub",
        }
        if self.base_url:
            device["configuration_url"] = self.base_url
        try:
            # sensor: last_species
            cfg = {
                "name": "Last Species",
                "state_topic": HA_TOPIC_LAST_SPECIES,
                "unique_id": "birdlense_last_species",
                "device": device,
                "availability": [{"topic": "birdlense/status"}],
            }
            self._client.publish(
                f"{prefix}/sensor/birdlense_last_species/config",
                json.dumps(cfg),
                qos=1,
                retain=True,
            )
            # sensor: last_confidence
            cfg = {
                "name": "Last Confidence",
                "state_topic": HA_TOPIC_LAST_CONFIDENCE,
                "unique_id": "birdlense_last_confidence",
                "device": device,
                "availability": [{"topic": "birdlense/status"}],
            }
            self._client.publish(
                f"{prefix}/sensor/birdlense_last_confidence/config",
                json.dumps(cfg),
                qos=1,
                retain=True,
            )
            # sensor: last_detection_time
            cfg = {
                "name": "Last Detection Time",
                "state_topic": HA_TOPIC_LAST_TIME,
                "unique_id": "birdlense_last_detection_time",
                "device": device,
                "availability": [{"topic": "birdlense/status"}],
            }
            self._client.publish(
                f"{prefix}/sensor/birdlense_last_detection_time/config",
                json.dumps(cfg),
                qos=1,
                retain=True,
            )
            # binary_sensor: bird_detected (off_delay: 300 = OFF 5 min after last ON)
            cfg = {
                "name": "Bird at Feeder",
                "state_topic": HA_TOPIC_BIRD_DETECTED,
                "payload_on": "ON",
                "payload_off": "OFF",
                "off_delay": 300,
                "unique_id": "birdlense_bird_detected",
                "device": device,
                "availability": [{"topic": "birdlense/status"}],
            }
            self._client.publish(
                f"{prefix}/binary_sensor/birdlense_bird_detected/config",
                json.dumps(cfg),
                qos=1,
                retain=True,
            )
            # Initial state: bird_detected OFF
            self._client.publish(HA_TOPIC_BIRD_DETECTED, "OFF", qos=1, retain=True)
            logger.info("Home Assistant MQTT Autodiscovery configs published")
        except Exception as e:
            logger.warning("HA discovery publish failed: %s", e)

    def _on_disconnect(self, client, userdata, *args):
        self._connected = False
        reason = args[0] if args else "unknown"
        logger.warning(f"MQTT aggregator disconnected: {reason}")

    def _clear_publish_queue(self) -> None:
        while True:
            try:
                self._publish_queue.get_nowait()
            except queue.Empty:
                break

    def _enqueue_publish(
        self, topic: str, payload: str | bytes, qos: int = 0, retain: bool = False
    ) -> None:
        if self._stopped:
            return
        try:
            self._publish_queue.put_nowait((topic, payload, qos, retain))
        except queue.Full:
            logger.warning("MQTT outbound queue full; dropping publish to %s", topic)

    def _drain_publish_queue(self, max_items: int = 500) -> None:
        """Flush queued outbound messages (only from the MQTT loop thread)."""
        if not self._client or not self._connected:
            return
        for _ in range(max_items):
            try:
                topic, payload, qos, retain = self._publish_queue.get_nowait()
            except queue.Empty:
                break
            try:
                self._client.publish(topic, payload, qos=qos, retain=retain)
            except Exception as e:
                logger.warning("MQTT publish failed (drain): %s", e)

    def _on_message(self, client, userdata, msg):
        ev = None
        if msg.topic == self.frigate_topic:
            try:
                fdata = json.loads(msg.payload.decode())
            except (json.JSONDecodeError, UnicodeDecodeError) as e:
                logger.warning("Frigate parse error: %s", e)
                return
            after = fdata.get("after") or fdata
            ev = _parse_frigate_event_dict(fdata)
            if ev is None:
                plen = len(msg.payload) if msg.payload else 0
                logger.debug(
                    "MQTT frigate: parse returned None topic=%s payload_len=%s",
                    msg.topic,
                    plen,
                )
            if ev:
                label = ev.get("label", "")
                sub_label = ev.get("sub_label", "")
                species = ev.get("species", "")
                labels = {label, sub_label, species} if sub_label else {label, species}
                # Excluded labels must not enter merge/fusion (no «cat» as species),
                # but must NOT block motion/recording: OpenCV may miss night/mice while
                # Frigate already has a tracked box (e.g. cat mis-ID for mouse).
                skip_merge_queue = bool(
                    self._frigate_label_exclude
                    and _frigate_labels_match_exclude(
                        labels, self._frigate_label_exclude
                    )
                )
                if skip_merge_queue:
                    logger.debug(
                        "Frigate exclude list (suppress YOLO merge only): label=%s sub=%s",
                        label,
                        sub_label,
                    )
                    ev["_frigate_merge_suppressed"] = True
                if self._on_frigate_motion:
                    cam_f, lbl_f, cb = self._on_frigate_motion
                    camera = ev.get("camera", "")
                    cam_lower = {
                        str(c).strip().lower() for c in cam_f if str(c).strip()
                    }
                    # Пустой camera_filter = любая камера (как пустой label_filter).
                    cam_ok = (not cam_lower) or (
                        str(camera or "").strip().lower() in cam_lower
                    )
                    labels_lower = {s.lower() for s in labels}
                    lbl_f_lower = {s.lower() for s in lbl_f}
                    # Empty label filter means wildcard (accept any label).
                    lbl_ok = (not lbl_f_lower) or bool(lbl_f_lower & labels_lower)
                    relaxed = bool(
                        app_config.get('motion.frigate_trigger_on_tracked_object', True)
                    )
                    has_geometry = _frigate_after_has_tracked_geometry(
                        after if isinstance(after, dict) else {}
                    )
                    accepted_by = 'label_filter'
                    if not lbl_ok and relaxed and has_geometry:
                        lbl_ok = True
                        accepted_by = 'geometry_fallback'
                        if skip_merge_queue:
                            logger.info(
                                "Frigate trigger: geometry fallback (excluded label, recording only) "
                                "camera=%s label=%s",
                                camera,
                                label,
                            )
                        else:
                            logger.info(
                                "Frigate trigger: geometry fallback (label not in filter) "
                                "camera=%s label=%s sub_label=%s",
                                camera, label, sub_label,
                            )
                    if cam_ok and lbl_ok:
                        logger.info(
                            "Frigate trigger accepted: reason=%s camera=%s label=%s sub_label=%s "
                            "merge_suppressed=%s has_geometry=%s filter_empty=%s",
                            accepted_by,
                            camera,
                            label,
                            sub_label,
                            skip_merge_queue,
                            has_geometry,
                            not bool(lbl_f_lower),
                        )
                        try:
                            cb(camera, species)
                        except Exception as e:
                            logger.debug("Frigate motion callback: %s", e)
                    else:
                        reasons = []
                        if not cam_ok:
                            reasons.append('camera_filter_miss')
                        if not lbl_ok:
                            if bool(lbl_f_lower):
                                reasons.append('label_filter_miss')
                            if not has_geometry:
                                reasons.append('no_tracked_geometry')
                        logger.info(
                            "Frigate trigger rejected: reason=%s camera=%s label=%s sub_label=%s "
                            "camera_filter=%s label_filter=%s has_geometry=%s relaxed=%s",
                            ','.join(reasons) if reasons else 'unknown',
                            camera,
                            label,
                            sub_label,
                            list(cam_f) if cam_f else "none",
                            list(lbl_f) if lbl_f else "any",
                            has_geometry,
                            relaxed,
                        )
        elif mqtt.topic_matches_sub(getattr(self, '_frigate_snapshot_topic', ''), msg.topic):
            # Fallback when frigate/events is sparse/disabled: topic like
            # frigate/<camera>/<label>/snapshot (ignore retained bootstrap payloads).
            if getattr(msg, 'retain', False):
                return
            parsed = _parse_frigate_snapshot_topic(msg.topic)
            if parsed:
                camera, label = parsed
                ev = {
                    'source': 'frigate',
                    'species': label,
                    'label': label,
                    'sub_label': '',
                    'confidence': 0.0,
                    'camera': camera,
                    'timestamp': datetime.now(timezone.utc).isoformat(),
                }
                after = {}
                labels = {label}
                skip_merge_queue = bool(
                    self._frigate_label_exclude
                    and _frigate_labels_match_exclude(
                        labels, self._frigate_label_exclude
                    )
                )
                if skip_merge_queue:
                    ev["_frigate_merge_suppressed"] = True
                if self._on_frigate_motion:
                    cam_f, lbl_f, cb = self._on_frigate_motion
                    cam_lower = {
                        str(c).strip().lower() for c in cam_f if str(c).strip()
                    }
                    cam_ok = (not cam_lower) or (
                        str(camera or "").strip().lower() in cam_lower
                    )
                    labels_lower = {s.lower() for s in labels}
                    lbl_f_lower = {s.lower() for s in lbl_f}
                    lbl_ok = (not lbl_f_lower) or bool(lbl_f_lower & labels_lower)
                    if cam_ok and lbl_ok:
                        logger.info(
                            "Frigate trigger accepted: reason=snapshot_topic camera=%s "
                            "label=%s sub_label=%s merge_suppressed=%s has_geometry=%s filter_empty=%s",
                            camera,
                            label,
                            '',
                            skip_merge_queue,
                            False,
                            not bool(lbl_f_lower),
                        )
                        try:
                            cb(camera, label)
                        except Exception as e:
                            logger.debug("Frigate motion callback: %s", e)
                    else:
                        reasons = []
                        if not cam_ok:
                            reasons.append('camera_filter_miss')
                        if not lbl_ok:
                            reasons.append('label_filter_miss')
                        logger.info(
                            "Frigate trigger rejected: reason=%s camera=%s label=%s "
                            "sub_label=%s camera_filter=%s label_filter=%s has_geometry=%s relaxed=%s",
                            ','.join(reasons) if reasons else 'unknown',
                            camera,
                            label,
                            '',
                            list(cam_f) if cam_f else "none",
                            list(lbl_f) if lbl_f else "any",
                            False,
                            False,
                        )
        elif any(
            mqtt.topic_matches_sub(sub, msg.topic)
            for sub in getattr(self, 'birdnet_topics', ())
        ):
            ev, reason = _parse_birdnet_event_with_reason(msg.payload)
            if ev is None:
                plen = len(msg.payload) if msg.payload else 0
                self._birdnet_log(
                    'info',
                    'BirdNET MQTT event: reason=%s topic=%s payload_len=%s',
                    reason,
                    msg.topic,
                    plen,
                )
            else:
                self._birdnet_log(
                    'debug',
                    'BirdNET MQTT event: reason=%s topic=%s species=%s confidence=%.3f audio_source=%s',
                    reason,
                    msg.topic,
                    ev.get('species', 'unknown'),
                    float(ev.get('confidence') or 0.0),
                    ev.get('audio_source', ''),
                )
        elif self.scales_topic and msg.topic == self.scales_topic:
            w = _parse_scale_payload(msg.payload)
            if w is not None and self.scales_data_dir:
                self._enqueue_feeder_scale_write(
                    weight=w,
                    unit=self.scales_unit,
                    bird_present=None,
                )
                logger.debug("Scales MQTT: weight=%s %s", w, self.scales_unit)
            if (
                w is not None
                and self._scale_motion_trigger_cb
                and self._scale_motion_min_delta_kg
            ):
                w_kg = weight_reading_to_kg(w, self.scales_unit)
                prev = self._prev_scale_kg
                self._prev_scale_kg = w_kg
                if prev is not None:
                    if abs(w_kg - prev) >= self._scale_motion_min_delta_kg:
                        now = time.time()
                        if now - self._last_scale_motion_ts >= self._scale_motion_debounce_seconds:
                            self._last_scale_motion_ts = now
                            try:
                                self._scale_motion_trigger_cb()
                            except Exception as e:
                                logger.debug("scale motion trigger cb: %s", e)
            return
        elif (
            self.scales_bird_present_topic
            and msg.topic == self.scales_bird_present_topic
        ):
            bp = _parse_bird_present_payload(msg.payload)
            if bp is not None and self.scales_data_dir:
                self._enqueue_feeder_scale_write(
                    weight=None,
                    unit=None,
                    bird_present=bp,
                )
                logger.debug("Scales MQTT: bird_present=%s", bp)
            return
        if ev:
            self._validate_normalized_event(ev)
            with self._lock:
                self._events.append(ev)
            if ev.get("source") == "birdnet":
                self._remember_birdnet_event(ev)

    def _run_client(self):
        retry_delay = self.reconnect_min_delay
        while True:
            try:
                self._client = mqtt.Client(
                    callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
                    client_id=self.client_id,
                )
                self._client.reconnect_delay_set(
                    min_delay=self.reconnect_min_delay,
                    max_delay=self.reconnect_max_delay,
                )
                if self.username:
                    self._client.username_pw_set(self.username, self.password)
                self._client.on_connect = self._on_connect
                self._client.on_disconnect = self._on_disconnect
                self._client.on_message = self._on_message
                self._client.will_set("birdlense/status", "offline", qos=1, retain=True)
                self._client.connect(self.broker, self.port, 60)
                self._client.subscribe(self.frigate_topic, qos=1)
                if self._frigate_snapshot_topic and self._frigate_snapshot_topic != self.frigate_topic:
                    self._client.subscribe(self._frigate_snapshot_topic, qos=0)
                    logger.info(
                        "MQTT: subscribed Frigate fallback snapshot topic %s",
                        self._frigate_snapshot_topic,
                    )
                for t in self.birdnet_topics:
                    self._client.subscribe(t, qos=1)
                    # If exact topic was configured, also subscribe subtree to
                    # catch common BirdNET publisher variants.
                    if "+" not in t and "#" not in t:
                        self._client.subscribe(f"{t}/#", qos=1)
                        logger.info("MQTT: subscribed BirdNET topics %s and %s/#", t, t)
                    else:
                        logger.info("MQTT: subscribed BirdNET topic %s", t)
                if self.scales_topic:
                    self._client.subscribe(self.scales_topic, qos=1)
                    logger.info("MQTT: subscribed scales weight topic %s", self.scales_topic)
                if self.scales_bird_present_topic:
                    self._client.subscribe(self.scales_bird_present_topic, qos=1)
                    logger.info(
                        "MQTT: subscribed scales bird_present topic %s",
                        self.scales_bird_present_topic,
                    )
                self._client.publish("birdlense/status", "online", qos=1, retain=True)
                retry_delay = self.reconnect_min_delay
                # Manual loop so we drain _publish_queue in the same thread as loop
                # (processor thread never calls Client.publish directly).
                while not self._stopped and self._client is not None:
                    rc = self._client.loop(timeout=0.1)
                    self._drain_publish_queue(500)
                    if rc != mqtt.MQTT_ERR_SUCCESS:
                        logger.debug("MQTT loop rc=%s, leaving inner loop", rc)
                        break
            except Exception as e:
                logger.error("MQTT aggregator error: %s, reconnecting in %ds", e, retry_delay)
            finally:
                self._connected = False
                if self._client:
                    try:
                        self._client.disconnect()
                    except Exception:
                        pass
                    self._client = None
            if self._stopped:
                break
            time.sleep(retry_delay)
            retry_delay = min(retry_delay * 2, self.reconnect_max_delay)

    def start(self):
        if not self.broker:
            logger.warning("MQTT broker not configured, aggregator disabled")
            return
        self._thread = threading.Thread(target=self._run_client, daemon=True)
        self._thread.start()
        time.sleep(0.5)

    def get_events_in_window(
        self, start_time, end_time, window_seconds=5, lookback_seconds=None
    ):
        """Return MQTT events within [start - lookback, end + window].

        lookback_seconds: if set, overrides window for low bound (для pending trigger).
        """
        from datetime import timedelta
        lookback = lookback_seconds if lookback_seconds is not None else window_seconds
        low = start_time - timedelta(seconds=lookback)
        high = end_time + timedelta(seconds=window_seconds)
        with self._lock:
            result = []
            for ev in self._events:
                ts = _parse_iso8601_utc(ev.get("timestamp"))
                if ts is None:
                    continue
                if low <= ts <= high:
                    result.append(ev)
            return result

    def get_birdnet_events(self, now=None, ttl_hours: float = 25.0) -> list[dict]:
        now = now or datetime.now(timezone.utc)
        with self._lock:
            self._prune_birdnet_events_locked(now=now, ttl_hours=ttl_hours)
            return list(self._birdnet_events)

    def get_birdnet_prior_scores(
        self,
        *,
        now=None,
        window_hours: float = 24.0,
        ttl_hours: float = 25.0,
        half_life_hours: float = 6.0,
        min_confidence: float = 0.0,
    ) -> dict[str, dict]:
        now = now or datetime.now(timezone.utc)
        try:
            window_hours = float(window_hours)
        except (TypeError, ValueError):
            window_hours = 24.0
        try:
            ttl_hours = float(ttl_hours)
        except (TypeError, ValueError):
            ttl_hours = 25.0
        try:
            half_life_hours = float(half_life_hours)
        except (TypeError, ValueError):
            half_life_hours = 6.0
        try:
            min_confidence = float(min_confidence)
        except (TypeError, ValueError):
            min_confidence = 0.0

        window_hours = max(0.25, min(window_hours, ttl_hours))
        ttl_hours = max(window_hours, min(ttl_hours, 168.0))
        half_life_hours = max(0.1, min(half_life_hours, ttl_hours))
        min_confidence = max(0.0, min(min_confidence, 1.0))

        low_epoch = now.timestamp() - (window_hours * 3600.0)
        decay_base = 0.5
        out: dict[str, dict] = {}

        with self._lock:
            self._prune_birdnet_events_locked(now=now, ttl_hours=ttl_hours)
            for ev in self._birdnet_events:
                species = str(
                    ev.get("species")
                    or ev.get("common_name")
                    or ""
                ).strip()
                if not species or species.lower() == "unknown":
                    continue
                try:
                    conf = float(ev.get("confidence") or 0.0)
                except (TypeError, ValueError):
                    conf = 0.0
                conf = max(0.0, min(conf, 1.0))
                if conf < min_confidence:
                    continue
                ts = _parse_iso8601_utc(ev.get("timestamp"))
                if ts is None:
                    continue
                ts_epoch = ts.timestamp()
                ev["_ts_epoch"] = ts_epoch
                if ts_epoch < low_epoch:
                    continue
                age_hours = max(0.0, (now.timestamp() - ts_epoch) / 3600.0)
                decay = decay_base ** (age_hours / half_life_hours)
                weighted = conf * decay
                bucket = out.setdefault(
                    species,
                    {
                        "score": 0.0,
                        "support_count": 0,
                        "latest_seen_at": ev.get("timestamp"),
                        "scientific_name": ev.get("scientific_name"),
                        "species_code": ev.get("species_code"),
                        "audio_sources": set(),
                    },
                )
                bucket["score"] += weighted
                bucket["support_count"] += 1
                if ev.get("audio_source"):
                    bucket["audio_sources"].add(str(ev["audio_source"]))
                latest_ts = _parse_iso8601_utc(bucket.get("latest_seen_at"))
                if latest_ts is None or ts_epoch > latest_ts.timestamp():
                    bucket["latest_seen_at"] = ev.get("timestamp")
                if not bucket.get("scientific_name") and ev.get("scientific_name"):
                    bucket["scientific_name"] = ev.get("scientific_name")
                if not bucket.get("species_code") and ev.get("species_code"):
                    bucket["species_code"] = ev.get("species_code")

        for meta in out.values():
            meta["score"] = round(float(meta["score"]), 6)
            meta["audio_sources"] = sorted(meta["audio_sources"])
        self._birdnet_log(
            'debug',
            'BirdNET FIFO prior: reason=window_ready species_count=%s queue_len=%s '
            'window_hours=%.2f ttl_hours=%.2f half_life_hours=%.2f min_confidence=%.3f',
            len(out),
            len(self._birdnet_events),
            window_hours,
            ttl_hours,
            half_life_hours,
            min_confidence,
        )
        return out

    def publish_detection(self, species, confidence, source="yolo", start_time=None, end_time=None):
        """Publish detection to birdlense/detections and HA discovery state topics."""
        if self._stopped or not (self.broker or "").strip():
            return
        ts = start_time or datetime.now(timezone.utc)
        ts_iso = ts.isoformat()
        payload = {
            "species": species,
            "confidence": confidence,
            "source": source,
            "timestamp": ts_iso,
        }
        if end_time:
            payload["end_time"] = end_time.isoformat()
        self._enqueue_publish(self.publish_topic, json.dumps(payload), qos=1, retain=False)
        if self.ha_discovery:
            self._enqueue_publish(HA_TOPIC_LAST_SPECIES, str(species), qos=1, retain=True)
            self._enqueue_publish(
                HA_TOPIC_LAST_CONFIDENCE, f"{float(confidence):.2f}", qos=1, retain=True
            )
            self._enqueue_publish(HA_TOPIC_LAST_TIME, ts_iso, qos=1, retain=True)
            self._enqueue_publish(HA_TOPIC_BIRD_DETECTED, "ON", qos=1, retain=False)

    def publish_detections(self, detections, start_time, end_time):
        """Publish all detections from a video session."""
        if self._stopped or not (self.broker or "").strip():
            return
        for d in detections:
            species = d.get("species") or d.get("name", "unknown")
            conf = d.get("confidence", 0)
            src = d.get("source", "yolo")
            self.publish_detection(species, conf, src, start_time, end_time)

    def is_mqtt_live(self) -> bool:
        """True only while the broker socket is up (safe for Frigate / publish gating)."""
        return bool(self._connected)

    def is_mqtt_ok_for_heartbeat(self) -> bool:
        """True if live or disconnected within MQTT_DISCONNECT_DISPLAY_GRACE_SEC (UI / API status)."""
        if self._connected:
            return True
        if self._last_connected_at and (
            time.time() - self._last_connected_at
        ) < MQTT_DISCONNECT_DISPLAY_GRACE_SEC:
            return True
        return False

    def is_connected(self):
        """Backward compatible: relaxed status for heartbeat (see is_mqtt_ok_for_heartbeat)."""
        return self.is_mqtt_ok_for_heartbeat()

    def stop(self):
        self._stopped = True
        if self._feeder_scale_queue is not None:
            try:
                self._feeder_scale_queue.put_nowait(None)
            except queue.Full:
                pass
        self._clear_publish_queue()
        if self._client:
            self._client.disconnect()
            self._client.loop_stop()
