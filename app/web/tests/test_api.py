"""API integration tests for web service."""
from datetime import datetime, timedelta, timezone
import sqlite3

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
                try:
                    float(parts[1])
                except ValueError:
                    pytest.fail(f"Metric value not numeric: {parts[1]!r}")

    def test_api_metrics_same_as_metrics(self, client):
        """`/api/metrics` — отдельный эндпоинт для Grafana, тот же формат."""
        r = client.get('/api/metrics')
        assert r.status_code == 200
        assert 'text/plain' in (r.content_type or '')
        body = r.get_data(as_text=True)
        assert 'birdlense_cpu_usage_percent' in body
        assert 'birdlense_memory_used_percent' in body
        assert 'birdlense_disk_used_percent' in body
        assert 'birdlense_detections_total' in body

    def test_metrics_summary_json(self, client):
        r = client.get('/api/metrics/summary')
        assert r.status_code == 200
        assert r.is_json
        data = r.get_json()
        assert data.get('service') == 'birdlense-hub'
        assert 'notify_preview_24h' in data
        assert 'notify_preview_generated_24h' in data
        assert 'detections_total' in data
        assert isinstance(data['notify_preview_24h'], dict)

    def test_system_metrics_live_only(self, client):
        r = client.get('/api/ui/system/metrics')
        assert r.status_code == 200
        body = r.json
        assert 'cpu' in body and 'memory' in body and 'disk' in body
        assert 'visitors' not in body

    def test_system_visitors_endpoint_counts_anonymous_browsers(self, app, client):
        payload = {'browser_id': '11111111-1111-4111-8111-111111111111'}
        headers = {'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) Mobile'}
        r1 = client.post('/api/ui/system/visitors/track', json=payload, headers=headers)
        assert r1.status_code == 200

        r2 = client.post('/api/ui/system/visitors/track', json=payload, headers=headers)
        assert r2.status_code == 200

        r3 = client.post(
            '/api/ui/system/visitors/track',
            json={'browser_id': '22222222-2222-4222-8222-222222222222'},
            headers={'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36'},
        )
        assert r3.status_code == 200

        r = client.get('/api/ui/system/visitors', query_string={'days': 7})
        assert r.status_code == 200
        assert r.json['period_days'] == 7
        assert r.json['method'] == 'anonymous_browser_id'
        assert r.json['unique_visits'] == 2
        assert r.json['browser_count'] == 2
        assert r.json['device_breakdown']['mobile'] == 1
        assert r.json['device_breakdown']['desktop'] == 1
        assert isinstance(r.json['unique_visits'], int)
        assert 'species_visit_count' not in r.json

    def test_system_visitors_counts_browser_days_as_unique_visits(self, app, client):
        from models import SiteVisitor, db
        from routes.ui_system_routes import _browser_hash

        with app.app_context():
            db.session.add_all([
                SiteVisitor(
                    browser_hash=_browser_hash('same-browser'),
                    seen_day='2026-04-01',
                    device_class='desktop',
                    first_seen_at=datetime.now(timezone.utc).replace(tzinfo=None),
                    last_seen_at=datetime.now(timezone.utc).replace(tzinfo=None),
                ),
                SiteVisitor(
                    browser_hash=_browser_hash('same-browser'),
                    seen_day='2026-04-02',
                    device_class='desktop',
                    first_seen_at=datetime.now(timezone.utc).replace(tzinfo=None),
                    last_seen_at=datetime.now(timezone.utc).replace(tzinfo=None),
                ),
            ])
            db.session.commit()

        response = client.get('/api/ui/system/visitors', query_string={'days': 7})

        assert response.status_code == 200
        assert response.json['browser_count'] >= 1
        assert response.json['unique_visits'] >= 2

    def test_system_metrics_history_endpoint(self, app, client):
        from models import db, SystemResourceSample
        now = datetime.now(timezone.utc)
        with app.app_context():
            db.session.add(SystemResourceSample(
                recorded_at=now,
                cpu_percent=11.5,
                memory_percent=44.0,
                disk_percent=55.0,
                gpu_percent=None,
            ))
            db.session.commit()
        r = client.get('/api/ui/system/metrics/history', query_string={'hours': 24})
        assert r.status_code == 200
        body = r.json
        assert 'samples' in body
        assert len(body['samples']) >= 1
        s0 = body['samples'][0]
        assert s0['cpu'] == 11.5
        assert 't' in s0
        assert 'sample_interval_seconds' in body
        assert 'retention_hours' in body


class TestLibraryDatasetFlow:
    """Smoke for critical Library dataset happy-path endpoints."""

    def test_library_dataset_endpoints_smoke(self, app, client):
        from app_config.app_config import app_config

        with app.app_context():
            old_admin = app_config.get('general.settings_password')
            old_contrib = app_config.get('general.contributor_password')
            app_config.set('general.settings_password', '')
            app_config.set('general.contributor_password', '')
            try:
                r_stats = client.get('/api/ui/storage/stats')
                assert r_stats.status_code == 200
                assert isinstance(r_stats.json, list)

                r_spec_status = client.get('/api/ui/system/regenerate-spectrograms/status')
                assert r_spec_status.status_code == 200
                assert 'status' in r_spec_status.json

                r_tracks_status = client.get('/api/ui/system/regenerate-tracks/status')
                assert r_tracks_status.status_code == 200
                assert 'status' in r_tracks_status.json

                r_tracks_bad_video_ids = client.post(
                    '/api/ui/system/regenerate-tracks',
                    json={'video_ids': 'not-an-array'},
                )
                assert r_tracks_bad_video_ids.status_code == 400
                assert 'video_ids' in (r_tracks_bad_video_ids.json.get('error') or '')

                r_tracks_bad_species_ids = client.post(
                    '/api/ui/system/regenerate-tracks',
                    json={'species_ids': 'not-an-array'},
                )
                assert r_tracks_bad_species_ids.status_code == 400
                assert 'species_ids' in (r_tracks_bad_species_ids.json.get('error') or '')

                r_clean = client.post('/api/ui/dataset/clean', json={
                    'dry_run': True,
                    'remove_fullframe': False,
                    'remove_orphaned': False,
                })
                assert r_clean.status_code == 200
                assert 'dry_run' in r_clean.json
            finally:
                app_config.set('general.settings_password', old_admin)
                app_config.set('general.contributor_password', old_contrib)


