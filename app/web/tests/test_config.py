"""Config-level tests for environment-driven defaults."""

import importlib


def test_cors_default_origins_from_env(monkeypatch):
    monkeypatch.setenv("CORS_DEFAULT_ORIGINS", "https://demo.example,http://demo.local")
    import config as config_module

    importlib.reload(config_module)
    assert config_module.Config.CORS_DEFAULT_ORIGINS == "https://demo.example,http://demo.local"


def test_cors_local_dev_origins_default(monkeypatch):
    monkeypatch.delenv("CORS_LOCAL_DEV_ORIGINS", raising=False)
    import config as config_module

    importlib.reload(config_module)
    assert "http://localhost:5173" in config_module.Config.CORS_LOCAL_DEV_ORIGINS
    assert "8085" in config_module.Config.CORS_LOCAL_DEV_ORIGINS


def test_cors_local_dev_origins_empty_overrides_default(monkeypatch):
    monkeypatch.setenv("CORS_LOCAL_DEV_ORIGINS", "")
    import config as config_module

    importlib.reload(config_module)
    assert config_module.Config.CORS_LOCAL_DEV_ORIGINS == ""


def test_cors_local_dev_origins_disabled_by_default_in_production(monkeypatch):
    monkeypatch.delenv("CORS_LOCAL_DEV_ORIGINS", raising=False)
    monkeypatch.setenv("BIRDLENSE_ENV", "production")
    monkeypatch.delenv("FLASK_ENV", raising=False)
    # В CI Docker .env часто без секрета; web/config.py в production требует FLASK_SECRET_KEY при reload.
    monkeypatch.setenv("FLASK_SECRET_KEY", "pytest-config-reload-secret")
    monkeypatch.setenv("PROCESSOR_SECRET", "pytest-processor-secret")
    monkeypatch.setenv("BIRDLENSE_STRICT_API_AUTH", "1")
    import config as config_module

    importlib.reload(config_module)
    assert config_module.Config.CORS_LOCAL_DEV_ORIGINS == ""


def test_production_requires_processor_secret_and_strict_ui_auth(monkeypatch):
    monkeypatch.setenv("BIRDLENSE_ENV", "production")
    monkeypatch.delenv("FLASK_ENV", raising=False)
    monkeypatch.setenv("FLASK_SECRET_KEY", "pytest-config-reload-secret")
    monkeypatch.delenv("PROCESSOR_SECRET", raising=False)
    monkeypatch.delenv("BIRDLENSE_STRICT_API_AUTH", raising=False)
    import config as config_module
    import pytest

    with pytest.raises(RuntimeError, match="PROCESSOR_SECRET"):
        importlib.reload(config_module)

    monkeypatch.setenv("PROCESSOR_SECRET", "pytest-processor-secret")
    importlib.reload(config_module)
