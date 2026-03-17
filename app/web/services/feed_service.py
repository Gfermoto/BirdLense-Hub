"""Feed control service: MQTT or ESPHome for feeder dispense."""
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

import paho.mqtt.client as mqtt
import requests

from app_config.app_config import app_config

logger = logging.getLogger(__name__)

_FEED_LAST_FILE = 'feed_last_dispense.json'


def _feed_data_path():
    """Path to feed state file in DATA_DIR."""
    data_dir = os.environ.get('DATA_DIR') or os.path.join(
        os.path.dirname(os.path.dirname(__file__)), '..', 'data'
    )
    return Path(data_dir) / _FEED_LAST_FILE


def _save_last_dispense():
    """Save current UTC timestamp when feed was dispensed."""
    try:
        path = _feed_data_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        now = datetime.now(timezone.utc)
        path.write_text(json.dumps({'last_dispense_at': now.isoformat()}), encoding='utf-8')
    except OSError as e:
        logger.warning('Could not save last dispense time: %s', e)


def get_last_dispense():
    """Return last dispense ISO timestamp or None."""
    try:
        path = _feed_data_path()
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding='utf-8'))
        return data.get('last_dispense_at')
    except (OSError, json.JSONDecodeError, KeyError):
        return None

_mqtt_client = None


def _on_feed_disconnect(client, userdata, *args):
    global _mqtt_client
    _mqtt_client = None
    logger.warning('MQTT feed client disconnected')


def _get_mqtt_client():
    global _mqtt_client
    if _mqtt_client is not None and _mqtt_client.is_connected():
        return _mqtt_client
    if _mqtt_client is not None:
        try:
            _mqtt_client.disconnect()
        except Exception:
            pass
        _mqtt_client = None
    broker = os.environ.get('MQTT_BROKER') or app_config.get('mqtt.broker')
    if not broker:
        return None
    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id='birdlense_feed',
    )
    username = os.environ.get('MQTT_USERNAME') or app_config.get('mqtt.username')
    password = os.environ.get('MQTT_PASSWORD') or app_config.get('mqtt.password')
    if username:
        client.username_pw_set(username, password)
    client.on_disconnect = _on_feed_disconnect
    try:
        port = app_config.get('mqtt.port', 1883)
        client.connect(broker, port, 60)
        client.loop_start()
        _mqtt_client = client
        return client
    except Exception as e:
        logger.error('MQTT connect failed: %s', e)
        return None


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
    """Dispense feed via MQTT (Tasmota) or ESPHome. Relay on for duration_seconds."""
    import time
    source = app_config.get('feed.source', 'mqtt')
    if source in (None, '', 'none'):
        return False, 'Подкормка выключена в настройках'
    duration = app_config.get('feed.duration_seconds', 3)
    if source == 'mqtt':
        client = _get_mqtt_client()
        topic = app_config.get('feed.mqtt_topic', 'cmnd/bird_feeder/Power')
        if not client:
            return False, 'MQTT broker not configured'
        try:
            client.publish(topic, 'ON', qos=1)
            time.sleep(duration)
            client.publish(topic, 'OFF', qos=1)
            logger.info('Feed dispensed via MQTT (relay %ds)', duration)
            _save_last_dispense()
            return True, 'Feed dispensed'
        except Exception as e:
            logger.error('MQTT feed failed: %s', e)
            return False, str(e)
    elif source == 'esphome':
        url = os.environ.get('ESPHOME_FEEDER_URL') or app_config.get(
            'feed.esphome_url', 'http://feeder.local'
        )
        entity_id = os.environ.get('ESPHOME_SWITCH_ID') or app_config.get(
            'feed.esphome_switch_id', 'bird_feeder'
        )
        esphome_type = app_config.get('feed.esphome_type', 'switch')
        # ESPHome REST API: /switch/{object_id}/turn_on (object_id from YAML id)
        entity_path = quote(str(entity_id).strip(), safe='')
        try:
            if esphome_type == 'button':
                r = requests.post(
                    f"{url.rstrip('/')}/button/{entity_path}/press", timeout=5
                )
                r.raise_for_status()
                logger.info('Feed dispensed via ESPHome (button press)')
            else:
                r = requests.post(
                    f"{url.rstrip('/')}/switch/{entity_path}/turn_on", timeout=5
                )
                r.raise_for_status()
                time.sleep(duration)
                requests.post(
                    f"{url.rstrip('/')}/switch/{entity_path}/turn_off", timeout=5
                )
                logger.info('Feed dispensed via ESPHome (switch %ds)', duration)
            _save_last_dispense()
            return True, 'Feed dispensed'
        except Exception as e:
            logger.error('ESPHome feed failed: %s', e)
            return False, str(e)
    return False, 'Unknown feed source'