class TestTrackRegenFallback:
    """Fast regen should escalate to a precise pass only when needed."""

    def test_precise_fallback_runs_after_empty_fast_pass(self):
        from routes.ui_system_routes import _run_track_regen_with_precise_fallback

        calls = []

        def fake_process(video_path, **kwargs):
            calls.append((video_path, kwargs['frame_step'], kwargs['lores_size']))
            if len(calls) == 1:
                return []
            return [{'species_name': 'Eurasian Jay'}]

        detections, precise_used = _run_track_regen_with_precise_fallback(
            '/tmp/test.mp4',
            fake_process,
            {
                'frame_step': 6,
                'lores_size': (512, 512),
            },
            lambda: {
                'frame_step': 2,
                'lores_size': (640, 640),
            },
        )

        assert precise_used is True
        assert detections == [{'species_name': 'Eurasian Jay'}]
        assert calls == [
            ('/tmp/test.mp4', 6, (512, 512)),
            ('/tmp/test.mp4', 2, (640, 640)),
        ]

    def test_precise_fallback_skips_second_pass_when_fast_found_detections(self):
        from routes.ui_system_routes import _run_track_regen_with_precise_fallback

        calls = []

        def fake_process(video_path, **kwargs):
            calls.append((video_path, kwargs['frame_step']))
            return [{'species_name': 'Great Tit'}]

        detections, precise_used = _run_track_regen_with_precise_fallback(
            '/tmp/test.mp4',
            fake_process,
            {
                'frame_step': 6,
                'lores_size': (512, 512),
            },
            lambda: {
                'frame_step': 2,
                'lores_size': (640, 640),
            },
        )

        assert precise_used is False
        assert detections == [{'species_name': 'Great Tit'}]
        assert calls == [('/tmp/test.mp4', 6)]

    def test_manual_conflict_filter_drops_unknown_same_track(self):
        from types import SimpleNamespace
        from routes.ui_system_routes import _manual_conflict_with_detection

        manual_rows = [
            SimpleNamespace(
                track_id=1,
                start_time=6.0,
                end_time=12.0,
                species=SimpleNamespace(name='Eurasian Jay'),
            )
        ]

        conflict = _manual_conflict_with_detection(
            manual_rows,
            {
                'species_name': 'Unknown',
                'track_id': 1,
                'start_time': 6.1,
                'end_time': 11.9,
            },
            lambda a, b: a.strip().lower() == b.strip().lower(),
        )
        same_species = _manual_conflict_with_detection(
            manual_rows,
            {
                'species_name': 'Eurasian Jay',
                'track_id': 1,
                'start_time': 6.1,
                'end_time': 11.9,
            },
            lambda a, b: a.strip().lower() == b.strip().lower(),
        )

        assert conflict is True
        assert same_species is False

    def test_derive_track_regen_species_scope_uses_mapping_and_prior_observed(self, app):
        from models import Species, Video, VideoSpecies, db
        from routes.ui_system_routes import _derive_track_regen_species_scope
        from app_config.app_config import app_config
        from datetime import datetime

        with app.app_context():
            old_mapping = app_config.get('detection.species_mapping')
            app_config.set('detection.species_mapping', {
                'Corvus_cornix': 'Hooded Crow',
                'Sitta_europaea': 'Eurasian Nuthatch',
            })
            try:
                sp = Species(name='Eurasian Jay')
                db.session.add(sp)
                db.session.flush()
                video = Video(
                    processor_version='test',
                    start_time=datetime(2026, 3, 25, 8, 0, 0),
                    end_time=datetime(2026, 3, 25, 8, 0, 30),
                    video_path='data/recordings/2026/03/25/080000/video.mp4',
                )
                db.session.add(video)
                db.session.flush()
                db.session.add(VideoSpecies(
                    species_id=sp.id,
                    video_id=video.id,
                    start_time=0.0,
                    end_time=12.0,
                    confidence=0.9,
                    source='video',
                ))
                db.session.commit()

                names = _derive_track_regen_species_scope(
                    datetime(2026, 3, 26, 0, 0, 0)
                )

                assert 'Eurasian Jay' in names
                assert 'Hooded Crow' in names
                assert 'Eurasian Nuthatch' in names
            finally:
                app_config.set('detection.species_mapping', old_mapping)

    def test_remap_detection_to_local_scope_maps_exotics_to_unknown(self, app):
        from routes.ui_system_routes import _remap_detection_to_local_scope

        with app.app_context():
            kept = _remap_detection_to_local_scope(
                {'species_name': 'Eurasian Jay'},
                {'eurasian jay', 'great tit'},
            )
            remapped = _remap_detection_to_local_scope(
                {'species_name': 'Gyrfalcon'},
                {'eurasian jay', 'great tit'},
            )

        assert kept['species_name'] == 'Eurasian Jay'
        assert remapped['species_name'] == 'Unknown'


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

    def test_export_ebird_returns_csv(self, client):
        ts = int(datetime.now(timezone.utc).timestamp())
        r = client.get(
            '/api/ui/timeline/export',
            query_string={'start_time': ts, 'end_time': ts, 'format': 'ebird'}
        )
        assert r.status_code == 200
        assert r.headers.get('Content-Disposition', '').endswith('birdlense_ebird.csv')
        assert 'text/csv' in (r.content_type or '')

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

    def test_timeline_accepts_observer_local_date(self, app, client):
        from app_config.app_config import app_config
        from models import Species, SpeciesVisit, Video, VideoSpecies, db

        with app.app_context():
            app_config.set('secrets.latitude', '55.7558')
            app_config.set('secrets.longitude', '37.6176')
            species = Species(name=f'Timeline Local {id(app)}')
            db.session.add(species)
            db.session.flush()
            species_name = species.name
            visit = SpeciesVisit(
                species_id=species.id,
                start_time=datetime(2026, 3, 24, 21, 5, 0),
                end_time=datetime(2026, 3, 24, 21, 15, 0),
                max_simultaneous=1,
            )
            video = Video(
                processor_version='test',
                start_time=datetime(2026, 3, 24, 21, 5, 0),
                end_time=datetime(2026, 3, 24, 21, 5, 30),
                video_path='data/recordings/2026/03/24/210500/video.mp4',
            )
            db.session.add_all([visit, video])
            db.session.flush()
            db.session.add(
                VideoSpecies(
                    video_id=video.id,
                    species_id=species.id,
                    species_visit_id=visit.id,
                    start_time=0.0,
                    end_time=5.0,
                    confidence=0.9,
                    source='video',
                    detection_provider='yolo',
                ),
            )
            db.session.commit()
        r = client.get(
            '/api/ui/timeline',
            query_string={'date': '2026-03-25'},
        )
        assert r.status_code == 200
        assert any(
            row.get('species', {}).get('name') == species_name
            for row in r.json
        )

    def test_timeline_dedupes_visit_with_multiple_video_species(self, app, client):
        """JOIN VideoSpecies must not duplicate one SpeciesVisit in the JSON list."""
        from app_config.app_config import app_config
        from models import Species, SpeciesVisit, Video, VideoSpecies, db

        with app.app_context():
            app_config.set('secrets.latitude', '55.7558')
            app_config.set('secrets.longitude', '37.6176')
            species = Species(name=f'Timeline Dedup {id(app)}')
            db.session.add(species)
            db.session.flush()
            visit = SpeciesVisit(
                species_id=species.id,
                start_time=datetime(2026, 3, 24, 21, 5, 0),
                end_time=datetime(2026, 3, 24, 21, 15, 0),
                max_simultaneous=1,
            )
            video = Video(
                processor_version='test',
                start_time=datetime(2026, 3, 24, 21, 5, 0),
                end_time=datetime(2026, 3, 24, 21, 5, 30),
                video_path=f'data/recordings/2026/03/24/210501/dedup{id(app)}.mp4',
            )
            db.session.add_all([visit, video])
            db.session.flush()
            db.session.add_all([
                VideoSpecies(
                    video_id=video.id,
                    species_id=species.id,
                    species_visit_id=visit.id,
                    start_time=0.0,
                    end_time=2.0,
                    confidence=0.9,
                    source='video',
                    detection_provider='yolo',
                ),
                VideoSpecies(
                    video_id=video.id,
                    species_id=species.id,
                    species_visit_id=visit.id,
                    start_time=3.0,
                    end_time=5.0,
                    confidence=0.85,
                    source='video',
                    detection_provider='frigate',
                ),
            ])
            db.session.commit()
            visit_id = visit.id

        from services.http_response_cache import bust_response_caches
        bust_response_caches()

        r = client.get(
            '/api/ui/timeline',
            query_string={'date': '2026-03-25'},
        )
        assert r.status_code == 200
        same_visit_rows = [row for row in r.json if row.get('id') == visit_id]
        assert len(same_visit_rows) == 1

    def test_timeline_includes_video_not_attached_to_any_visit(self, app, client):
        """Ролик за сутки без SpeciesVisit появляется как unlinked_video."""
        from datetime import datetime, timezone
        from models import Video, db
        from services.http_response_cache import bust_response_caches

        with app.app_context():
            st = datetime(2026, 3, 24, 12, 0, 0)
            v = Video(
                processor_version='test',
                start_time=st,
                end_time=st.replace(minute=1),
                video_path=f'2026/03/24/120000/orphan_timeline_{id(app)}.mp4',
            )
            db.session.add(v)
            db.session.commit()

        bust_response_caches()
        ts_start = int(datetime(2026, 3, 24, 0, 0, 0, tzinfo=timezone.utc).timestamp())
        ts_end = int(datetime(2026, 3, 24, 23, 59, 59, tzinfo=timezone.utc).timestamp())
        r = client.get(
            '/api/ui/timeline',
            query_string={'start_time': ts_start, 'end_time': ts_end},
        )
        assert r.status_code == 200
        assert any(row.get('timeline_kind') == 'unlinked_video' for row in r.json)
        unlinked = [row for row in r.json if row.get('timeline_kind') == 'unlinked_video']
        assert unlinked and all(row['id'] < 0 for row in unlinked)


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
        assert data['video'] in ('ok', 'unknown', 'error', 'not_configured')
        assert data['mqtt'] in ('ok', 'error', 'not_configured', 'not_used', 'unknown')
        assert data['esphome'] in ('ok', 'error', 'not_configured', 'not_used')
        assert data['yolo'] in ('ok', 'unknown')

    def test_status_mqtt_reflects_feed_source(self, client):
        """MQTT status is real when feed.source=mqtt, else not_used."""
        r = client.get('/api/ui/status')
        assert r.status_code == 200
        # Without MQTT broker configured, mqtt is not_configured, not_used, or unknown (timeout)
        assert r.json['mqtt'] in ('ok', 'error', 'not_configured', 'not_used', 'unknown')

    def test_status_esphome_reflects_feed_source(self, client):
        """ESPHome status is real when feed.source=esphome, else not_used."""
        r = client.get('/api/ui/status')
        assert r.status_code == 200
        assert r.json['esphome'] in ('ok', 'error', 'not_configured', 'not_used')


