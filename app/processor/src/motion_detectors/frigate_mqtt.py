"""
Frigate MQTT motion detector. Subscribes to frigate/events, triggers on bird/motion.
FrigateMotionFromAggregator — один MQTT (через aggregator), без второго подключения.
"""

import json
import logging
import os
import threading
import time
from collections import deque
from datetime import datetime, timezone

import paho.mqtt.client as mqtt
from processor_runtime_stats import inc_counter

logger = logging.getLogger(__name__)


class FrigateMotionFromAggregator:
    """Motion через MQTT aggregator — одно подключение вместо двух (Not authorized)."""

    def __init__(self, aggregator, camera_filter=None, label_filter=None):
        self._aggregator = aggregator
        self._camera_filter = set(camera_filter or [])
        self._label_filter = set(label_filter or ["bird", "Bird"])
        self._event = threading.Event()
        self._lock = threading.Lock()
        self._pending_events = deque(maxlen=256)
        self._last_camera = None
        self._last_confidence = 0.0
        self._last_event_ts = 0.0
        self._last_event_monotonic = 0.0
        self._last_event_payload = None
        self._active_event_payload = None

    def _on_motion(self, camera, label, confidence=0.0, event=None):
        self._last_camera = camera
        try:
            self._last_confidence = float(confidence or 0.0)
        except (TypeError, ValueError):
            self._last_confidence = 0.0
        self._last_event_ts = time.time()
        self._last_event_monotonic = time.monotonic()
        payload = event if isinstance(event, dict) else {}
        self._last_event_payload = {
            "source": "frigate",
            "camera": camera,
            "species": str(payload.get("species") or label or "bird"),
            "label": str(payload.get("label") or label or "bird"),
            "sub_label": str(payload.get("sub_label") or ""),
            "confidence": self._last_confidence,
            "timestamp": str(payload.get("timestamp") or datetime.now(timezone.utc).isoformat()),
            "_frigate_has_geometry": bool(payload.get("_frigate_has_geometry", True)),
        }
        with self._lock:
            # Coalesce MQTT bursts: one pending trigger per camera (latest wins).
            kept = deque(
                (e for e in self._pending_events if str(e.get("camera") or "") != str(camera)),
                maxlen=self._pending_events.maxlen,
            )
            if len(kept) >= kept.maxlen:
                kept.popleft()
                inc_counter("motion_trigger_queue_drop_total")
            kept.append(dict(self._last_event_payload))
            self._pending_events = kept
        logger.info(
            "Frigate motion: camera=%s, label=%s, confidence=%.3f",
            camera,
            label,
            self._last_confidence,
        )
        self._event.set()

    def get_on_frigate_motion_tuple(self):
        return (self._camera_filter, self._label_filter, self._on_motion)

    def check_pending(self):
        """Non-blocking: True if motion event is pending (for OR with other detectors)."""
        with self._lock:
            if self._pending_events:
                self._active_event_payload = self._pending_events.popleft()
                if not self._pending_events:
                    self._event.clear()
                self._last_camera = self._active_event_payload.get("camera")
                try:
                    self._last_confidence = float(self._active_event_payload.get("confidence") or 0.0)
                except (TypeError, ValueError):
                    self._last_confidence = 0.0
                self._last_event_monotonic = time.monotonic()
                self._last_event_ts = time.time()
                return True
        if self._event.is_set():
            self._event.clear()
        return False

    def mark_pending(self):
        """Re-arm the pending motion flag when caller defers recording."""
        payload = self._active_event_payload or self._last_event_payload
        if isinstance(payload, dict) and payload:
            with self._lock:
                if len(self._pending_events) >= self._pending_events.maxlen:
                    self._pending_events.popleft()
                    inc_counter("motion_trigger_queue_drop_total")
                self._pending_events.append(dict(payload))
            self._event.set()

    @property
    def _connected(self):
        return self._aggregator.is_mqtt_live()

    def detect(self):
        if not self._connected:
            time.sleep(1)
            return False
        if self.check_pending():
            logger.info(f"Frigate motion (pending): camera={self._last_camera}")
            return True
        self._event.clear()
        self._event.wait(timeout=300)
        return self.check_pending()

    def get_triggered_camera(self):
        return self._last_camera

    def get_last_frigate_event(self):
        if isinstance(self._last_event_payload, dict):
            return dict(self._last_event_payload)
        return None

    def has_recent_activity(self, camera=None, max_age_seconds=0, min_confidence=0.0):
        try:
            max_age = float(max_age_seconds or 0.0)
        except (TypeError, ValueError):
            max_age = 0.0
        if max_age <= 0 or self._last_event_monotonic <= 0:
            return False
        if time.monotonic() - self._last_event_monotonic > max_age:
            return False
        if camera and self._last_camera and str(camera) != str(self._last_camera):
            return False
        try:
            min_conf = float(min_confidence or 0.0)
        except (TypeError, ValueError):
            min_conf = 0.0
        return float(self._last_confidence or 0.0) >= min_conf

    def stop(self):
        pass


