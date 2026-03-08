"""
Feed controller: MQTT or ESPHome for feeder control.
"""
import logging
import os

import requests

logger = logging.getLogger(__name__)


class FeedController:
    """Control bird feeder via MQTT or ESPHome."""

    def __init__(self, source: str, mqtt_client=None, mqtt_topic: str = "", esphome_url: str = "", esphome_switch_id: str = ""):
        self.source = source or "mqtt"
        self.mqtt_client = mqtt_client
        self.mqtt_topic = mqtt_topic or "homeassistant/switch/bird_feeder/command"
        self.esphome_url = esphome_url or os.environ.get("ESPHOME_FEEDER_URL", "http://feeder.local")
        self.esphome_switch_id = esphome_switch_id or os.environ.get("ESPHOME_SWITCH_ID", "bird_feeder")

    def feed_on(self):
        """Turn feeder on."""
        if self.source == "mqtt" and self.mqtt_client:
            try:
                self.mqtt_client.publish(self.mqtt_topic, "ON", qos=1)
                logger.info("Feed ON via MQTT")
                return True
            except Exception as e:
                logger.error(f"MQTT feed_on failed: {e}")
                return False
        elif self.source == "esphome":
            return self._esphome_call("turn_on")
        return False

    def feed_off(self):
        """Turn feeder off."""
        if self.source == "mqtt" and self.mqtt_client:
            try:
                self.mqtt_client.publish(self.mqtt_topic, "OFF", qos=1)
                logger.info("Feed OFF via MQTT")
                return True
            except Exception as e:
                logger.error(f"MQTT feed_off failed: {e}")
                return False
        elif self.source == "esphome":
            return self._esphome_call("turn_off")
        return False

    def feed_pulse(self, seconds=3):
        """Pulse feeder on for N seconds (ESPHome). MQTT: just ON."""
        if self.source == "mqtt":
            self.feed_on()
            return True
        return self.feed_on()

    def _esphome_call(self, action: str):
        url = f"{self.esphome_url.rstrip('/')}/switch/{self.esphome_switch_id}/{action}"
        try:
            r = requests.post(url, timeout=5)
            r.raise_for_status()
            logger.info(f"Feed {action} via ESPHome")
            return True
        except Exception as e:
            logger.error(f"ESPHome feed {action} failed: {e}")
            return False