class TestSettings:
    def test_settings_get_returns_config(self, client):
        r = client.get('/api/ui/settings')
        # 200 без пароля или с сессией; 403 если пароль задан и сессии нет
        assert r.status_code in (200, 403)
        if r.status_code == 200:
            assert isinstance(r.json, dict)

    def test_settings_with_mcp_token(self, app, client):
        """MCP token в Authorization даёт доступ к settings без сессии."""
        from app_config.app_config import app_config
        token = (app_config.get('mcp.token') or '').strip()
        if not token:
            pytest.skip('mcp.token not configured')
        r = client.get('/api/ui/settings', headers={'Authorization': f'Bearer {token}'})
        assert r.status_code == 200
        assert isinstance(r.json, dict)


class TestFeed:
    def test_feed_dispense_returns_200_or_403_or_500(self, client):
        """Feed dispense route exists; 403 if password required, 500 if MQTT/ESPHome not configured."""
        r = client.post('/api/ui/feed/dispense')
        assert r.status_code in (200, 403, 500)
        if r.status_code == 200:
            assert 'message' in r.json
        elif r.status_code in (403, 500):
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

    def test_weather_includes_source_metadata(self, app, client, monkeypatch):
        import routes.ui_routes as ui_routes
        from app_config.app_config import app_config

        monkeypatch.setattr(
            ui_routes,
            'fetch_weather',
            lambda: {
                'weather_main': 'Rain',
                'weather_description': 'steady rain',
                'weather_temp': 7,
                'weather_humidity': 100,
                'weather_pressure': 1000,
                'weather_clouds': 100,
                'weather_wind_speed': 3,
            },
        )
        with app.app_context():
            app_config.set('weather.source', 'homeassistant')
            r = client.get('/api/ui/weather')

        assert r.status_code == 200
        assert r.json['source'] == 'homeassistant'
        assert isinstance(r.json.get('fetched_at'), str)


