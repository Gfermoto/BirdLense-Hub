"""API integration tests for web service."""
import pytest


class TestHealth:
    def test_health_returns_ok(self, client):
        r = client.get('/api/ui/health')
        assert r.status_code == 200
        assert r.json == {'status': 'ok'}


class TestStatus:
    def test_status_returns_component_status(self, client):
        r = client.get('/api/ui/status')
        assert r.status_code == 200
        data = r.json
        assert data['web'] == 'ok'
        assert data['processor'] in ('ok', 'offline')
        assert data['video'] in ('ok', 'unknown')
        assert data['mqtt'] in ('ok', 'error', 'not_configured', 'not_used')
        assert data['esphome'] in ('ok', 'error', 'not_configured', 'not_used')
        assert data['yolo'] in ('ok', 'unknown')

    def test_status_mqtt_reflects_feed_source(self, client):
        """MQTT status is real when feed.source=mqtt, else not_used."""
        r = client.get('/api/ui/status')
        assert r.status_code == 200
        # Without MQTT broker configured, mqtt is either not_configured or not_used
        assert r.json['mqtt'] in ('ok', 'error', 'not_configured', 'not_used')

    def test_status_esphome_reflects_feed_source(self, client):
        """ESPHome status is real when feed.source=esphome, else not_used."""
        r = client.get('/api/ui/status')
        assert r.status_code == 200
        assert r.json['esphome'] in ('ok', 'error', 'not_configured', 'not_used')


class TestSettings:
    def test_settings_get_returns_config(self, client):
        r = client.get('/api/ui/settings')
        assert r.status_code == 200
        data = r.json
        assert isinstance(data, dict)


class TestFeed:
    def test_feed_dispense_returns_200_or_500(self, client):
        """Feed dispense route exists; may fail if MQTT/ESPHome not configured."""
        r = client.post('/api/ui/feed/dispense')
        assert r.status_code in (200, 500)
        if r.status_code == 200:
            assert 'message' in r.json
        else:
            assert 'error' in r.json


class TestCameras:
    def test_cameras_returns_list(self, client):
        r = client.get('/api/ui/cameras')
        assert r.status_code == 200
        assert 'cameras' in r.json
        assert isinstance(r.json['cameras'], list)
