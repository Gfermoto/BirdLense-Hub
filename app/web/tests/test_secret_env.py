"""Secret overlays from BIRDLENSE_* env (#278)."""

from app_config.secret_env import apply_secret_env_overrides


def test_apply_secret_env_overrides_sets_nested_keys(monkeypatch):
    merged = {
        "general": {"settings_password": "from-yaml"},
        "mqtt": {"password": "old"},
    }
    monkeypatch.setenv("BIRDLENSE_SETTINGS_PASSWORD", "  from-env  ")
    monkeypatch.setenv("BIRDLENSE_MQTT_PASSWORD", "mqtt-secret")
    apply_secret_env_overrides(merged)
    assert merged["general"]["settings_password"] == "from-env"
    assert merged["mqtt"]["password"] == "mqtt-secret"


def test_apply_secret_env_skips_empty_and_unset(monkeypatch):
    merged = {"general": {"settings_password": "keep"}}
    monkeypatch.delenv("BIRDLENSE_SETTINGS_PASSWORD", raising=False)
    monkeypatch.setenv("BIRDLENSE_MQTT_PASSWORD", "   ")
    apply_secret_env_overrides(merged)
    assert merged["general"]["settings_password"] == "keep"
    assert "mqtt" not in merged
