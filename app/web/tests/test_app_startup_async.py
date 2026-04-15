"""Tests for non-blocking startup notification scheduling."""

import importlib


def test_create_app_schedules_startup_notify_in_background(monkeypatch):
    """`create_app()` should not block readiness on Telegram delivery."""
    app_mod = importlib.import_module('app')

    monkeypatch.setattr(app_mod, 'init_extensions', lambda app: None)
    monkeypatch.setattr(app_mod, 'init_request_logging', lambda app: None)
    monkeypatch.setattr(app_mod, 'register_error_handlers', lambda app: None)
    monkeypatch.setattr(app_mod, 'register_all_routes', lambda app: None)
    monkeypatch.setattr(
        app_mod,
        'apply_schema_migrations_and_seed',
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(app_mod, 'bootstrap_species_registry', lambda: None)
    monkeypatch.setattr(app_mod, 'bootstrap_legacy_import_cleanup', lambda: None)
    monkeypatch.setattr(
        app_mod,
        'bootstrap_species_metadata_repair',
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        app_mod,
        'bootstrap_species_metadata_enrich',
        lambda *_args, **_kwargs: None,
    )

    started = {}

    class _FakeThread:
        def __init__(self, *, target=None, args=(), daemon=None, name=None):
            started['target'] = target
            started['args'] = args
            started['daemon'] = daemon
            started['name'] = name

        def start(self):
            started['started'] = True

    monkeypatch.setattr(app_mod.threading, 'Thread', _FakeThread)

    app = app_mod.create_app()

    assert app is not None
    assert started['target'] is app_mod.notify_app_startup
    assert started['args'] == (app,)
    assert started['daemon'] is True
    assert started['name'] == 'birdlense-startup-notify'
    assert started['started'] is True
