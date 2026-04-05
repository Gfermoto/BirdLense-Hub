"""Pytest fixtures for web API tests."""
import os
import sys

import pytest

# Set test DB before any app imports
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
# Не поднимать фоновый sampler метрик в тестах (поток + psutil sleep).
os.environ['DISABLE_SYSTEM_METRICS_SAMPLER'] = '1'
# Prevent startup Telegram/push notification.
# app.py calls create_app() at module level (for gunicorn `app:app`); this flag must be set
# BEFORE any test module imports `app`, otherwise notify_app_startup hangs on the real token.
os.environ['FLASK_TESTING'] = '1'

# Prevent MQTT/ESPHome connection attempts (would hang or fail in CI)
os.environ.pop('MQTT_BROKER', None)
os.environ.pop('ESPHOME_FEEDER_URL', None)
os.environ.pop('OPENWEATHER_API_KEY', None)
os.environ.pop('HA_TOKEN', None)
os.environ.pop('HA_URL', None)

# Add project root to path (app/ on host, or /app in Docker)
_app_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if _app_root not in sys.path:
    sys.path.insert(0, _app_root)
# In Docker, app_config is at /app/app_config; on host, at app/app_config
_parent = os.path.dirname(_app_root)
if _parent not in sys.path and os.path.isdir(os.path.join(_parent, 'app_config')):
    sys.path.insert(0, _parent)


@pytest.fixture
def app():
    """Create Flask app. Run: cd app && pytest web/tests, or in Docker: pytest tests/."""
    from app_config.app_config import app_config
    try:
        from app import create_app
    except ImportError:
        from web.app import create_app
    # Avoid external network calls in tests.
    app_config.set('secrets.openweather_api_key', '')
    app_config.set('weather.ha_token', '')
    app_config.set('weather.ha_url', '')
    app_config.set('homeassistant.token', '')
    app_config.set('homeassistant.url', '')
    app = create_app()
    app.config['TESTING'] = True
    return app


@pytest.fixture
def client(app):
    """Flask test client."""
    return app.test_client()
