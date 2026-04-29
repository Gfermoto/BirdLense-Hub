"""Pytest fixtures for web API tests."""

import os
import sys

import pytest

# Не наследовать «прод» и секреты хоста разработчика (иначе 403 и рассинхрон MCP Bearer).
os.environ.pop("BIRDLENSE_ENV", None)
os.environ.pop("BIRDLENSE_STRICT_API_AUTH", None)
os.environ.pop("BIRDLENSE_UI_API_KEY", None)
os.environ.pop("BIRDLENSE_METRICS_TOKEN", None)
os.environ.pop("MCP_TOKEN", None)
if (os.environ.get("FLASK_ENV") or "").strip().lower() in ("production", "prod"):
    os.environ["FLASK_ENV"] = "development"

# Set test DB before any app imports
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
# Не поднимать фоновый sampler метрик в тестах (поток + psutil sleep).
os.environ["DISABLE_SYSTEM_METRICS_SAMPLER"] = "1"
# Prevent startup Telegram/push notification.
# app.py calls create_app() at module level (for gunicorn `app:app`); this flag must be set
# BEFORE any test module imports `app`, otherwise notify_app_startup hangs on the real token.
os.environ["FLASK_TESTING"] = "1"

# Prevent MQTT/ESPHome connection attempts (would hang or fail in CI)
os.environ.pop("MQTT_BROKER", None)
os.environ.pop("ESPHOME_FEEDER_URL", None)
os.environ.pop("OPENWEATHER_API_KEY", None)
os.environ.pop("HA_TOKEN", None)
os.environ.pop("HA_URL", None)

# Add project root to path (app/ on host, or /app in Docker)
_app_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _app_root not in sys.path:
    sys.path.insert(0, _app_root)
# In Docker, app_config is at /app/app_config; on host, at app/app_config
_parent = os.path.dirname(_app_root)
if _parent not in sys.path and os.path.isdir(os.path.join(_parent, "app_config")):
    sys.path.insert(0, _parent)
# inference.* (binary_paths, ml_lineage_service) — app/processor/src (_app_root is app/web).
_app_home = os.path.dirname(_app_root)
_processor_src = os.path.join(_app_home, "processor", "src")
if os.path.isdir(_processor_src) and _processor_src not in sys.path:
    sys.path.insert(0, _processor_src)


@pytest.fixture
def app():
    """Create Flask app. Run: cd app && pytest web/tests, or in Docker: pytest tests/."""
    from app_config.app_config import app_config

    try:
        from app import create_app
    except ImportError:
        from web.app import create_app
    # Avoid external network calls in tests.
    app_config.set("secrets.openweather_api_key", "")
    app_config.set("weather.ha_token", "")
    app_config.set("weather.ha_url", "")
    app_config.set("homeassistant.token", "")
    app_config.set("homeassistant.url", "")
    app_config.set("notifications.telegram_proxy_type", "")
    app_config.set("notifications.telegram_proxy_url", "")
    app = create_app()
    app.config["TESTING"] = True
    return app


@pytest.fixture
def client(app):
    """Flask test client."""
    return app.test_client()


@pytest.fixture(autouse=True)
def _reset_global_test_state():
    """Autouse fixture to reset global in-memory caches and module-level status between tests.

    This avoids test-ordering flakiness caused by shared process-level state
    (in-memory cache, module-level status dicts, MQTT clients).
    """
    # Reset in-memory cache store
    try:
        from services import cache as _cache

        with _cache._lock:
            _cache._store.clear()
    except Exception:
        pass
    try:
        from observer_time import _observer_timezone_name_cached

        _observer_timezone_name_cached.cache_clear()
    except Exception:
        pass
    # Reset UI long-job status (shared module, not ui_system_routes)
    try:
        import routes.ui_system_jobs_state as _js

        idle = {"status": "idle", "result": None, "error": None, "progress": None}
        _js._regenerate_status = dict(idle)
        _js._regenerate_tracks_status = dict(idle)
        _js._species_metadata_status = dict(idle)
        _js._catalog_cards_status = dict(idle)
        _js._fusion_export_status = dict(idle)
        _js._fusion_eval_status = dict(idle)
        _js._telegram_proxy_refresh_status = dict(idle)
    except Exception:
        pass
    # Reset feed service mqtt client
    try:
        import services.feed_service as _fs

        _fs._mqtt_client = None
    except Exception:
        pass
    yield
