"""
MQTT event aggregator: subscribes to Frigate and BirdNET, stores events for merging,
publishes to birdlense/detections for HA.
Supports Home Assistant MQTT Autodiscovery when ha_discovery=true.
"""
import json
import logging
import os
import threading
import time
from collections import deque
from datetime import datetime, timezone

import paho.mqtt.client as mqtt

logger = logging.getLogger(__name__)

# HA Discovery state topics (we publish state here)
HA_TOPIC_LAST_SPECIES = "birdlense/sensor/last_species/state"
HA_TOPIC_LAST_CONFIDENCE = "birdlense/sensor/last_confidence/state"
HA_TOPIC_LAST_TIME = "birdlense/sensor/last_detection_time/state"
HA_TOPIC_BIRD_DETECTED = "birdlense/binary_sensor/bird_detected/state"


def _parse_frigate_event(payload):
    """Parse Frigate event: before/after, type (new/update/end). Uses after for final state.

    sub_label: species from Frigate Bird Classification (MobileNet INat), when enabled.
    See https://docs.frigate.video/configuration/bird_classification/
    """
    try:
        data = json.loads(payload.decode())
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        logger.warning("Frigate parse error: %s", e)
        return None
    after = data.get("after") or data
    before = data.get("before") or {}
    camera = after.get("camera") or before.get("camera", "")
    label = after.get("label") or before.get("label", "")
    # sub_label = bird species from Frigate Bird Classification (INat model)
    sub_label_raw = after.get("sub_label") or before.get("sub_label")
    sub_label = ""
    if isinstance(sub_label_raw, str):
        sub_label = sub_label_raw
    elif isinstance(sub_label_raw, (list, tuple)) and sub_label_raw:
        sub_label = str(sub_label_raw[0]) if sub_label_raw else ""
    score = after.get("top_score") or after.get("score") or before.get("top_score") or before.get("score", 0)
    # frame_time — Unix timestamp для слияния по времени (after, before, или root)
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
        "species": sub_label or label or "unknown",  # prefer sub_label (species) over label (bird)
        "label": label,
        "sub_label": sub_label,
        "confidence": float(score),
        "camera": camera,
        "timestamp": timestamp,
    }


