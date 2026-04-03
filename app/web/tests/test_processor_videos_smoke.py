"""Smoke tests for POST /api/processor/videos (issue #202)."""
from datetime import datetime, timezone

import pytest

PROC_SECRET = 'pytest-processor-secret-202'


@pytest.fixture(autouse=True)
def _processor_secret_env(monkeypatch):
    monkeypatch.setenv('PROCESSOR_SECRET', PROC_SECRET)
    monkeypatch.delenv('BIRDLENSE_ENV', raising=False)
    monkeypatch.setenv('FLASK_ENV', 'testing')


@pytest.fixture
def proc_headers():
    return {'X-Processor-Token': PROC_SECRET, 'Content-Type': 'application/json'}


def _base_video_payload(folder_token: str):
    t0 = datetime.now(timezone.utc).isoformat()
    t1 = datetime.now(timezone.utc).isoformat()
    return {
        'processor_version': 'pytest-1',
        'start_time': t0,
        'end_time': t1,
        'video_path': f'data/recordings/2026/04/04/{folder_token}/video.mp4',
        'spectrogram_path': '',
    }


def test_processor_videos_forbidden_wrong_token(client, monkeypatch):
    monkeypatch.setenv('PROCESSOR_SECRET', 'expected-proc-secret')
    r = client.post(
        '/api/processor/videos',
        json={},
        headers={'Content-Type': 'application/json', 'X-Processor-Token': 'wrong-token'},
    )
    assert r.status_code == 403


def test_processor_videos_missing_species_400(client, proc_headers, monkeypatch):
    from routes import processor_routes

    monkeypatch.setattr(processor_routes, 'fetch_weather', lambda: {})
    body = _base_video_payload('090010')
    body['species'] = []
    r = client.post('/api/processor/videos', json=body, headers=proc_headers)
    assert r.status_code == 400
    assert 'missing' in (r.get_json() or {}).get('error', '').lower()


def test_processor_videos_all_below_threshold_400(client, proc_headers, monkeypatch):
    from app_config.app_config import app_config
    from routes import processor_routes

    monkeypatch.setattr(processor_routes, 'fetch_weather', lambda: {})
    monkeypatch.setitem(
        app_config.config.setdefault('detection', {}),
        'min_confidence_to_store',
        0.5,
    )
    body = _base_video_payload('090011')
    body['species'] = [{
        'species_name': 'Great Tit',
        'confidence': 0.1,
        'start_time': 0,
        'end_time': 1,
        'source': 'video',
        'frames': [],
    }]
    r = client.post('/api/processor/videos', json=body, headers=proc_headers)
    assert r.status_code == 400
    err = (r.get_json() or {}).get('error', '')
    assert 'threshold' in err.lower() or 'below' in err.lower()


def test_processor_videos_success_201(app, client, proc_headers, monkeypatch):
    from app_config.app_config import app_config
    from routes import processor_routes
    from models import Video, db
    import services.visit_processor as vp_mod

    monkeypatch.setattr(processor_routes, 'fetch_weather', lambda: {})
    monkeypatch.setattr(vp_mod, 'update_species_info_from_wiki', lambda *_a, **_k: None)
    monkeypatch.setitem(app_config.config.setdefault('gallery', {}), 'enabled', False)
    monkeypatch.setitem(app_config.config.setdefault('webhook', {}), 'url', '')

    token = str(id(app))[-6:].zfill(6)
    body = _base_video_payload(token)
    body['species'] = [{
        'species_name': f'Pytest Finch {token}',
        'confidence': 0.95,
        'start_time': 0,
        'end_time': 2,
        'source': 'video',
        'frames': [],
    }]

    r = client.post('/api/processor/videos', json=body, headers=proc_headers)
    assert r.status_code == 201, r.get_data(as_text=True)
    data = r.get_json()
    assert 'video_id' in data
    vid = data['video_id']

    with app.app_context():
        assert db.session.get(Video, vid) is not None


def test_processor_videos_invalid_iso_400(client, proc_headers, monkeypatch):
    from routes import processor_routes

    monkeypatch.setattr(processor_routes, 'fetch_weather', lambda: {})
    body = {
        'processor_version': 'x',
        'start_time': 'not-a-date',
        'end_time': 'also-bad',
        'video_path': 'data/recordings/2026/04/04/090012/video.mp4',
        'spectrogram_path': '',
        'species': [{
            'species_name': 'X',
            'confidence': 1,
            'start_time': 0,
            'end_time': 1,
            'source': 'video',
            'frames': [],
        }],
    }
    r = client.post('/api/processor/videos', json=body, headers=proc_headers)
    assert r.status_code == 400
    assert 'datetime' in (r.get_json() or {}).get('error', '').lower()
