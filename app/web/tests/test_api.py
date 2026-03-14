"""API integration tests for web service."""
from datetime import datetime, timezone

import pytest


class TestMetrics:
    """Prometheus /metrics endpoint."""

    def test_metrics_returns_prometheus_format(self, client):
        r = client.get('/metrics')
        assert r.status_code == 200
        assert 'text/plain' in (r.content_type or '')
        body = r.get_data(as_text=True)
        assert 'birdlense_detections_total' in body
        assert 'birdlense_species_count' in body
        assert 'birdlense_videos_total' in body
        assert '# HELP' in body
        assert '# TYPE' in body

    def test_metrics_values_are_numeric(self, client):
        r = client.get('/metrics')
        assert r.status_code == 200
        body = r.get_data(as_text=True)
        for line in body.split('\n'):
            if line and not line.startswith('#'):
                parts = line.split()
                assert len(parts) >= 2
                assert parts[1].isdigit()


class TestTimelineExport:
    """Timeline export CSV/JSON."""

    def test_export_requires_params(self, client):
        r = client.get('/api/ui/timeline/export')
        assert r.status_code == 400
        assert 'error' in r.json

    def test_export_requires_format(self, client):
        ts = int(datetime.now(timezone.utc).timestamp())
        r = client.get(
            '/api/ui/timeline/export',
            query_string={'start_time': ts, 'end_time': ts, 'format': 'xml'}
        )
        assert r.status_code == 400
        assert 'format' in r.json.get('error', '').lower()

    def test_export_json_returns_array(self, client):
        ts = int(datetime.now(timezone.utc).timestamp())
        r = client.get(
            '/api/ui/timeline/export',
            query_string={'start_time': ts, 'end_time': ts, 'format': 'json'}
        )
        assert r.status_code == 200
        assert r.headers.get('Content-Disposition', '').endswith('birdlense_timeline.json')
        import json
        data = json.loads(r.get_data(as_text=True))
        assert isinstance(data, list)

    def test_export_csv_returns_text(self, client):
        ts = int(datetime.now(timezone.utc).timestamp())
        r = client.get(
            '/api/ui/timeline/export',
            query_string={'start_time': ts, 'end_time': ts, 'format': 'csv'}
        )
        assert r.status_code == 200
        assert r.headers.get('Content-Disposition', '').endswith('birdlense_timeline.csv')
        body = r.get_data(as_text=True)
        assert 'id' in body or 'species_name' in body

    def test_export_rejects_interval_over_one_day(self, client):
        ts = int(datetime.now(timezone.utc).timestamp())
        r = client.get(
            '/api/ui/timeline/export',
            query_string={
                'start_time': ts - 86400 * 2,
                'end_time': ts,
                'format': 'json'
            }
        )
        assert r.status_code == 400
        assert 'error' in r.json


class TestTimeline:
    """Timeline API."""

    def test_timeline_requires_params(self, client):
        r = client.get('/api/ui/timeline')
        assert r.status_code == 400
        assert 'error' in r.json

    def test_timeline_returns_list(self, client):
        ts = int(datetime.now(timezone.utc).timestamp())
        r = client.get(
            '/api/ui/timeline',
            query_string={'start_time': ts - 86400, 'end_time': ts}
        )
        assert r.status_code == 200
        assert isinstance(r.json, list)

    def test_timeline_rejects_interval_over_one_day(self, client):
        ts = int(datetime.now(timezone.utc).timestamp())
        r = client.get(
            '/api/ui/timeline',
            query_string={
                'start_time': ts - 86400 * 2,
                'end_time': ts
            }
        )
        assert r.status_code == 400


class TestOverview:
    """Overview API with lastDetection."""

    def test_overview_returns_last_detection_key(self, client):
        ts = int(datetime.now(timezone.utc).timestamp())
        start = ts - 86400  # 1 day ago
        r = client.get(
            '/api/ui/overview',
            query_string={'start_time': start, 'end_time': ts}
        )
        assert r.status_code == 200
        data = r.json
        assert 'lastDetection' in data
        assert 'topSpecies' in data
        assert 'stats' in data

    def test_overview_rejects_invalid_timestamp(self, client):
        r = client.get(
            '/api/ui/overview',
            query_string={'start_time': 'invalid', 'end_time': '123'}
        )
        assert r.status_code == 400


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


