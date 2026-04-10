"""Миграция устаревших ключей user_config (weather.ha_* → homeassistant.*)."""
import copy

import yaml

from app_config.app_config import migrate_legacy_homeassistant_from_weather


def test_migrate_copies_legacy_ha_into_homeassistant():
    user = {
        'weather': {'ha_url': 'http://ha.test', 'ha_token': 'tok1', 'source': 'homeassistant'},
    }
    assert migrate_legacy_homeassistant_from_weather(user) is True
    assert user['homeassistant']['url'] == 'http://ha.test'
    assert user['homeassistant']['token'] == 'tok1'
    assert 'ha_url' not in user['weather']
    assert 'ha_token' not in user['weather']


def test_migrate_does_not_overwrite_existing_homeassistant():
    user = {
        'homeassistant': {'url': 'http://new', 'token': 'newtok'},
        'weather': {'ha_url': 'http://old', 'ha_token': 'oldtok'},
    }
    assert migrate_legacy_homeassistant_from_weather(user) is True
    assert user['homeassistant']['url'] == 'http://new'
    assert user['homeassistant']['token'] == 'newtok'
    assert 'ha_url' not in user['weather']
    assert 'ha_token' not in user['weather']


def test_migrate_noop_when_no_legacy_keys():
    user = {'weather': {'source': 'openweather'}, 'homeassistant': {'url': '', 'token': ''}}
    orig = copy.deepcopy(user)
    assert migrate_legacy_homeassistant_from_weather(user) is False
    assert user == orig


def test_migrate_partial_only_url_in_weather():
    user = {'weather': {'ha_url': 'http://only.url'}}
    assert migrate_legacy_homeassistant_from_weather(user) is True
    assert user['homeassistant']['url'] == 'http://only.url'
    assert 'ha_url' not in user['weather']


def test_migrate_drops_empty_legacy_keys():
    user = {'weather': {'ha_url': '', 'ha_token': '   ', 'source': 'homeassistant'}}
    assert migrate_legacy_homeassistant_from_weather(user) is True
    assert 'ha_url' not in user['weather']
    assert 'ha_token' not in user['weather']


def test_confidence_floors_clamp_legacy_soft_values(tmp_path, monkeypatch):
    from app_config.app_config import app_config

    user_cfg = {
        'detection': {'min_confidence_to_store': 0.05},
        'processor': {
            'min_confidence_binary': 0.1,
            'min_confidence_to_process': 0.03,
            'min_track_duration': 0.2,
            'min_box_size_px': 24,
        },
    }
    user_config = tmp_path / 'user_config.yaml'
    user_config.write_text(yaml.safe_dump(user_cfg), encoding='utf-8')
    old_user_config_file = app_config.user_config_file
    monkeypatch.setattr(app_config, 'user_config_file', str(user_config))

    try:
        app_config.reload()

        assert app_config.get('detection.min_confidence_to_store') == 0.30
        assert app_config.get('processor.min_confidence_binary') == 0.22
        assert app_config.get('processor.min_confidence_to_process') == 0.30
        assert app_config.get('processor.min_track_duration') == 1.0
        assert app_config.get('processor.min_box_size_px') == 64

        app_config.save()
        saved = yaml.safe_load(user_config.read_text(encoding='utf-8')) or {}
        assert float(saved['detection']['min_confidence_to_store']) == 0.30
        assert float(saved['processor']['min_confidence_binary']) == 0.22
        assert float(saved['processor']['min_confidence_to_process']) == 0.30
        assert float(saved['processor']['min_track_duration']) == 1.0
        assert int(saved['processor']['min_box_size_px']) == 64
    finally:
        app_config.user_config_file = old_user_config_file
        app_config.reload()