class FrigateMQTTMotionDetector:
    """
    Motion detection via Frigate MQTT events.
    Blocks in detect() until a relevant event is received.
    """

    def __init__(
        self,
        broker: str,
        port: int = 1883,
        topic: str = "frigate/events",
        camera_filter=None,
        label_filter=None,
        username=None,
        password=None,
        reconnect_min_delay: int = 5,
        reconnect_max_delay: int = 300,
    ):
        self.broker = broker
        self.port = port
        self.topic = topic
        self.camera_filter = set(camera_filter or [])
        self.label_filter = set(label_filter or ["bird", "Bird"])
        self.username = username or os.environ.get("MQTT_USERNAME")
        self.password = password or os.environ.get("MQTT_PASSWORD")
        self._event = threading.Event()
        self._lock = threading.Lock()
        self._pending_events = deque(maxlen=256)
        self._last_camera = None
        self._last_confidence = 0.0
        self._last_event_ts = 0.0
        self._last_event_monotonic = 0.0
        self._last_event_payload = None
        self._active_event_payload = None
        self._client = None
        self._thread = None
        self._connected = False
        self._stopped = False
        self.reconnect_min_delay = max(1, int(reconnect_min_delay))
        self.reconnect_max_delay = max(self.reconnect_min_delay, int(reconnect_max_delay))

    def _on_connect(self, client, userdata, flags, reason_code, properties=None):
        if reason_code == 0:
            self._connected = True
            logger.info("Frigate MQTT connected")
        else:
            self._connected = False
            logger.warning(f"Frigate MQTT connect failed: {reason_code}")

    def _on_disconnect(self, client, userdata, disconnect_flags, reason_code, properties=None):
        self._connected = False
        logger.warning(f"Frigate MQTT disconnected: {reason_code}")

    def _on_message(self, client, userdata, msg):
        try:
            data = json.loads(msg.payload.decode())
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            logger.debug(f"Invalid MQTT payload: {e}")
            return
        after = data.get("after") or data
        camera = after.get("camera", "")
        label = after.get("label", "")
        sub_label_raw = after.get("sub_label")
        sub_label = ""
        if isinstance(sub_label_raw, str):
            sub_label = sub_label_raw
        elif isinstance(sub_label_raw, (list, tuple)) and sub_label_raw:
            sub_label = str(sub_label_raw[0]) if sub_label_raw else ""
        score = after.get("top_score") or after.get("score") or 0.0
        try:
            score = float(score)
        except (TypeError, ValueError):
            score = 0.0
        if self.camera_filter and camera not in self.camera_filter:
            return
        labels = {label, sub_label} if sub_label else {label}
        if not (labels & self.label_filter):
            return
        self._last_camera = camera
        self._last_confidence = score
        self._last_event_ts = time.time()
        self._last_event_monotonic = time.monotonic()
        has_geometry = bool(
            after.get("box")
            or after.get("region")
            or (isinstance(after.get("snapshot"), dict) and (after.get("snapshot") or {}).get("box"))
            or (isinstance(after.get("snapshot"), dict) and (after.get("snapshot") or {}).get("region"))
        )
        self._last_event_payload = {
            "source": "frigate",
            "camera": camera,
            "species": str(sub_label or label or "bird"),
            "label": str(label or sub_label or "bird"),
            "sub_label": str(sub_label or ""),
            "confidence": score,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "_frigate_has_geometry": has_geometry,
        }
        with self._lock:
            kept = deque(
                (e for e in self._pending_events if str(e.get("camera") or "") != str(camera)),
                maxlen=self._pending_events.maxlen,
            )
            if len(kept) >= kept.maxlen:
                kept.popleft()
                inc_counter("motion_trigger_queue_drop_total")
            kept.append(dict(self._last_event_payload))
            self._pending_events = kept
        logger.info(
            "Frigate event: camera=%s, label=%s, sub_label=%s, confidence=%.3f",
            camera,
            label,
            sub_label,
            self._last_confidence,
        )
        self._event.set()

    def _consume_pending_event(self) -> bool:
        with self._lock:
            if not self._pending_events:
                return False
            self._active_event_payload = self._pending_events.popleft()
            if not self._pending_events:
                self._event.clear()
        self._last_camera = self._active_event_payload.get("camera")
        try:
            self._last_confidence = float(self._active_event_payload.get("confidence") or 0.0)
        except (TypeError, ValueError):
            self._last_confidence = 0.0
        self._last_event_monotonic = time.monotonic()
        self._last_event_ts = time.time()
        return True

    def _run_client(self):
        retry_delay = self.reconnect_min_delay
        while True:
            try:
                self._client = mqtt.Client(
                    callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
                    client_id="birdlense_frigate",
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
                self._client.subscribe(self.topic)
                self._client.publish("birdlense/status", "online", qos=1, retain=True)
                retry_delay = self.reconnect_min_delay
                self._client.loop_forever(retry_first_connection=True)
            except Exception as e:
                logger.error("Frigate MQTT error: %s, reconnecting in %ds", e, retry_delay)
            finally:
                self._connected = False
                self._event.set()
                if self._client:
                    try:
                        self._client.disconnect()
                    except Exception:
                        logger.debug("Frigate MQTT disconnect cleanup failed", exc_info=True)
                    self._client = None
            if self._stopped:
                break
            time.sleep(retry_delay)
            retry_delay = min(retry_delay * 2, self.reconnect_max_delay)

    def start(self):
        if not self.broker:
            raise ValueError("MQTT broker not configured")
        self._thread = threading.Thread(target=self._run_client, daemon=True)
        self._thread.start()
        time.sleep(1)

    def detect(self):
        """Block until a relevant Frigate event is received. Returns True."""
        if not self._client or not self._connected:
            time.sleep(1)
            return False
        if self._consume_pending_event():
            return True
        self._event.clear()
        self._event.wait(timeout=300)
        return self._consume_pending_event()

    def mark_pending(self):
        """Re-arm the pending motion flag when caller defers recording."""
        payload = self._active_event_payload or self._last_event_payload
        if isinstance(payload, dict) and payload:
            with self._lock:
                if len(self._pending_events) >= self._pending_events.maxlen:
                    self._pending_events.popleft()
                    inc_counter("motion_trigger_queue_drop_total")
                self._pending_events.append(dict(payload))
            self._event.set()

    def get_triggered_camera(self):
        """Return camera id from last Frigate event, or None."""
        return self._last_camera

    def get_last_frigate_event(self):
        if isinstance(self._last_event_payload, dict):
            return dict(self._last_event_payload)
        return None

    def has_recent_activity(self, camera=None, max_age_seconds=0, min_confidence=0.0):
        try:
            max_age = float(max_age_seconds or 0.0)
        except (TypeError, ValueError):
            max_age = 0.0
        if max_age <= 0 or self._last_event_monotonic <= 0:
            return False
        if time.monotonic() - self._last_event_monotonic > max_age:
            return False
        if camera and self._last_camera and str(camera) != str(self._last_camera):
            return False
        try:
            min_conf = float(min_confidence or 0.0)
        except (TypeError, ValueError):
            min_conf = 0.0
        return float(self._last_confidence or 0.0) >= min_conf

    def stop(self):
        self._stopped = True
        if self._client:
            self._client.disconnect()
            self._client.loop_stop()