class TestVideos:
    def test_videos_not_found_returns_404(self, client):
        r = client.get('/api/ui/videos/999999')
        assert r.status_code == 404
        assert 'error' in r.json

    def test_video_neighbors_not_found_returns_404(self, client):
        r = client.get('/api/ui/videos/999999/neighbors')
        assert r.status_code == 404
        assert 'error' in r.json

    def test_video_neighbors_prev_next_same_utc_day(self, app, client):
        from datetime import datetime, timedelta
        from models import db, Video

        with app.app_context():
            base = datetime(2025, 3, 19, 8, 0, 0)
            videos = []
            for off_hours in (0, 2, 4):
                st = base + timedelta(hours=off_hours)
                v = Video(
                    processor_version='test',
                    start_time=st,
                    end_time=st + timedelta(minutes=1),
                    video_path=f'2025/03/19/{80000 + off_hours}/v.mp4',
                )
                db.session.add(v)
                videos.append(v)
            db.session.commit()
            v1_id, v2_id, v3_id = videos[0].id, videos[1].id, videos[2].id

        r = client.get(f'/api/ui/videos/{v2_id}/neighbors')
        assert r.status_code == 200
        j = r.json
        assert j['day_scope'] == 'utc'
        assert j['day_label'] == '2025-03-19'
        assert j['previous_id'] == v1_id
        assert j['next_id'] == v3_id
        assert j['index'] == 1
        assert j['total'] == 3

        r0 = client.get(f'/api/ui/videos/{v1_id}/neighbors')
        assert r0.status_code == 200
        assert r0.json['previous_id'] is None
        assert r0.json['next_id'] == v2_id

        r2 = client.get(f'/api/ui/videos/{v3_id}/neighbors')
        assert r2.status_code == 200
        assert r2.json['previous_id'] == v2_id
        assert r2.json['next_id'] is None

    def test_video_neighbors_local_scope_and_cross_day(self, app, client):
        from datetime import datetime, timedelta
        from models import db, Video

        with app.app_context():
            day1_late = datetime(2025, 3, 19, 22, 30, 0)  # UTC
            day2_early = datetime(2025, 3, 20, 0, 30, 0)  # UTC
            v1 = Video(
                processor_version='test',
                start_time=day1_late,
                end_time=day1_late + timedelta(minutes=1),
                video_path='2025/03/19/223000/v.mp4',
            )
            v2 = Video(
                processor_version='test',
                start_time=day2_early,
                end_time=day2_early + timedelta(minutes=1),
                video_path='2025/03/20/003000/v.mp4',
            )
            db.session.add(v1)
            db.session.add(v2)
            db.session.commit()
            v1_id = v1.id
            v2_id = v2.id

        # UTC+3 browser: 22:30 UTC => 01:30 local next day
        local = client.get(
            f'/api/ui/videos/{v1_id}/neighbors',
            query_string={
                'day_scope': 'local',
                'tz_offset_minutes': -180,
                'cross_day': '1',
            },
        )
        assert local.status_code == 200
        data = local.json
        assert data['day_scope'] == 'local'
        assert data['day_label'] == '2025-03-20'
        assert data['timezone_offset_minutes'] == -180
        # В local-дне оба ролика: сосед справа есть
        assert data['next_id'] == v2_id

    def test_video_neighbors_can_follow_primary_videos_of_visits(self, app, client):
        from datetime import datetime, timedelta
        from models import db, Video, Species, SpeciesVisit, VideoSpecies

        with app.app_context():
            species = Species(name='Visit Neighbor Bird')
            db.session.add(species)
            db.session.flush()

            base = datetime(2025, 3, 21, 8, 0, 0)

            def make_video(offset_minutes: int):
                st = base + timedelta(minutes=offset_minutes)
                video = Video(
                    processor_version='test',
                    start_time=st,
                    end_time=st + timedelta(minutes=1),
                    video_path=f'2025/03/21/{80000 + offset_minutes}/v.mp4',
                )
                db.session.add(video)
                db.session.flush()
                return video

            v1a = make_video(0)
            v1b = make_video(5)
            v2a = make_video(60)
            v2b = make_video(65)
            v3a = make_video(120)
            v3b = make_video(125)

            visits = []
            for idx, (primary, extra) in enumerate(((v1a, v1b), (v2a, v2b), (v3a, v3b)), start=1):
                visit = SpeciesVisit(
                    species_id=species.id,
                    start_time=primary.start_time,
                    end_time=extra.end_time,
                    max_simultaneous=1,
                )
                db.session.add(visit)
                db.session.flush()
                db.session.add(
                    VideoSpecies(
                        video_id=primary.id,
                        species_id=species.id,
                        species_visit_id=visit.id,
                        start_time=0.0,
                        end_time=30.0,
                        confidence=0.9,
                        source='video',
                        track_id=idx * 10,
                    ),
                )
                db.session.add(
                    VideoSpecies(
                        video_id=extra.id,
                        species_id=species.id,
                        species_visit_id=visit.id,
                        start_time=0.0,
                        end_time=30.0,
                        confidence=0.8,
                        source='video',
                        track_id=idx * 10 + 1,
                    ),
                )
                visits.append((visit, primary, extra))

            db.session.commit()
            target_visit_id = visits[1][0].id
            target_extra_id = visits[1][2].id
            prev_primary_id = visits[0][1].id
            next_primary_id = visits[2][1].id

        r = client.get(
            f'/api/ui/videos/{target_extra_id}/neighbors',
            query_string={
                'day_scope': 'utc',
                'cross_day': '1',
                'visit_id': target_visit_id,
                'neighbor_mode': 'visit_primary',
            },
        )
        assert r.status_code == 200
        data = r.get_json()
        assert data['previous_id'] == prev_primary_id
        assert data['next_id'] == next_primary_id
        assert data['total'] == 3
        assert data['index'] == 1

    def test_video_neighbors_visit_primary_requires_visit_id(self, app, client):
        from models import db, Video

        with app.app_context():
            video = Video(
                processor_version='test',
                start_time=datetime(2025, 3, 21, 8, 0, 0),
                end_time=datetime(2025, 3, 21, 8, 1, 0),
                video_path='2025/03/21/080000/v.mp4',
            )
            db.session.add(video)
            db.session.commit()
            video_id = video.id

        response = client.get(
            f'/api/ui/videos/{video_id}/neighbors',
            query_string={'neighbor_mode': 'visit_primary'},
        )

        assert response.status_code == 400
        assert 'visit_id' in response.get_json()['error']

    def test_video_neighbors_visit_primary_uses_primary_video_inside_current_day(
        self, app, client,
    ):
        from models import db, Video, Species, SpeciesVisit, VideoSpecies

        with app.app_context():
            species = Species(name='Cross Midnight Visit Neighbor Bird')
            db.session.add(species)
            db.session.flush()

            cross_primary = Video(
                processor_version='test',
                start_time=datetime(2025, 3, 20, 23, 58, 0),
                end_time=datetime(2025, 3, 21, 0, 0, 0),
                video_path='2025/03/20/235800/v.mp4',
            )
            same_day_extra = Video(
                processor_version='test',
                start_time=datetime(2025, 3, 21, 0, 2, 0),
                end_time=datetime(2025, 3, 21, 0, 3, 0),
                video_path='2025/03/21/000200/v.mp4',
            )
            next_visit_primary = Video(
                processor_version='test',
                start_time=datetime(2025, 3, 21, 1, 0, 0),
                end_time=datetime(2025, 3, 21, 1, 1, 0),
                video_path='2025/03/21/010000/v.mp4',
            )
            db.session.add_all([cross_primary, same_day_extra, next_visit_primary])
            db.session.flush()

            visit1 = SpeciesVisit(
                species_id=species.id,
                start_time=cross_primary.start_time,
                end_time=same_day_extra.end_time,
                max_simultaneous=1,
            )
            visit2 = SpeciesVisit(
                species_id=species.id,
                start_time=next_visit_primary.start_time,
                end_time=next_visit_primary.end_time,
                max_simultaneous=1,
            )
            db.session.add_all([visit1, visit2])
            db.session.flush()

            db.session.add_all([
                VideoSpecies(
                    video_id=cross_primary.id,
                    species_id=species.id,
                    species_visit_id=visit1.id,
                    start_time=0.0,
                    end_time=10.0,
                    confidence=0.9,
                    source='video',
                ),
                VideoSpecies(
                    video_id=same_day_extra.id,
                    species_id=species.id,
                    species_visit_id=visit1.id,
                    start_time=0.0,
                    end_time=10.0,
                    confidence=0.88,
                    source='video',
                ),
                VideoSpecies(
                    video_id=next_visit_primary.id,
                    species_id=species.id,
                    species_visit_id=visit2.id,
                    start_time=0.0,
                    end_time=10.0,
                    confidence=0.91,
                    source='video',
                ),
            ])
            db.session.commit()

            same_day_video_id = same_day_extra.id
            visit1_id = visit1.id
            next_primary_id = next_visit_primary.id

        response = client.get(
            f'/api/ui/videos/{same_day_video_id}/neighbors',
            query_string={
                'neighbor_mode': 'visit_primary',
                'visit_id': visit1_id,
                'day_scope': 'utc',
            },
        )

        assert response.status_code == 200
        assert response.get_json()['next_id'] == next_primary_id

    def test_video_neighbors_includes_clip_starting_before_day_but_overlapping(
        self, app, client,
    ):
        """Локальный день UTC−5: клип с start до day_start UTC, но пересекающий сутки — в списке."""
        from datetime import datetime
        from models import db, Video

        with app.app_context():
            # tz_offset +300 (JS): local = UTC − 5h. Локальные 2025-03-20 → [Mar20 05:00, Mar21 05:00) UTC.
            overlap_early_start = datetime(2025, 3, 20, 4, 0, 0)
            overlap_early_end = datetime(2025, 3, 21, 4, 0, 0)
            anchor_start = datetime(2025, 3, 21, 3, 0, 0)
            anchor_end = datetime(2025, 3, 21, 3, 30, 0)
            overlap = Video(
                processor_version='test',
                start_time=overlap_early_start,
                end_time=overlap_early_end,
                video_path='2025/03/20/040000/overlap.mp4',
            )
            anchor = Video(
                processor_version='test',
                start_time=anchor_start,
                end_time=anchor_end,
                video_path='2025/03/21/030000/v.mp4',
            )
            db.session.add_all([overlap, anchor])
            db.session.commit()
            overlap_id, anchor_id = overlap.id, anchor.id

        r = client.get(
            f'/api/ui/videos/{anchor_id}/neighbors',
            query_string={
                'day_scope': 'local',
                'tz_offset_minutes': 300,
            },
        )
        assert r.status_code == 200
        j = r.json
        assert j['day_label'] == '2025-03-20'
        assert j['total'] == 2
        assert j['index'] == 1
        assert j['previous_id'] == overlap_id
        assert j['next_id'] is None

    def test_storage_nearest_recording_day_skips_empty_days(self, app, client):
        import os
        from pathlib import Path
        import routes.ui_system_routes as ui_system_routes

        with app.app_context():
            tmp_root = Path(app.instance_path) / 'storage-nearest-day-test'
            rec_root = tmp_root / 'recordings'
            (rec_root / '2025' / '03' / '19' / '120000').mkdir(parents=True, exist_ok=True)
            (rec_root / '2025' / '03' / '22' / '130000').mkdir(parents=True, exist_ok=True)
            (rec_root / '2025' / '03' / '19' / '120000' / 'video.mp4').write_bytes(b'x')
            (rec_root / '2025' / '03' / '22' / '130000' / 'video.mp4').write_bytes(b'x')

            original_recordings_dir = ui_system_routes.recordings_dir
            ui_system_routes.recordings_dir = lambda: os.fspath(rec_root)
            try:
                prev_r = client.get(
                    '/api/ui/storage/nearest-recording-day',
                    query_string={'date': '2025-03-21', 'direction': 'prev'},
                )
                next_r = client.get(
                    '/api/ui/storage/nearest-recording-day',
                    query_string={'date': '2025-03-20', 'direction': 'next'},
                )
            finally:
                ui_system_routes.recordings_dir = original_recordings_dir

        assert prev_r.status_code == 200
        assert prev_r.get_json() == {'date': '2025-03-19', 'direction': 'prev', 'found': True}
        assert next_r.status_code == 200
        assert next_r.get_json() == {'date': '2025-03-22', 'direction': 'next', 'found': True}

    def test_delete_video_requires_access(self, client):
        """Delete returns 403 without contributor/admin access when password is set."""
        r = client.delete('/api/ui/videos/1')
        # 403 if password required and no session; 404 if video not found; 200 if no password
        assert r.status_code in (200, 403, 404)


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

    def test_species_observed_returns_list(self, client):
        r = client.get('/api/ui/species/observed')
        assert r.status_code == 200
        assert isinstance(r.json, list)
        for item in r.json:
            assert 'id' in item and 'name' in item and 'count' in item

    def test_species_track_regen_options_returns_list(self, client):
        r = client.get('/api/ui/species/track-regen-options')
        assert r.status_code == 200
        assert isinstance(r.json, list)
        for item in r.json:
            assert 'id' in item and 'name' in item and 'count' in item