def _parse_birdnet_event(payload):
    """Parse BirdNET-Pi (birdnet/sightings) or BirdNET-Go (birdnet) JSON.

    BirdNET-Go format: ID, SourceNode, Date, Time, BeginTime, EndTime,
    SpeciesCode, ScientificName, CommonName, Confidence, Source, BirdImage, ...
    """
    try:
        data = json.loads(payload.decode())
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
    # BirdNET-Pi: Common_Name, Confidence_Score
    # BirdNET-Go: CommonName, Confidence
    species = (
        data.get("Common_Name") or data.get("CommonName") or
        data.get("comname") or data.get("species") or
        data.get("common_name") or data.get("label") or
        data.get("Com_Name") or "unknown"
    )
    conf_raw = (
        data.get("Confidence_Score") or data.get("confidence") or
        data.get("score") or data.get("Confidence") or 0
    )
    try:
        confidence = float(str(conf_raw).replace(",", "."))
    except (ValueError, TypeError):
        confidence = 0.0

    # BirdNET-Go: BeginTime — точное время детекции для слияния с YOLO/Frigate
    ts_str = data.get("BeginTime") or data.get("Date") or data.get("timestamp")
    if ts_str:
        try:
            ts = datetime.fromisoformat(str(ts_str).replace("Z", "+00:00"))
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            timestamp = ts.isoformat()
        except (ValueError, TypeError):
            timestamp = datetime.now(timezone.utc).isoformat()
    else:
        timestamp = datetime.now(timezone.utc).isoformat()

    ev = {
        "source": "birdnet",
        "species": species,
        "confidence": confidence,
        "timestamp": timestamp,
    }
    # BirdNET-Go: ScientificName для маппинга, BirdImage.URL для UI
    if data.get("ScientificName"):
        ev["scientific_name"] = data["ScientificName"]
    bird_img = data.get("BirdImage")
    if isinstance(bird_img, dict) and bird_img.get("URL"):
        ev["bird_image_url"] = bird_img["URL"]
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
    ):
        """on_frigate_motion: (camera_filter, label_filter, callback). frigate_label_exclude: labels to ignore (e.g. cat, dog).
        client_id: MQTT client ID; use different ID when running test (args.input) to avoid conflict with main processor.
        ha_discovery: publish Home Assistant MQTT Autodiscovery configs on connect.
        base_url: URL for device configuration_url (e.g. http://birdlense.local:8085)."""
        self.client_id = client_id or os.environ.get("MQTT_CLIENT_ID", "birdlense_aggregator")
        self.broker = broker
        self.port = port
        self.frigate_topic = frigate_topic
        self.birdnet_topics = [birdnet_topic] if (birdnet_topic or "").strip() else []
        self.publish_topic = publish_topic
        self.username = username or os.environ.get("MQTT_USERNAME")
        self.password = password or os.environ.get("MQTT_PASSWORD")
        self.max_events = max_events
        self._events = deque(maxlen=max_events)
        self._lock = threading.Lock()
        self._client = None
        self._thread = None
        self._connected = False
        self._stopped = False
        self._on_frigate_motion = on_frigate_motion  # (camera_filter, label_filter, callback)
        self._frigate_label_exclude = set(frigate_label_exclude or [])
        self.ha_discovery = ha_discovery
        self.base_url = (base_url or "").strip().rstrip("/")

    def _on_connect(self, client, userdata, flags, reason_code, properties=None):
        if reason_code == 0:
            self._connected = True
            logger.info("MQTT aggregator connected")
            if self.ha_discovery:
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

    def _on_message(self, client, userdata, msg):
        ev = None
        if msg.topic == self.frigate_topic:
            ev = _parse_frigate_event(msg.payload)
            if ev:
                label = ev.get("label", "")
                sub_label = ev.get("sub_label", "")
                species = ev.get("species", "")
                labels = {label, sub_label, species} if sub_label else {label, species}
                if self._frigate_label_exclude and (labels & self._frigate_label_exclude):
                    logger.debug(
                        "Frigate event excluded (label_exclude): label=%s sub=%s",
                        label, sub_label)
                    return
                if self._on_frigate_motion:
                    cam_f, lbl_f, cb = self._on_frigate_motion
                    camera = ev.get("camera", "")
                    cam_lower = {c.lower() for c in cam_f} if cam_f else set()
                    cam_ok = not cam_f or (camera.lower() in cam_lower)
                    labels_lower = {s.lower() for s in labels}
                    lbl_f_lower = {s.lower() for s in lbl_f}
                    lbl_ok = bool(lbl_f_lower & labels_lower)
                    if cam_ok and lbl_ok:
                        logger.info(
                            "Frigate trigger: camera=%s label=%s sub_label=%s -> recording",
                            camera, label, sub_label)
                        try:
                            cb(camera, species)
                        except Exception as e:
                            logger.debug("Frigate motion callback: %s", e)
                    else:
                        logger.info(
                            "Frigate event skipped (no trigger): camera=%s label=%s "
                            "sub_label=%s | camera_filter=%s label_filter=%s",
                            camera, label, sub_label,
                            list(cam_f) if cam_f else "any",
                            list(lbl_f))
        elif msg.topic in self.birdnet_topics:
            ev = _parse_birdnet_event(msg.payload)
        if ev:
            with self._lock:
                self._events.append(ev)

    def _run_client(self):
        retry_delay = 5
        max_retry_delay = 300
        while True:
            try:
                self._client = mqtt.Client(
                    callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
                    client_id=self.client_id,
                )
                if self.username:
                    self._client.username_pw_set(self.username, self.password)
                self._client.on_connect = self._on_connect
                self._client.on_disconnect = self._on_disconnect
                self._client.on_message = self._on_message
                self._client.will_set("birdlense/status", "offline", qos=1, retain=True)
                self._client.connect(self.broker, self.port, 60)
                self._client.subscribe(self.frigate_topic, qos=1)
                for t in self.birdnet_topics:
                    self._client.subscribe(t, qos=1)
                self._client.publish("birdlense/status", "online", qos=1, retain=True)
                retry_delay = 5
                self._client.loop_forever()
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
            retry_delay = min(retry_delay * 2, max_retry_delay)

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
                ts_str = ev.get("timestamp")
                if not ts_str:
                    continue
                try:
                    ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                except ValueError:
                    continue
                if low <= ts <= high:
                    result.append(ev)
            return result

    def publish_detection(self, species, confidence, source="yolo", start_time=None, end_time=None):
        """Publish detection to birdlense/detections and HA discovery state topics."""
        if not self._client or not self._connected:
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
        try:
            self._client.publish(
                self.publish_topic,
                json.dumps(payload),
                qos=1,
            )
            if self.ha_discovery:
                self._client.publish(HA_TOPIC_LAST_SPECIES, str(species), qos=1, retain=True)
                self._client.publish(HA_TOPIC_LAST_CONFIDENCE, f"{float(confidence):.2f}", qos=1, retain=True)
                self._client.publish(HA_TOPIC_LAST_TIME, ts_iso, qos=1, retain=True)
                self._client.publish(HA_TOPIC_BIRD_DETECTED, "ON", qos=1)
        except Exception as e:
            logger.warning("MQTT publish failed: %s", e)

    def publish_detections(self, detections, start_time, end_time):
        """Publish all detections from a video session."""
        if not self._client or not self._connected:
            return
        for d in detections:
            species = d.get("species") or d.get("name", "unknown")
            conf = d.get("confidence", 0)
            src = d.get("source", "yolo")
            self.publish_detection(species, conf, src, start_time, end_time)

    def is_connected(self):
        return self._connected

    def stop(self):
        self._stopped = True
        if self._client:
            self._client.disconnect()
            self._client.loop_stop()
