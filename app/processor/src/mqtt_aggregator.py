"""
MQTT event aggregator: subscribes to Frigate and BirdNET, stores events for merging,
publishes to birdlense/detections for HA.
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


def _parse_frigate_event(payload):
    """Parse Frigate event: before/after, type (new/update/end). Uses after for final state."""
    try:
        data = json.loads(payload.decode())
    except (json.JSONDecodeError, UnicodeDecodeError):
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
        "species": sub_label or label or "unknown",
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
    ):
        """on_frigate_motion: (camera_filter, label_filter, callback). frigate_label_exclude: labels to ignore (e.g. cat, dog)."""
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
        self._on_frigate_motion = on_frigate_motion  # (camera_filter, label_filter, callback)
        self._frigate_label_exclude = set(frigate_label_exclude or [])

    def _on_connect(self, client, userdata, flags, reason_code, properties=None):
        if reason_code == 0:
            self._connected = True
            logger.info("MQTT aggregator connected")
        else:
            self._connected = False
            logger.warning(f"MQTT aggregator connect failed: {reason_code}")

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
        self._client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id="birdlense_aggregator",
        )
        if self.username:
            self._client.username_pw_set(self.username, self.password)
        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._client.on_message = self._on_message
        self._client.will_set("birdlense/status", "offline", qos=1, retain=True)
        try:
            self._client.connect(self.broker, self.port, 60)
            self._client.subscribe(self.frigate_topic)
            for t in self.birdnet_topics:
                self._client.subscribe(t)
            self._client.publish("birdlense/status", "online", qos=1, retain=True)
            self._client.loop_forever()
        except Exception as e:
            logger.error(f"MQTT aggregator error: {e}")
        finally:
            self._connected = False

    def start(self):
        if not self.broker:
            logger.warning("MQTT broker not configured, aggregator disabled")
            return
        self._thread = threading.Thread(target=self._run_client, daemon=True)
        self._thread.start()
        time.sleep(0.5)

    def get_events_in_window(self, start_time, end_time, window_seconds=5):
        """Return MQTT events within [start - window, end + window]."""
        from datetime import timedelta
        low = start_time - timedelta(seconds=window_seconds)
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
        """Publish detection to birdlense/detections for HA automations."""
        if not self._client or not self._connected:
            return
        payload = {
            "species": species,
            "confidence": confidence,
            "source": source,
            "timestamp": (start_time or datetime.now(timezone.utc)).isoformat(),
        }
        if end_time:
            payload["end_time"] = end_time.isoformat()
        try:
            self._client.publish(
                self.publish_topic,
                json.dumps(payload),
                qos=1,
            )
        except Exception as e:
            logger.warning(f"MQTT publish failed: {e}")

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
        if self._client:
            self._client.disconnect()
            self._client.loop_stop()