class TestCorrectionsHistory:
    def test_recent_corrections_endpoint_shape(self, client):
        r = client.get('/api/ui/corrections/recent', query_string={'limit': 5})
        assert r.status_code in (200, 403)
        if r.status_code == 200:
            assert isinstance(r.json, list)
            for row in r.json:
                assert 'id' in row
                assert 'created_at' in row
                assert 'action' in row
                assert 'source' in row

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
        assert r.status_code == 200
        assert 'unlocked' in r.json
        assert r.json['unlocked'] in (True, False)


class TestStatusDebug:
    def test_status_debug_requires_access(self, client):
        from app_config.app_config import app_config

        old_admin = app_config.get('general.settings_password')
        old_contrib = app_config.get('general.contributor_password')
        app_config.set('general.settings_password', 'test-admin-password')
        app_config.set('general.contributor_password', '')
        try:
            r = client.get('/api/ui/status/debug')
            assert r.status_code == 403
        finally:
            app_config.set('general.settings_password', old_admin)
            app_config.set('general.contributor_password', old_contrib)

    def test_status_debug_returns_diagnostics_when_unlocked(self, client):
        with client.session_transaction() as sess:
            sess['access_role'] = 'admin'
            sess['settings_unlocked'] = True
        r = client.get('/api/ui/status/debug')
        assert r.status_code == 200
        data = r.json
        assert 'last_heartbeat' in data or 'cutoff_utc' in data


class TestDatabaseBackupRestore:
    def test_db_backup_endpoint_exists(self, client):
        r = client.get('/api/ui/system/db/backup')
        # 200 when unlocked and file DB is available; 403 if locked; 404 for in-memory test DB.
        assert r.status_code in (200, 403, 404)
        if r.status_code == 200:
            cd = r.headers.get('Content-Disposition', '')
            assert 'attachment' in cd.lower()
            assert '.db' in cd

    def test_db_restore_requires_file(self, client):
        r = client.post('/api/ui/system/db/restore', data={}, content_type='multipart/form-data')
        # 400 when endpoint reachable and file is missing; 403 if locked.
        assert r.status_code in (400, 403)
        if r.status_code == 400:
            assert 'error' in r.json

    def test_sqlite_backup_helper_captures_live_database(self, tmp_path):
        from routes.ui_system_routes import _sqlite_backup_to_file

        live_db = tmp_path / 'live.db'
        snapshot_db = tmp_path / 'snapshot.db'

        with sqlite3.connect(live_db) as conn:
            conn.execute('PRAGMA journal_mode=WAL')
            conn.execute('CREATE TABLE sample (value TEXT)')
            conn.execute('INSERT INTO sample(value) VALUES (?)', ('from-live-db',))
            conn.commit()

        _sqlite_backup_to_file(str(live_db), str(snapshot_db))

        with sqlite3.connect(snapshot_db) as conn:
            row = conn.execute('SELECT value FROM sample').fetchone()
        assert row == ('from-live-db',)

    def test_sqlite_replace_live_db_swaps_file_and_removes_sidecars(self, tmp_path):
        from routes.ui_system_routes import _sqlite_replace_live_db

        live_db = tmp_path / 'live.db'
        restored_db = tmp_path / 'restored.db'
        wal_path = tmp_path / 'live.db-wal'
        shm_path = tmp_path / 'live.db-shm'

        with sqlite3.connect(live_db) as conn:
            conn.execute('CREATE TABLE sample (value TEXT)')
            conn.execute('INSERT INTO sample(value) VALUES (?)', ('old-value',))
            conn.commit()

        with sqlite3.connect(restored_db) as conn:
            conn.execute('CREATE TABLE sample (value TEXT)')
            conn.execute('INSERT INTO sample(value) VALUES (?)', ('new-value',))
            conn.commit()

        wal_path.write_bytes(b'legacy wal')
        shm_path.write_bytes(b'legacy shm')

        _sqlite_replace_live_db(str(live_db), str(restored_db))

        with sqlite3.connect(live_db) as conn:
            row = conn.execute('SELECT value FROM sample').fetchone()
        assert row == ('new-value',)
        assert wal_path.exists() is False
        assert shm_path.exists() is False


class TestStoragePurge:
    def test_purge_storage_deletes_db_rows_and_files(self, app, client, tmp_path, monkeypatch):
        from app_config.app_config import app_config
        from models import Species, SpeciesVisit, Video, VideoSpecies, db
        import routes.ui_system_routes as ui_system_routes

        old_admin = app_config.get('general.settings_password')
        old_contrib = app_config.get('general.contributor_password')
        app_config.set('general.settings_password', '')
        app_config.set('general.contributor_password', '')

        recordings_root = tmp_path / 'app' / 'data' / 'recordings'
        clip_dir = recordings_root / '2026' / '03' / '26' / '031309'
        clip_dir.mkdir(parents=True, exist_ok=True)
        (clip_dir / 'video.mp4').write_bytes(b'video-bytes')
        monkeypatch.setattr(ui_system_routes, 'recordings_dir', lambda: str(recordings_root))

        try:
            with app.app_context():
                species = Species(name='Eurasian Jay')
                visit = SpeciesVisit(
                    species=species,
                    start_time=datetime(2026, 3, 26, 3, 13, 9),
                    end_time=datetime(2026, 3, 26, 3, 13, 21),
                    max_simultaneous=1,
                )
                video = Video(
                    processor_version='test',
                    start_time=datetime(2026, 3, 26, 3, 13, 9),
                    end_time=datetime(2026, 3, 26, 3, 13, 39),
                    video_path='data/recordings/2026/03/26/031309/video.mp4',
                )
                detection = VideoSpecies(
                    video=video,
                    species=species,
                    species_visit=visit,
                    start_time=0.0,
                    end_time=12.0,
                    confidence=0.91,
                    source='video',
                )
                db.session.add_all([species, visit, video, detection])
                db.session.commit()

            response = client.post('/api/ui/storage/purge', json={'date': '2026-03-26'})
            assert response.status_code == 200

            with app.app_context():
                assert Video.query.count() == 0
                assert VideoSpecies.query.count() == 0
                assert SpeciesVisit.query.count() == 0

            assert not clip_dir.exists()
        finally:
            app_config.set('general.settings_password', old_admin)
            app_config.set('general.contributor_password', old_contrib)


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


