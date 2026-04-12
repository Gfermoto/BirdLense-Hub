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
