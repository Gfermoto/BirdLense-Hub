"""Tests for UI automation bridge endpoints."""

from __future__ import annotations


class _ImmediateThread:
    def __init__(self, target=None, daemon=None, **kwargs):
        self._target = target

    def start(self):
        if self._target:
            self._target()


def test_repo_root_contains_fusion_export_script():
    """Repository root should expose the bundled fusion export script."""
    import routes.ui_system_routes as uis

    script = uis._repo_root() / 'scripts' / 'export_fusion_training_data.py'
    assert script.exists()


def test_repo_root_finds_script_in_container_layout(tmp_path, monkeypatch):
    """Repo root lookup should walk upward until it finds the shipped scripts dir."""
    import routes.ui_system_routes as uis

    fake_module = tmp_path / 'app' / 'web' / 'routes' / 'ui_system_routes.py'
    fake_script = tmp_path / 'app' / 'scripts' / 'export_fusion_training_data.py'
    fake_script.parent.mkdir(parents=True, exist_ok=True)
    fake_script.write_text('#!/usr/bin/env python3\n', encoding='utf-8')
    fake_module.parent.mkdir(parents=True, exist_ok=True)
    fake_module.write_text('', encoding='utf-8')

    monkeypatch.setattr(uis, '__file__', str(fake_module))

    assert uis._repo_root() == tmp_path / 'app'


def test_repo_root_falls_back_to_cwd(tmp_path, monkeypatch):
    """Repo root lookup should also work when the source file path is opaque."""
    import routes.ui_system_routes as uis

    fake_module = tmp_path / 'site-packages' / 'routes' / 'ui_system_routes.py'
    repo_root = tmp_path / 'repo'
    fake_script = repo_root / 'scripts' / 'export_fusion_training_data.py'
    fake_script.parent.mkdir(parents=True, exist_ok=True)
    fake_script.write_text('#!/usr/bin/env python3\n', encoding='utf-8')
    fake_module.parent.mkdir(parents=True, exist_ok=True)
    fake_module.write_text('', encoding='utf-8')

    monkeypatch.setattr(uis, '__file__', str(fake_module))
    monkeypatch.setattr(uis.Path, 'cwd', staticmethod(lambda: repo_root))

    assert uis._repo_root() == repo_root


def test_fusion_export_route_runs_job_and_exposes_status(client, monkeypatch):
    """Fusion export should start and expose a finished status."""
    from app_config.app_config import app_config
    import routes.ui_system_routes as uis

    app_config.set('general.settings_password', '')
    app_config.set('general.contributor_password', '')
    monkeypatch.setattr(uis.threading, 'Thread', _ImmediateThread)
    monkeypatch.setattr(
        uis,
        '_run_fusion_export_job',
        lambda: {'output_path': '/tmp/fusion.csv', 'rows_written': 12},
    )

    response = client.post('/api/ui/system/fusion/export')
    assert response.status_code == 202

    status = client.get('/api/ui/system/fusion/export/status')
    assert status.status_code == 200
    body = status.get_json()
    assert body['status'] == 'done'
    assert body['result']['rows_written'] == 12


def test_fusion_eval_route_runs_job_and_exposes_status(client, monkeypatch):
    """Fusion eval should start and expose a finished status."""
    from app_config.app_config import app_config
    import routes.ui_system_routes as uis

    app_config.set('general.settings_password', '')
    app_config.set('general.contributor_password', '')
    monkeypatch.setattr(uis.threading, 'Thread', _ImmediateThread)
    monkeypatch.setattr(
        uis,
        '_run_fusion_eval_job',
        lambda **kwargs: {'accuracy': 0.91, 'n': 123},
    )

    response = client.post(
        '/api/ui/system/fusion/eval',
        json={'slice_fields': ['species']},
    )
    assert response.status_code == 202

    status = client.get('/api/ui/system/fusion/eval/status')
    assert status.status_code == 200
    body = status.get_json()
    assert body['status'] == 'done'
    assert body['result']['accuracy'] == 0.91


def test_telegram_proxy_refresh_route_runs_job_and_exposes_status(client, monkeypatch):
    """Telegram proxy refresh should start and expose a finished status."""
    from app_config.app_config import app_config
    import routes.ui_system_routes as uis

    app_config.set('general.settings_password', '')
    app_config.set('general.contributor_password', '')
    monkeypatch.setattr(uis.threading, 'Thread', _ImmediateThread)
    monkeypatch.setattr(
        uis,
        'refresh_telegram_proxy_service',
        lambda: {
            'checked': 3,
            'working': 1,
            'best_proxy': 'socks5h://1.2.3.4:1080',
        },
    )

    response = client.post('/api/ui/system/telegram-proxy/refresh')
    assert response.status_code == 202

    status = client.get('/api/ui/system/telegram-proxy/refresh/status')
    assert status.status_code == 200
    body = status.get_json()
    assert body['status'] == 'done'
    assert body['result']['best_proxy'] == 'socks5h://1.2.3.4:1080'