class TestSpeciesRegionalScope:
    def test_species_list_includes_regional_scope_boolean(self, client):
        r = client.get('/api/ui/species')
        assert r.status_code == 200
        data = r.json
        assert isinstance(data, list)
        for row in data[:5]:
            assert 'regional_scope' in row
            assert isinstance(row['regional_scope'], bool)

    def test_regional_scope_true_for_birdnet_detection(self, app, client):
        from datetime import datetime, timezone
        from models import Species, Video, VideoSpecies, db

        with app.app_context():
            sp = Species.query.filter(Species.parent_id.isnot(None)).first()
            if sp is None:
                import pytest
                pytest.skip('no leaf species in test DB')
            v = Video(
                processor_version='test',
                start_time=datetime.now(timezone.utc),
                end_time=datetime.now(timezone.utc),
                video_path='contract/test_clip.mp4',
            )
            db.session.add(v)
            db.session.flush()
            db.session.add(
                VideoSpecies(
                    video_id=v.id,
                    species_id=sp.id,
                    start_time=0.0,
                    end_time=1.0,
                    confidence=0.95,
                    source='audio',
                    detection_provider='birdnet_mqtt',
                )
            )
            db.session.commit()
            sid = sp.id

        # Прямой commit в БД минует processor — сбросить TTL-кэш списка видов
        from services.http_response_cache import bust_response_caches
        bust_response_caches()

        r = client.get('/api/ui/species')
        assert r.status_code == 200
        row = next((x for x in r.json if x['id'] == sid), None)
        assert row is not None
        assert row['regional_scope'] is True


class TestSpeciesXenoCanto:
    def test_xeno_canto_404_for_unknown_species(self, client):
        r = client.get('/api/ui/species/999999/xeno-canto')
        assert r.status_code == 404

    def test_xeno_canto_returns_recordings_or_empty(self, client, monkeypatch):
        # Depends on seed data - get first species from /species; no real Xeno-canto HTTP.
        from routes import ui_routes

        fake = [{
            'id': '1',
            'file': 'https://xeno-canto.org/1/test.mp3',
            'en': 'song',
            'type': 'call',
            'rec': 'r',
            'cnt': 'c',
        }]
        monkeypatch.setattr(ui_routes, 'fetch_recordings', lambda species_name, limit=5: fake)

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
            assert r.json['recordings'] == fake


class TestPush:
    """Web Push endpoints."""

    def test_push_vapid_returns_key_or_503(self, client):
        """vapid-public returns key when py-vapid available, else 503."""
        r = client.get('/api/ui/push/vapid-public')
        if r.status_code == 200:
            assert 'vapid_public_key' in r.json
        else:
            assert r.status_code == 503
            assert 'error' in r.json

    def test_push_subscribe_rejects_empty_or_invalid(self, client, monkeypatch):
        """Subscribe returns 400 when notifications disabled or payload invalid."""
        from app_config.app_config import app_config

        general = dict(app_config.config.get('general') or {})
        general['settings_password'] = ''
        general['contributor_password'] = ''
        monkeypatch.setitem(app_config.config, 'general', general)
        r = client.post(
            '/api/ui/push/subscribe',
            json={},
            content_type='application/json',
        )
        assert r.status_code == 400
        err = r.json.get('error', '').lower()
        assert 'notifications' in err or 'subscription' in err

    def test_push_subscribe_requires_keys(self, client, monkeypatch):
        from app_config.app_config import app_config

        general = dict(app_config.config.get('general') or {})
        general['settings_password'] = ''
        general['contributor_password'] = ''
        monkeypatch.setitem(app_config.config, 'general', general)
        r = client.post(
            '/api/ui/push/subscribe',
            json={'subscription': {'endpoint': 'https://example.com/push'}},
            content_type='application/json',
        )
        assert r.status_code == 400


class TestMigrationCalendar:
    """Migration calendar: species activity by month."""

    def test_migration_calendar_returns_200(self, client):
        r = client.get('/api/ui/migration-calendar')
        assert r.status_code == 200
        data = r.json
        assert 'species' in data
        assert 'month_labels' in data
        assert isinstance(data['species'], list)
        assert data['month_labels'] == [
            'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
            'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec',
        ]

    def test_migration_calendar_species_structure(self, client):
        r = client.get('/api/ui/migration-calendar')
        assert r.status_code == 200
        species = r.json['species']
        for item in species:
            assert 'id' in item and 'name' in item
            assert 'monthly_counts' in item
            assert len(item['monthly_counts']) == 12
            assert 'total' in item
            assert item['total'] == sum(item['monthly_counts'])

    def test_migration_calendar_filter_by_year(self, client):
        r = client.get('/api/ui/migration-calendar', query_string={'start_year': 2024, 'end_year': 2025})
        assert r.status_code == 200
        assert 'species' in r.json
        assert 'month_labels' in r.json

    def test_migration_calendar_filter_by_date(self, client):
        r = client.get(
            '/api/ui/migration-calendar',
            query_string={'start_date': '2024-01-01', 'end_date': '2025-12-31'},
        )
        assert r.status_code == 200
        assert 'species' in r.json
        assert 'month_labels' in r.json

    def test_migration_calendar_rejects_invalid_start_date(self, client):
        r = client.get('/api/ui/migration-calendar', query_string={'start_date': '2024/01/01'})
        assert r.status_code == 400
        assert 'error' in r.json

    def test_migration_calendar_rejects_reversed_date_range(self, client):
        r = client.get(
            '/api/ui/migration-calendar',
            query_string={'start_date': '2025-01-01', 'end_date': '2024-01-01'},
        )
        assert r.status_code == 400
        assert 'error' in r.json

    def test_migration_calendar_catalog_full_and_evidence_video(self, client):
        r = client.get(
            '/api/ui/migration-calendar',
            query_string={'catalog': 'full', 'evidence': 'video'},
        )
        assert r.status_code == 200
        assert 'species' in r.json

    def test_migration_calendar_evidence_param_ignored(self, app, client):
        from models import db, Species, SpeciesVisit, VideoSpecies

        with app.app_context():
            camera_species = Species(name='Camera only species')
            birdnet_species = Species(name='BirdNET only species')
            db.session.add_all([camera_species, birdnet_species])
            db.session.flush()

            visit_camera = SpeciesVisit(
                species_id=camera_species.id,
                start_time=datetime(2025, 3, 1, 10, 0, 0),
                end_time=datetime(2025, 3, 1, 10, 1, 0),
                max_simultaneous=1,
            )
            visit_birdnet = SpeciesVisit(
                species_id=birdnet_species.id,
                start_time=datetime(2025, 3, 2, 10, 0, 0),
                end_time=datetime(2025, 3, 2, 10, 1, 0),
                max_simultaneous=1,
            )
            db.session.add_all([visit_camera, visit_birdnet])
            db.session.flush()

            db.session.add(VideoSpecies(
                video_id=1,
                species_id=camera_species.id,
                species_visit_id=visit_camera.id,
                start_time=0,
                end_time=1,
                confidence=0.99,
                source='video',
                detection_provider='yolo',
            ))
            db.session.add(VideoSpecies(
                video_id=2,
                species_id=birdnet_species.id,
                species_visit_id=visit_birdnet.id,
                start_time=0,
                end_time=1,
                confidence=0.99,
                source='audio',
                detection_provider='birdnet_mqtt',
            ))
            db.session.commit()

        r_camera = client.get('/api/ui/migration-calendar', query_string={'evidence': 'camera'})
        r_birdnet = client.get('/api/ui/migration-calendar', query_string={'evidence': 'birdnet'})
        assert r_camera.status_code == 200
        assert r_birdnet.status_code == 200
        assert r_camera.json == r_birdnet.json

    def test_migration_calendar_rejects_bad_catalog(self, client):
        r = client.get('/api/ui/migration-calendar', query_string={'catalog': 'maybe'})
        assert r.status_code == 400


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

    def test_unknowns_limit_is_capped(self, client):
        ts = int(datetime.now(timezone.utc).timestamp())
        r = client.get(
            '/api/ui/unknowns',
            query_string={
                'start_time': ts - 86400,
                'end_time': ts,
                'limit': 999999,
            }
        )
        assert r.status_code == 200
        assert isinstance(r.json, list)
        assert len(r.json) <= 500

    def test_unknowns_excludes_legacy_import_placeholders(self, app, client):
        from models import db, Species, SpeciesVisit, Video, VideoSpecies

        now = datetime.now(timezone.utc).replace(tzinfo=None)
        with app.app_context():
            unknown = Species.query.filter_by(name='Unknown').first()
            if unknown is None:
                unknown = Species(name='Unknown', active=False)
                db.session.add(unknown)
                db.session.flush()

            video = Video(
                processor_version='1',
                start_time=now,
                end_time=now + timedelta(seconds=30),
                video_path='data/recordings/2026/03/30/120000/video.mp4',
                spectrogram_path=None,
            )
            db.session.add(video)
            db.session.flush()

            visit = SpeciesVisit(
                species_id=unknown.id,
                start_time=now,
                end_time=now + timedelta(seconds=30),
                max_simultaneous=1,
            )
            db.session.add(visit)
            db.session.flush()

            db.session.add(VideoSpecies(
                video_id=video.id,
                species_id=unknown.id,
                species_visit_id=visit.id,
                start_time=0,
                end_time=30,
                confidence=0,
                source='video',
                detection_provider='legacy',
                created_at=now,
            ))
            db.session.commit()

        ts = int(now.replace(tzinfo=timezone.utc).timestamp())
        r = client.get(
            '/api/ui/unknowns',
            query_string={'start_time': ts - 60, 'end_time': ts + 60},
        )
        assert r.status_code == 200
        assert r.json == []

    def test_unknowns_include_clip_that_overlaps_window(self, app, client):
        from models import db, Species, SpeciesVisit, Video, VideoSpecies

        with app.app_context():
            unknown = Species.query.filter_by(name='Unknown').first()
            if unknown is None:
                unknown = Species(name='Unknown', active=False)
                db.session.add(unknown)
                db.session.flush()

            video = Video(
                processor_version='1',
                start_time=datetime(2026, 3, 24, 23, 59, 50),
                end_time=datetime(2026, 3, 25, 0, 0, 20),
                video_path='data/recordings/2026/03/24/235950/video.mp4',
                spectrogram_path=None,
            )
            visit = SpeciesVisit(
                species_id=unknown.id,
                start_time=video.start_time,
                end_time=video.end_time,
                max_simultaneous=1,
            )
            db.session.add_all([video, visit])
            db.session.flush()
            detection = VideoSpecies(
                video_id=video.id,
                species_id=unknown.id,
                species_visit_id=visit.id,
                start_time=12.0,
                end_time=18.0,
                confidence=0.1,
                source='video',
                detection_provider='yolo',
                created_at=datetime(2026, 3, 25, 0, 0, 5),
            )
            db.session.add(detection)
            db.session.commit()
            detection_id = detection.id

        response = client.get(
            '/api/ui/unknowns',
            query_string={'date': '2026-03-25', 'time_of_day': 'all'},
        )

        assert response.status_code == 200
        assert any(row['id'] == detection_id for row in response.get_json())


