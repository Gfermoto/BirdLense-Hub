"""Тесты общих runtime env helper-ов."""

from services.runtime_env import env_flag_enabled, is_production_runtime


def test_env_flag_enabled_truthy_variants():
    assert env_flag_enabled("1") is True
    assert env_flag_enabled(" true ") is True
    assert env_flag_enabled("ON") is True


def test_env_flag_enabled_falsey_variants():
    assert env_flag_enabled(None) is False
    assert env_flag_enabled("") is False
    assert env_flag_enabled("0") is False
    assert env_flag_enabled("nope") is False


def test_is_production_runtime_accepts_prod_alias(monkeypatch):
    monkeypatch.delenv("FLASK_ENV", raising=False)
    monkeypatch.setenv("BIRDLENSE_ENV", "PROD")
    assert is_production_runtime() is True
