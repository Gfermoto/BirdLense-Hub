"""Home Assistant URL/token resolution and settings API shaping."""


def test_get_homeassistant_prefers_new_keys_over_legacy(app):
    from app_config.app_config import app_config
    from services.homeassistant_config import get_homeassistant_url, get_homeassistant_token

    with app.app_context():
        try:
            app_config.set("homeassistant.url", "http://new.example")
            app_config.set("homeassistant.token", "tok-new")
            app_config.set("weather.ha_url", "http://old.example")
            app_config.set("weather.ha_token", "tok-old")
            assert get_homeassistant_url() == "http://new.example"
            assert get_homeassistant_token() == "tok-new"
        finally:
            app_config.set("homeassistant.url", "")
            app_config.set("homeassistant.token", "")
            app_config.set("weather.ha_url", "")
            app_config.set("weather.ha_token", "")


def test_get_homeassistant_falls_back_to_legacy(app):
    from app_config.app_config import app_config
    from services.homeassistant_config import get_homeassistant_url, get_homeassistant_token

    with app.app_context():
        try:
            app_config.set("homeassistant.url", "")
            app_config.set("homeassistant.token", "")
            app_config.set("weather.ha_url", "http://legacy.example")
            app_config.set("weather.ha_token", "tok-legacy")
            assert get_homeassistant_url() == "http://legacy.example"
            assert get_homeassistant_token() == "tok-legacy"
        finally:
            app_config.set("weather.ha_url", "")
            app_config.set("weather.ha_token", "")


def test_get_homeassistant_env_overrides_config(app, monkeypatch):
    from app_config.app_config import app_config
    from services.homeassistant_config import get_homeassistant_url, get_homeassistant_token

    monkeypatch.setenv("HA_URL", "http://from-env")
    monkeypatch.setenv("HA_TOKEN", "env-secret")
    with app.app_context():
        try:
            app_config.set("homeassistant.url", "http://cfg")
            app_config.set("homeassistant.token", "cfg-secret")
            assert get_homeassistant_url() == "http://from-env"
            assert get_homeassistant_token() == "env-secret"
        finally:
            app_config.set("homeassistant.url", "")
            app_config.set("homeassistant.token", "")


def test_prepare_settings_for_api_hides_legacy_weather_ha_keys():
    from app_config.app_config import AppConfig

    cfg = {
        "weather": {
            "source": "homeassistant",
            "ha_url": "http://h.test",
            "ha_token": "secret",
            "ha_entity_id": "weather.home",
        },
        "homeassistant": {"url": "", "token": ""},
    }
    out = AppConfig.prepare_settings_for_api(cfg)
    assert out["homeassistant"]["url"] == "http://h.test"
    assert out["homeassistant"]["token"] == "***"
    assert "ha_url" not in out["weather"]
    assert "ha_token" not in out["weather"]
    assert out["weather"]["ha_entity_id"] == "weather.home"
