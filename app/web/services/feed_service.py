"""Feed control service: MQTT or ESPHome for feeder dispense."""
import logging
import os

import paho.mqtt.client as mqtt
import requests

from app_config.app_config import app_config

logger = logging.getLogger(__name__)

_mqtt_client = None


def _get_mqtt_client():
    global _mqtt_client
    if _mqtt_client is not None:
        return _mqtt_client
    broker = os.environ.get('MQTT_BROKER') or app_config.get('mqtt.broker')
    if not broker:
        return None
    _mqtt_client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id='birdlense_feed',
    )
    username = os.environ.get('MQTT_USERNAME') or app_config.get('mqtt.username')
    password = os.environ.get('MQTT_PASSWORD') or app_config.get('mqtt.password')
    if username:
        _mqtt_client.username_pw_set(username, password)
    try:
        port = app_config.get('mqtt.port', 1883)
        _mqtt_client.connect(broker, port, 60)
        _mqtt_client.loop_start()
    except Exception as e:
        logger.error('MQTT connect failed: %s', e)
        return None
    return _mqtt_client


def check_mqtt_connected():
    """Check if MQTT client exists and is connected. Returns 'ok', 'error', or 'not_configured'."""
    broker = os.environ.get('MQTT_BROKER') or app_config.get('mqtt.broker')
    if not broker:
        return 'not_configured'
    client = _get_mqtt_client()
    if not client:
        return 'error'
    try:
        return 'ok' if client.is_connected() else 'error'
    except Exception:
        return 'error'


def check_esphome_reachable():
    """Check if ESPHome feeder URL is reachable. Returns 'ok', 'error', or 'not_configured'."""
    source = app_config.get('feed.source', 'mqtt')
    if source != 'esphome':
        return 'not_configured'
    url = os.environ.get('ESPHOME_FEEDER_URL') or app_config.get(
        'feed.esphome_url', 'http://feeder.local'
    )
    if not url:
        return 'not_configured'
    try:
        r = requests.get(url.rstrip('/'), timeout=3)
        return 'ok' if r.status_code < 500 else 'error'
    except Exception:
        return 'error'


def dispense_feed():
    """Dispense feed via MQTT or ESPHome. Returns (success, message)."""
    source = app_config.get('feed.source', 'mqtt')
    if source == 'mqtt':
        client = _get_mqtt_client()
        topic = app_config.get(
            'feed.mqtt_topic', 'homeassistant/switch/bird_feeder/command'
        )
        if not client:
            return False, 'MQTT broker not configured'
        try:
            client.publish(topic, 'ON', qos=1)
            logger.info('Feed dispensed via MQTT')
            return True, 'Feed dispensed'
        except Exception as e:
            logger.error('MQTT feed failed: %s', e)
            return False, str(e)
    elif source == 'esphome':
        url = os.environ.get('ESPHOME_FEEDER_URL') or app_config.get(
            'feed.esphome_url', 'http://feeder.local'
        )
        switch_id = os.environ.get('ESPHOME_SWITCH_ID') or app_config.get(
            'feed.esphome_switch_id', 'bird_feeder'
        )
        try:
            r = requests.post(
                f"{url.rstrip('/')}/switch/{switch_id}/turn_on", timeout=5
            )
            r.raise_for_status()
            logger.info('Feed dispensed via ESPHome')
            return True, 'Feed dispensed'
        except Exception as e:
            logger.error('ESPHome feed failed: %s', e)
            return False, str(e)
    return False, 'Unknown feed source'
