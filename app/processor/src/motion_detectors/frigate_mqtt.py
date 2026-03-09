"""
Frigate MQTT motion detector. Subscribes to frigate/events, triggers on bird/motion.
FrigateMotionFromAggregator — один MQTT (через aggregator), без второго подключения.
"""
import json
import logging
import os
import threading
import time

import paho.mqtt.client as mqtt

logger = logging.getLogger(__name__)


class FrigateMotionFromAggregator:
    """Motion через MQTT aggregator — одно подключение вместо двух (Not authorized)."""

    def __init__(self, aggregator, camera_filter=None, label_filter=None):
        self._aggregator = aggregator
        self._camera_filter = set(camera_filter or [])
        self._label_filter = set(label_filter or ["bird", "Bird"])
        self._event = threading.Event()
        self._last_camera = None

    def _on_motion(self, camera, label):
        self._last_camera = camera
        logger.info(f"Frigate motion: camera={camera}, label={label}")
        self._event.set()

    def get_on_frigate_motion_tuple(self):
        return (self._camera_filter, self._label_filter, self._on_motion)

    @property
    def _connected(self):
        return self._aggregator.is_connected()

    def detect(self):
        if not self._connected:
            time.sleep(1)
            return False
        self._event.clear()
        self._last_camera = None
        self._event.wait(timeout=300)
        return self._event.is_set()

    def get_triggered_camera(self):
        return self._last_camera

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
    ):
        self.broker = broker
        self.port = port
        self.topic = topic
        self.camera_filter = set(camera_filter or [])
        self.label_filter = set(label_filter or ["bird", "Bird"])
        self.username = username or os.environ.get("MQTT_USERNAME")
        self.password = password or os.environ.get("MQTT_PASSWORD")
        self._event = threading.Event()
        self._last_camera = None
        self._client = None
        self._thread = None
        self._connected = False

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
        if self.camera_filter and camera not in self.camera_filter:
            return
        labels = {label, sub_label} if sub_label else {label}
        if not (labels & self.label_filter):
            return
        self._last_camera = camera
        logger.info(f"Frigate event: camera={camera}, label={label}, sub_label={sub_label}")
        self._event.set()

    def _run_client(self):
        self._client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id="birdlense_frigate",
        )
        if self.username:
            self._client.username_pw_set(self.username, self.password)
        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._client.on_message = self._on_message
        self._client.will_set("birdlense/status", "offline", qos=1, retain=True)
        try:
            self._client.connect(self.broker, self.port, 60)
            self._client.subscribe(self.topic)
            self._client.publish("birdlense/status", "online", qos=1, retain=True)
            self._client.loop_forever()
        except Exception as e:
            logger.error(f"Frigate MQTT error: {e}")
        finally:
            self._event.set()

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
        self._event.clear()
        self._last_camera = None
        self._event.wait(timeout=300)
        return self._event.is_set()

    def get_triggered_camera(self):
        """Return camera id from last Frigate event, or None."""
        return self._last_camera

    def stop(self):
        if self._client:
            self._client.disconnect()
            self._client.loop_stop()
