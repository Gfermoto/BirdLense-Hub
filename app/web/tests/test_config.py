"""Config-level tests for environment-driven defaults."""
import importlib


def test_cors_default_origins_from_env(monkeypatch):
    monkeypatch.setenv('CORS_DEFAULT_ORIGINS', 'https://demo.example,http://demo.local')
    import config as config_module
    importlib.reload(config_module)
    assert (
        config_module.Config.CORS_DEFAULT_ORIGINS
        == 'https://demo.example,http://demo.local'
    )
