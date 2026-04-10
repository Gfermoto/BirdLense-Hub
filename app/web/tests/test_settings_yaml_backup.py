"""Экспорт/импорт user_config YAML (#271)."""

import io

import yaml


def _open_admin_yaml(monkeypatch):
    from app_config.app_config import app_config

    monkeypatch.delenv('BIRDLENSE_ENV', raising=False)
    monkeypatch.delenv('FLASK_ENV', raising=False)
    gen = app_config.config.setdefault('general', {})
    monkeypatch.setitem(gen, 'settings_password', '')
    monkeypatch.setitem(gen, 'contributor_password', '')


def test_yaml_export_safe_masks_secret(client, monkeypatch, tmp_path):
    from app_config.app_config import app_config

    _open_admin_yaml(monkeypatch)
    user_file = tmp_path / 'user_config.yaml'
    user_file.write_text(
        yaml.safe_dump(
            {'secrets': {'openweather_api_key': 'SECRET123'}, 'general': {'app_name': 'Hub'}},
            allow_unicode=True,
        ),
        encoding='utf-8',
    )
    monkeypatch.setattr(app_config, 'user_config_file', str(user_file))

    r = client.get('/api/ui/settings/yaml-export?mode=safe')
    assert r.status_code == 200
    assert 'attachment' in r.headers.get('Content-Disposition', '')
    data = yaml.safe_load(r.get_data(as_text=True))
    assert data['general']['app_name'] == 'Hub'
    assert data['secrets']['openweather_api_key'] == '***'


def test_yaml_export_full_requires_ack(client, monkeypatch, tmp_path):
    from app_config.app_config import app_config

    _open_admin_yaml(monkeypatch)
    user_file = tmp_path / 'user_config.yaml'
    user_file.write_text('x: 1\n', encoding='utf-8')
    monkeypatch.setattr(app_config, 'user_config_file', str(user_file))

    assert client.get('/api/ui/settings/yaml-export?mode=full').status_code == 400
    r = client.get('/api/ui/settings/yaml-export?mode=full&ack=full')
    assert r.status_code == 200
    assert 'x: 1' in r.get_data(as_text=True)


def test_yaml_import_merge_and_validate(client, monkeypatch, tmp_path):
    from app_config.app_config import app_config

    _open_admin_yaml(monkeypatch)
    user_file = tmp_path / 'user_config.yaml'
    user_file.write_text(
        yaml.safe_dump({'general': {'app_name': 'Old'}}),
        encoding='utf-8',
    )
    monkeypatch.setattr(app_config, 'user_config_file', str(user_file))
    app_config.reload()

    incoming = yaml.safe_dump({'general': {'app_name': 'New'}})
    r = client.post(
        '/api/ui/settings/yaml-import',
        data={'file': (io.BytesIO(incoming.encode('utf-8')), 'cfg.yaml')},
        content_type='multipart/form-data',
    )
    assert r.status_code == 200, r.get_json()
    app_config.reload()
    saved = yaml.safe_load(user_file.read_text(encoding='utf-8'))
    assert saved['general']['app_name'] == 'New'


def test_yaml_import_rejects_bad_root(client, monkeypatch):
    _open_admin_yaml(monkeypatch)
    incoming = yaml.safe_dump([1, 2, 3])
    r = client.post(
        '/api/ui/settings/yaml-import',
        data={'file': (io.BytesIO(incoming.encode('utf-8')), 'bad.yaml')},
        content_type='multipart/form-data',
    )
    assert r.status_code == 400
