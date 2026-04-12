"""
MQTT binary sensor motion detector. Subscribes to a topic (e.g. Tasmota PIR, Shelly),
triggers when payload is ON/1/true.
"""

import logging
import os
import threading
import time

import paho.mqtt.client as mqtt

logger = logging.getLogger(__name__)

ON_VALUES = {"ON", "1", "true", "True", "yes"}


class MQTTBinaryMotionDetector:
    """Motion detection via MQTT binary sensor topic. ON = motion."""

    def __init__(
        self,
        broker: str,
        topic: str,
        port: int = 1883,
        username=None,
        password=None,
    ):
        self.broker = broker
        self.port = port
        self.topic = topic
        self.username = username or os.environ.get("MQTT_USERNAME")
        self.password = password or os.environ.get("MQTT_PASSWORD")
        self._event = threading.Event()
        self._client = None
        self._thread = None
        self._connected = False

    def _on_connect(self, client, userdata, flags, reason_code, properties=None):
        if reason_code == 0:
            self._connected = True
            logger.info("MQTT binary sensor connected")
        else:
            self._connected = False
            logger.warning(f"MQTT binary connect failed: {reason_code}")

    def _on_disconnect(self, client, userdata, reason_code, properties=None):
        self._connected = False
        logger.warning(f"MQTT binary disconnected: {reason_code}")

    def _on_message(self, client, userdata, msg):
        try:
            payload = msg.payload.decode().strip().upper()
        except (UnicodeDecodeError, AttributeError):
            return
        if payload in ("ON", "1", "TRUE", "YES"):
            logger.info("MQTT binary sensor: motion ON")
            self._event.set()

    def _run_client(self):
        self._client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id="birdlense_motion_binary",
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
            logger.error(f"MQTT binary sensor error: {e}")
        finally:
            self._event.set()

    def start(self):
        if not self.broker or not self.topic:
            raise ValueError("MQTT broker and topic required")
        self._thread = threading.Thread(target=self._run_client, daemon=True)
        self._thread.start()
        time.sleep(1)

    def check_pending(self):
        """Non-blocking: True if motion (ON) received (for OR with Frigate)."""
        if self._event.is_set():
            self._event.clear()
            return True
        return False

    def detect(self):
        """Block until motion (ON) received. Returns True."""
        if not self._client or not self._connected:
            time.sleep(1)
            return False
        self._event.clear()
        self._event.wait(timeout=300)
        return self._event.is_set()
