"""Tests for UI automation bridge endpoints."""

from __future__ import annotations

class _ImmediateThread:
    def __init__(self, target=None, daemon=None, **kwargs):
        self._target = target

    def start(self):
        if self._target:
            self._target()


def test_fusion_export_route_runs_job_and_exposes_status(client, monkeypatch):
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

    response = client.post('/api/ui/system/fusion/eval', json={'slice_fields': ['species']})
    assert response.status_code == 202

    status = client.get('/api/ui/system/fusion/eval/status')
    assert status.status_code == 200
    body = status.get_json()
    assert body['status'] == 'done'
    assert body['result']['accuracy'] == 0.91


def test_telegram_proxy_refresh_route_runs_job_and_exposes_status(client, monkeypatch):
    from app_config.app_config import app_config
    import routes.ui_system_routes as uis

    app_config.set('general.settings_password', '')
    app_config.set('general.contributor_password', '')
    monkeypatch.setattr(uis.threading, 'Thread', _ImmediateThread)
    monkeypatch.setattr(
        uis,
        'refresh_telegram_proxy_service',
        lambda: {'checked': 3, 'working': 1, 'best_proxy': 'socks5h://1.2.3.4:1080'},
    )

    response = client.post('/api/ui/system/telegram-proxy/refresh')
    assert response.status_code == 202

    status = client.get('/api/ui/system/telegram-proxy/refresh/status')
    assert status.status_code == 200
    body = status.get_json()
    assert body['status'] == 'done'
    assert body['result']['best_proxy'] == 'socks5h://1.2.3.4:1080'