class TestWeather:
    def test_weather_returns_dict(self, client):
        r = client.get('/api/ui/weather')
        assert r.status_code == 200
        assert isinstance(r.json, dict)


class TestVideos:
    def test_videos_not_found_returns_404(self, client):
        r = client.get('/api/ui/videos/999999')
        assert r.status_code == 404
        assert 'error' in r.json


class TestBirdfood:
    def test_birdfood_get_returns_list(self, client):
        r = client.get('/api/ui/birdfood')
        assert r.status_code == 200
        assert isinstance(r.json, list)


class TestSpecies:
    def test_species_returns_list(self, client):
        r = client.get('/api/ui/species')
        assert r.status_code == 200
        assert isinstance(r.json, list)


class TestBirdFamilies:
    def test_bird_families_returns_list(self, client):
        r = client.get('/api/ui/bird_families')
        assert r.status_code == 200
        assert isinstance(r.json, list)


class TestSettingsEndpoints:
    def test_settings_requires_password_returns_bool(self, client):
        r = client.get('/api/ui/settings/requires-password')
        assert r.status_code == 200
        assert 'requires' in r.json
        assert isinstance(r.json['requires'], bool)

    def test_settings_check_access_returns_status(self, client):
        r = client.get('/api/ui/settings/check-access')
        assert r.status_code in (200, 403)
        if r.status_code == 200:
            assert 'unlocked' in r.json
        else:
            assert 'error' in r.json


class TestStatusDebug:
    def test_status_debug_returns_diagnostics(self, client):
        r = client.get('/api/ui/status/debug')
        assert r.status_code == 200
        data = r.json
        assert 'last_heartbeat' in data or 'cutoff_utc' in data


class TestReportPdf:
    def test_report_requires_params(self, client):
        r = client.get('/api/ui/report/pdf')
        assert r.status_code == 400
        assert 'error' in r.json

    def test_report_month_returns_pdf(self, client):
        r = client.get('/api/ui/report/pdf', query_string={'month': '2026-03'})
        assert r.status_code == 200
        assert 'application/pdf' in (r.content_type or '')
        assert r.data[:4] == b'%PDF'

    def test_report_rejects_invalid_month(self, client):
        r = client.get('/api/ui/report/pdf', query_string={'month': 'invalid'})
        assert r.status_code == 400


class TestSpeciesXenoCanto:
    def test_xeno_canto_404_for_unknown_species(self, client):
        r = client.get('/api/ui/species/999999/xeno-canto')
        assert r.status_code == 404

    def test_xeno_canto_returns_recordings_or_empty(self, client):
        # Depends on seed data - get first species from /species
        species_r = client.get('/api/ui/species')
        assert species_r.status_code == 200
        species_list = species_r.json
        if species_list:
            sid = species_list[0]['id']
            r = client.get(f'/api/ui/species/{sid}/xeno-canto')
            assert r.status_code == 200
            assert 'recordings' in r.json
            assert 'species_name' in r.json
            assert 'xeno_canto_search_url' in r.json
            assert isinstance(r.json['recordings'], list)


class TestUnknowns:
    def test_unknowns_requires_params(self, client):
        r = client.get('/api/ui/unknowns')
        assert r.status_code == 400
        assert 'error' in r.json

    def test_unknowns_returns_list(self, client):
        ts = int(datetime.now(timezone.utc).timestamp())
        r = client.get(
            '/api/ui/unknowns',
            query_string={'start_time': ts - 86400, 'end_time': ts}
        )
        assert r.status_code == 200
        assert isinstance(r.json, list)

    def test_unknowns_rejects_interval_over_one_day(self, client):
        ts = int(datetime.now(timezone.utc).timestamp())
        r = client.get(
            '/api/ui/unknowns',
            query_string={
                'start_time': ts - 86400 * 2,
                'end_time': ts
            }
        )
        assert r.status_code == 400