class TestScanRecordings:
    def test_scan_import_avoids_new_legacy_unknowns_and_cleans_old_ones(
        self, app, client, monkeypatch, tmp_path,
    ):
        from app_config.app_config import app_config
        from models import db, Species, SpeciesVisit, Video, VideoSpecies

        general = dict(app_config.config.get('general') or {})
        general['settings_password'] = ''
        general['contributor_password'] = ''
        monkeypatch.setitem(app_config.config, 'general', general)

        monkeypatch.setenv('DATA_DIR', str(tmp_path))
        rec_dir = tmp_path / 'recordings' / '2026' / '03' / '30' / '131825'
        rec_dir.mkdir(parents=True)
        (rec_dir / 'video.mp4').write_bytes(b'fake-video')

        now = datetime(2026, 3, 29, 12, 0, 0, tzinfo=timezone.utc).replace(
            tzinfo=None,
        )
        with app.app_context():
            unknown = Species.query.filter_by(name='Unknown').first()
            if unknown is None:
                unknown = Species(name='Unknown', active=False)
                db.session.add(unknown)
                db.session.flush()

            old_video = Video(
                processor_version='1',
                start_time=now,
                end_time=now + timedelta(seconds=30),
                video_path='data/recordings/2026/03/29/120000/video.mp4',
                spectrogram_path=None,
            )
            db.session.add(old_video)
            db.session.flush()

            old_visit = SpeciesVisit(
                species_id=unknown.id,
                start_time=now,
                end_time=now + timedelta(seconds=30),
                max_simultaneous=1,
            )
            db.session.add(old_visit)
            db.session.flush()

            db.session.add(VideoSpecies(
                video_id=old_video.id,
                species_id=unknown.id,
                species_visit_id=old_visit.id,
                start_time=0,
                end_time=30,
                confidence=0,
                source='video',
                detection_provider='legacy',
                created_at=now,
            ))
            db.session.commit()

        response = client.post('/api/ui/system/recordings/scan')
        assert response.status_code == 200
        assert response.json['imported'] == 1
        assert response.json['cleaned_legacy_placeholders'] == 1

        with app.app_context():
            paths = {row.video_path for row in Video.query.all()}
            assert 'data/recordings/2026/03/30/131825/video.mp4' in paths
            assert VideoSpecies.query.count() == 0
            assert SpeciesVisit.query.count() == 0


class TestVerifyPasswordRateLimit:
    """POST /api/ui/settings/verify-password — brute-force throttle (issue #46)."""

    @pytest.fixture(autouse=True)
    def _clear_buckets(self, client):
        """Depends on ``client`` so the app loads before touching rate-limit state."""
        import auth as auth_mod
        with auth_mod._verify_password_lock:
            auth_mod._verify_password_attempts.clear()
        yield
        with auth_mod._verify_password_lock:
            auth_mod._verify_password_attempts.clear()

    def test_five_wrong_then_429(self, client, monkeypatch):
        from app_config.app_config import app_config
        general = dict(app_config.config.get('general') or {})
        general['settings_password'] = 'correct-horse-battery-staple'
        monkeypatch.setitem(app_config.config, 'general', general)

        for _ in range(5):
            r = client.post(
                '/api/ui/settings/verify-password',
                json={'password': 'wrong'},
            )
            assert r.status_code == 401
        r = client.post(
            '/api/ui/settings/verify-password',
            json={'password': 'wrong'},
        )
        assert r.status_code == 429
        assert r.json.get('error')
        import auth as auth_mod
        assert r.headers.get('Retry-After') == str(auth_mod.VERIFY_PASSWORD_WINDOW)

    def test_success_clears_counter(self, client, monkeypatch):
        from app_config.app_config import app_config
        general = dict(app_config.config.get('general') or {})
        general['settings_password'] = 'good-secret'
        monkeypatch.setitem(app_config.config, 'general', general)

        for _ in range(4):
            client.post('/api/ui/settings/verify-password', json={'password': 'nope'})
        r_ok = client.post(
            '/api/ui/settings/verify-password',
            json={'password': 'good-secret'},
        )
        assert r_ok.status_code == 200
        for _ in range(5):
            r = client.post(
                '/api/ui/settings/verify-password',
                json={'password': 'x'},
            )
            assert r.status_code == 401
        assert client.post(
            '/api/ui/settings/verify-password',
            json={'password': 'x'},
        ).status_code == 429

    def test_x_real_ip_separate_buckets(self, client, monkeypatch):
        """За доверенным прокси разные X-Real-IP — разные бакеты (см. TRUSTED_PROXY)."""
        monkeypatch.setenv('TRUSTED_PROXY', '1')
        from app_config.app_config import app_config
        general = dict(app_config.config.get('general') or {})
        general['settings_password'] = 's'
        monkeypatch.setitem(app_config.config, 'general', general)

        for _ in range(5):
            client.post(
                '/api/ui/settings/verify-password',
                json={'password': 'bad'},
                headers={'X-Real-IP': '198.51.100.22'},
            )
        assert client.post(
            '/api/ui/settings/verify-password',
            json={'password': 'bad'},
            headers={'X-Real-IP': '198.51.100.22'},
        ).status_code == 429
        r = client.post(
            '/api/ui/settings/verify-password',
            json={'password': 'bad'},
            headers={'X-Real-IP': '198.51.100.33'},
        )
        assert r.status_code == 401


