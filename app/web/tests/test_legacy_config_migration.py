"""Миграция устаревших ключей user_config (weather.ha_* → homeassistant.*)."""
import copy

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