class TestConfigAudit:
    def test_config_audit_ignores_valid_dynamic_and_schema_keys(self, client, tmp_path, monkeypatch):
        import yaml
        from app_config.app_config import app_config

        user_cfg = {
            'camera': {'stream_name': 'legacy'},
            'mqtt': {'username': 'user', 'password': 'secret'},
            'video': {'go2rtc_username': 'go2rtc-user', 'go2rtc_password': 'go2rtc-pass'},
            'species': {'tuning_target_species_ids': [1, 2, 3]},
            'ebird': {
                'species_mapping': {
                    'Gray-headed Woodpecker': 'Grey-headed Woodpecker',
                },
            },
            'processor': {
                'species_confidence_overrides': {
                    'Bird': 0.2,
                },
            },
            'secrets': {'zip': '12345'},
        }
        user_config = tmp_path / 'user_config.yaml'
        user_config.write_text(yaml.safe_dump(user_cfg), encoding='utf-8')
        monkeypatch.setattr(app_config, 'user_config_file', str(user_config))
        with client.session_transaction() as sess:
            sess['access_role'] = 'admin'
            sess['settings_unlocked'] = True

        response = client.get('/api/ui/system/config-audit')

        assert response.status_code == 200
        data = response.get_json()
        assert 'camera' not in data['deprecated_keys_present']
        assert 'camera' not in data['unknown_keys']
        assert 'mqtt.username' not in data['unknown_keys']
        assert 'mqtt.password' not in data['unknown_keys']
        assert 'video.go2rtc_username' not in data['unknown_keys']
        assert 'video.go2rtc_password' not in data['unknown_keys']
        assert 'species.tuning_target_species_ids' not in data['unknown_keys']
        assert 'ebird.species_mapping.Gray-headed Woodpecker' not in data['unknown_keys']
        assert 'processor.species_confidence_overrides.Bird' not in data['unknown_keys']
        assert 'secrets.zip' not in data['unknown_keys']

    def test_update_settings_does_not_persist_transient_zip_field(self, client, tmp_path, monkeypatch):
        import yaml
        from app_config.app_config import app_config

        user_config = tmp_path / 'user_config.yaml'
        user_config.write_text(
            yaml.safe_dump({'secrets': {'zip': '99999'}}),
            encoding='utf-8',
        )
        monkeypatch.setattr(app_config, 'user_config_file', str(user_config))
        with client.session_transaction() as sess:
            sess['access_role'] = 'admin'
            sess['settings_unlocked'] = True

        response = client.patch(
            '/api/ui/settings',
            json={
                'secrets': {
                    'zip': '12345',
                    'latitude': '55.75',
                    'longitude': '37.61',
                },
            },
        )

        assert response.status_code == 200
        assert 'zip' not in ((response.get_json() or {}).get('secrets') or {})
        assert 'zip' not in (app_config.config.get('secrets') or {})
        saved = yaml.safe_load(user_config.read_text(encoding='utf-8')) or {}
        assert 'zip' not in (saved.get('secrets') or {})


class TestSpeciesSummaryReadOnly:
    """GET /api/ui/species/:id/summary не обязан мутировать БД (containment)."""

    def test_summary_includes_metadata_trust(self, app, client):
        from models import Species, db

        unique = f'API Summary Trust Lark {id(app)}'
        with app.app_context():
            sp = Species(name=unique, metadata_status='ok')
            db.session.add(sp)
            db.session.commit()
            sid = sp.id
        r = client.get(f'/api/ui/species/{sid}/summary')
        assert r.status_code == 200
        data = r.get_json()
        assert data['species']['metadata_trust'] == 'unbound'
        assert data['species']['metadata_status'] == 'ok'

    def test_summary_hourly_activity_uses_observer_local_hour(self, app, client):
        from app_config.app_config import app_config
        from models import Species, SpeciesVisit, db

        unique = f'API Summary Time Owl {id(app)}'
        with app.app_context():
            app_config.set('secrets.latitude', '55.7558')
            app_config.set('secrets.longitude', '37.6176')
            sp = Species(name=unique, metadata_status='ok')
            db.session.add(sp)
            db.session.flush()
            db.session.add(
                SpeciesVisit(
                    species_id=sp.id,
                    start_time=datetime(2026, 3, 24, 21, 15, 0),
                    end_time=datetime(2026, 3, 24, 21, 25, 0),
                    max_simultaneous=4,
                ),
            )
            db.session.commit()
            sid = sp.id
        from services.http_response_cache import bust_response_caches
        bust_response_caches()
        r = client.get(f'/api/ui/species/{sid}/summary')
        assert r.status_code == 200
        data = r.get_json()
        assert data['stats']['hourlyActivity'][0] == 4


class TestVideoStreamAccess:
    """Поток видео для плеера: по умолчанию без пароля (Viewer)."""

    def test_stream_allows_guest_when_not_locked(self, app, client, tmp_path, monkeypatch):
        from models import Video, db

        fake = tmp_path / 'clip.mp4'
        fake.write_bytes(b'\x00\x00\x00\x20ftypisom\x00\x00\x02\x00isomiso2')
        monkeypatch.setattr('util.full_path_for_video', lambda _p: str(fake))

        vp = 'data/recordings/2026/03/31/120000/video.mp4'
        with app.app_context():
            v = Video(
                processor_version='t',
                start_time=datetime.now(timezone.utc),
                end_time=datetime.now(timezone.utc),
                video_path=vp,
            )
            db.session.add(v)
            db.session.commit()
            vid = v.id

        from app_config.app_config import app_config

        general = dict(app_config.config.get('general') or {})
        general['require_auth_for_video_stream'] = False
        monkeypatch.setitem(app_config.config, 'general', general)

        r = client.get(f'/api/ui/videos/{vid}/stream')
        assert r.status_code == 200
        assert 'video' in (r.content_type or '').lower()

    def test_stream_requires_password_when_locked(self, app, client, tmp_path, monkeypatch):
        from models import Video, db

        fake = tmp_path / 'clip2.mp4'
        fake.write_bytes(b'\x00\x00\x00\x20ftypisom\x00\x00\x02\x00isomiso2')
        monkeypatch.setattr('util.full_path_for_video', lambda _p: str(fake))

        vp = 'data/recordings/2026/03/31/130000/video.mp4'
        with app.app_context():
            v = Video(
                processor_version='t',
                start_time=datetime.now(timezone.utc),
                end_time=datetime.now(timezone.utc),
                video_path=vp,
            )
            db.session.add(v)
            db.session.commit()
            vid = v.id

        from app_config.app_config import app_config

        general = dict(app_config.config.get('general') or {})
        general['require_auth_for_video_stream'] = True
        general['settings_password'] = 'secret-stream-test'
        general['contributor_password'] = ''
        monkeypatch.setitem(app_config.config, 'general', general)

        r = client.get(f'/api/ui/videos/{vid}/stream')
        assert r.status_code == 403
