"""Notification delivery and observability regressions."""

import json
import os
from datetime import datetime, timezone

import notifications as notifications_mod
import requests
from routes import processor_routes as processor_routes_mod


class _FakeResponse:
    def __init__(self, ok=True, status_code=200, text='', payload=None):
        self.ok = ok
        self.status_code = status_code
        self.text = text
        self._payload = payload or {}

    def json(self):
        return self._payload


def _fake_config(overrides):
    defaults = {
        'general.enable_notifications': True,
        'notifications.telegram_bot_token': 'token',
        'notifications.telegram_chat_id': 'chat-id',
        'notifications.base_url': 'https://birdlense.example',
        'notifications.send_photo': True,
        'notifications.link_preview_large': False,
        'notifications.disable_notification': False,
        'notifications.protect_content': False,
        'notifications.telegram_timeout': 60,
        'notifications.telegram_retries': 1,
        'notifications.compress_photo_over_kb': 0,
        'notifications.telegram_max_side_px': 0,
        'notifications.message_thread_id': '',
        'notifications.paid_media_view_star_count': 0,
        'notifications.paid_media_forward_star_count': 0,
        'notifications.use_custom_emoji': False,
    }
    defaults.update(overrides)

    def _get(key, default=None):
        return defaults.get(key, default)

    return _get


def test_notify_returns_photo_delivery_metadata_on_success(monkeypatch):
    monkeypatch.setattr(notifications_mod.app_config, 'get', _fake_config({}))
    monkeypatch.setattr(notifications_mod, '_telegram_proxy_mode', lambda: 'none')
    monkeypatch.setattr(notifications_mod, '_compress_image_for_telegram', lambda image_bytes: image_bytes)

    sent = []

    def fake_request(method, url, timeout, **kwargs):
        sent.append((method, url, timeout, kwargs))
        return _FakeResponse(ok=True)

    monkeypatch.setattr(notifications_mod, '_telegram_request', fake_request)

    result = notifications_mod.notify(
        'Black-crowned Night-Heron Detected',
        image_bytes=b'jpeg-data',
        link='videos/443',
        timestamp=datetime.now(timezone.utc),
    )

    assert result['telegram_delivery'] == 'photo'
    assert result['photo_requested'] is True
    assert result['photo_available'] is True
    assert result['photo_sent'] is True
    assert result['fallback_reason'] is None
    assert result['link_url'] == 'https://birdlense.example/videos/443'
    assert len(sent) == 1
    assert sent[0][1].endswith('/sendPhoto')


def test_telegram_request_triggers_proxy_refresh_after_connection_error(monkeypatch):
    monkeypatch.setattr(
        notifications_mod.app_config,
        'get',
        _fake_config({
            'notifications.telegram_proxy_type': 'socks_http',
            'notifications.telegram_proxy_url': 'socks5h://127.0.0.1:9050',
            'notifications.telegram_retries': 1,
        }),
    )
    monkeypatch.setattr(notifications_mod, '_telegram_proxy_mode', lambda: 'socks_http')
    monkeypatch.setattr(
        notifications_mod,
        'refresh_telegram_proxy',
        lambda: {'checked': 1, 'working': 1, 'best_proxy': 'socks5h://127.0.0.1:9050'},
    )
    monkeypatch.setattr(
        notifications_mod.threading,
        'Thread',
        lambda target=None, daemon=None, **kwargs: type(
            'ImmediateThread',
            (),
            {'start': lambda self: target() if target else None},
        )(),
    )

    monkeypatch.setattr(
        notifications_mod.requests,
        'request',
        lambda *args, **kwargs: (_ for _ in ()).throw(requests.ConnectionError('network unreachable')),
    )

    try:
        notifications_mod._telegram_request('POST', 'https://api.telegram.org/bot/sendMessage', timeout=1)
    except requests.ConnectionError:
        pass

    assert notifications_mod.app_config.get('notifications.telegram_proxy_url') == 'socks5h://127.0.0.1:9050'


def test_notify_retries_photo_with_aggressive_jpeg_before_text_fallback(monkeypatch):
    monkeypatch.setattr(notifications_mod.app_config, 'get', _fake_config({}))
    monkeypatch.setattr(notifications_mod, '_telegram_proxy_mode', lambda: 'none')

    compress_calls = []

    def fake_compress(image_bytes, aggressive=False):
        compress_calls.append(aggressive)
        return b'aggressive-jpeg' if aggressive else b'normal-jpeg'

    monkeypatch.setattr(notifications_mod, '_compress_image_for_telegram', fake_compress)

    requests_seen = []

    def fake_request(method, url, timeout, **kwargs):
        requests_seen.append(kwargs['files']['photo'][1])
        if len(requests_seen) == 1:
            return _FakeResponse(ok=False, status_code=400, text='IMAGE_PROCESS_FAILED')
        return _FakeResponse(ok=True)

    text_fallback_calls = []

    def fake_send_message(*args, **kwargs):
        text_fallback_calls.append((args, kwargs))
        return _FakeResponse(ok=True)

    monkeypatch.setattr(notifications_mod, '_telegram_request', fake_request)
    monkeypatch.setattr(notifications_mod, '_telegram_send_message', fake_send_message)

    result = notifications_mod.notify(
        'Black-crowned Night-Heron Detected',
        image_bytes=b'jpeg-data',
        link='videos/443',
    )

    assert result['telegram_delivery'] == 'photo'
    assert result['photo_sent'] is True
    assert result['fallback_reason'] is None
    assert compress_calls == [False, True]
    assert requests_seen == [b'normal-jpeg', b'aggressive-jpeg']
    assert text_fallback_calls == []


def test_notify_returns_text_fallback_reason_when_photo_send_fails(monkeypatch):
    monkeypatch.setattr(notifications_mod.app_config, 'get', _fake_config({}))
    monkeypatch.setattr(notifications_mod, '_telegram_proxy_mode', lambda: 'none')
    monkeypatch.setattr(notifications_mod, '_compress_image_for_telegram', lambda image_bytes, aggressive=False: image_bytes)
    monkeypatch.setattr(
        notifications_mod,
        '_telegram_request',
        lambda method, url, timeout, **kwargs: _FakeResponse(ok=False, status_code=500, text='upstream down'),
    )

    text_fallback_calls = []

    def fake_send_message(*args, **kwargs):
        text_fallback_calls.append((args, kwargs))
        return _FakeResponse(ok=True)

    monkeypatch.setattr(notifications_mod, '_telegram_send_message', fake_send_message)

    result = notifications_mod.notify(
        'Black-crowned Night-Heron Detected',
        image_bytes=b'jpeg-data',
        link='videos/443',
    )

    assert result['telegram_delivery'] == 'text_fallback'
    assert result['photo_sent'] is False
    assert result['fallback_reason'] == 'telegram_photo_failed'
    assert len(text_fallback_calls) == 1


def test_notify_text_fallback_includes_diagnostic_note(monkeypatch):
    monkeypatch.setattr(notifications_mod.app_config, 'get', _fake_config({}))
    monkeypatch.setattr(notifications_mod, '_telegram_proxy_mode', lambda: 'none')

    text_calls = []

    def fake_send_message(token, chat_id, text, **kwargs):
        text_calls.append(text)
        return _FakeResponse(ok=True)

    monkeypatch.setattr(notifications_mod, '_telegram_send_message', fake_send_message)

    result = notifications_mod.notify(
        'Black-crowned Night-Heron Detected',
        image_bytes=None,
        link='videos/443',
        fallback_reason_hint='decode_failed',
    )

    assert result['telegram_delivery'] == 'text'
    assert result['fallback_reason'] == 'decode_failed'
    assert 'preview decode failed' in text_calls[0]


def test_notify_text_only_mode_skips_preview_diagnostic(monkeypatch):
    monkeypatch.setattr(notifications_mod.app_config, 'get', _fake_config({}))
    monkeypatch.setattr(notifications_mod, '_telegram_proxy_mode', lambda: 'none')

    text_calls = []

    def fake_send_message(token, chat_id, text, **kwargs):
        text_calls.append(text)
        return _FakeResponse(ok=True)

    monkeypatch.setattr(notifications_mod, '_telegram_send_message', fake_send_message)

    result = notifications_mod.notify(
        'App is UP!',
        timestamp=datetime.now(timezone.utc),
        send_photo_override=False,
    )

    assert result['telegram_delivery'] == 'text'
    assert result['photo_requested'] is False
    assert result['photo_available'] is False
    assert result['fallback_reason'] is None
    assert 'photo unavailable' not in text_calls[0]


def test_notify_app_startup_uses_text_only_notification(monkeypatch):
    monkeypatch.delenv('FLASK_TESTING', raising=False)
    marker = '/tmp/.birdlense_startup_notify_sent'
    try:
        os.remove(marker)
    except OSError:
        pass

    calls = []
    monkeypatch.setattr(notifications_mod, 'notify', lambda *args, **kwargs: calls.append(kwargs))
    monkeypatch.setattr(notifications_mod.os.path, 'exists', lambda path: False)
    monkeypatch.setattr(notifications_mod.time, 'sleep', lambda _s: None)

    notifications_mod.notify_app_startup()

    assert len(calls) == 1
    assert calls[0]['send_photo_override'] is False


def test_notify_marks_text_failure_when_photo_and_fallback_both_fail(monkeypatch):
    monkeypatch.setattr(notifications_mod.app_config, 'get', _fake_config({}))
    monkeypatch.setattr(notifications_mod, '_telegram_proxy_mode', lambda: 'none')
    monkeypatch.setattr(notifications_mod, '_compress_image_for_telegram', lambda image_bytes, aggressive=False: image_bytes)
    monkeypatch.setattr(
        notifications_mod,
        '_telegram_request',
        lambda method, url, timeout, **kwargs: _FakeResponse(ok=False, status_code=500, text='upstream down'),
    )
    monkeypatch.setattr(
        notifications_mod,
        '_telegram_send_message',
        lambda *args, **kwargs: (_ for _ in ()).throw(requests.ConnectionError('fallback down')),
    )

    result = notifications_mod.notify(
        'Black-crowned Night-Heron Detected',
        image_bytes=b'jpeg-data',
        link='videos/443',
    )

    assert result['telegram_delivery'] == 'failed'
    assert result['fallback_reason'] == 'telegram_text_failed'


def test_notify_detections_logs_decode_failed_reason(app, client, monkeypatch):
    from models import ActivityLog, db

    with app.app_context():
        old_secret = processor_routes_mod.os.environ.get('PROCESSOR_SECRET')
        processor_routes_mod.os.environ['PROCESSOR_SECRET'] = ''

        monkeypatch.setattr(
            processor_routes_mod.app_config,
            'get',
            lambda key, default=None: [] if key == 'general.notification_excluded_species' else default,
        )
        monkeypatch.setattr(
            processor_routes_mod,
            'notify',
            lambda *args, **kwargs: {
                'telegram_delivery': 'text',
                'photo_requested': True,
                'photo_available': False,
                'photo_sent': False,
                'fallback_reason': 'no_preview',
                'link_url': kwargs.get('link'),
            },
        )

        response = client.post('/api/processor/notify/detections', json={
            'detection': 'Black-crowned Night-Heron',
            'image_base64': 'not-valid-base64',
            'preview_source': 'best_frame',
            'link': 'videos/443',
        })

        assert response.status_code == 200
        row = db.session.query(ActivityLog).filter(ActivityLog.type == 'notify_preview').order_by(ActivityLog.id.desc()).first()
        payload = __import__('json').loads(row.data)
        assert payload['species'] == 'Black-crowned Night-Heron'
        assert payload['preview_source'] == 'best_frame'
        assert payload['has_image'] is False
        assert payload['telegram_delivery'] == 'text'
        assert payload['fallback_reason'] == 'decode_failed'

        if old_secret is None:
            processor_routes_mod.os.environ.pop('PROCESSOR_SECRET', None)
        else:
            processor_routes_mod.os.environ['PROCESSOR_SECRET'] = old_secret


def test_notify_detections_skips_when_no_preview_context(app, client, monkeypatch):
    from models import ActivityLog, db

    with app.app_context():
        old_secret = processor_routes_mod.os.environ.get('PROCESSOR_SECRET')
        processor_routes_mod.os.environ['PROCESSOR_SECRET'] = ''

        called = []
        monkeypatch.setattr(
            processor_routes_mod.app_config,
            'get',
            lambda key, default=None: [] if key == 'general.notification_excluded_species' else default,
        )
        monkeypatch.setattr(
            processor_routes_mod,
            'notify',
            lambda *args, **kwargs: called.append((args, kwargs)),
        )

        response = client.post('/api/processor/notify/detections', json={
            'detection': 'Black-crowned Night-Heron',
            'preview_source': 'none',
            'link': 'live',
        })

        assert response.status_code == 200
        assert called == []
        row = db.session.query(ActivityLog).filter(ActivityLog.type == 'notify_preview').order_by(ActivityLog.id.desc()).first()
        payload = __import__('json').loads(row.data)
        assert payload['telegram_delivery'] == 'skipped'
        assert payload['fallback_reason'] == 'no_preview_context'
        assert payload['has_image'] is False

        if old_secret is None:
            processor_routes_mod.os.environ.pop('PROCESSOR_SECRET', None)
        else:
            processor_routes_mod.os.environ['PROCESSOR_SECRET'] = old_secret


def test_notify_detections_skips_when_notification_ineligible_even_with_image(app, client, monkeypatch):
    from models import ActivityLog, db
    import base64

    with app.app_context():
        old_secret = processor_routes_mod.os.environ.get('PROCESSOR_SECRET')
        processor_routes_mod.os.environ['PROCESSOR_SECRET'] = ''

        called = []
        monkeypatch.setattr(
            processor_routes_mod.app_config,
            'get',
            lambda key, default=None: [] if key == 'general.notification_excluded_species' else default,
        )
        monkeypatch.setattr(
            processor_routes_mod,
            'notify',
            lambda *args, **kwargs: called.append((args, kwargs)),
        )

        tiny_jpeg = base64.b64encode(
            b'\xff\xd8\xff\xdb\x00C\x00\xff\xd9',
        ).decode('ascii')

        response = client.post('/api/processor/notify/detections', json={
            'detection': 'Bird',
            'preview_source': 'bbox_crop',
            'link': 'videos/1',
            'image_base64': tiny_jpeg,
            'notification_eligible': False,
            'suppress_reason': 'review_only_generic',
        })

        assert response.status_code == 200
        assert called == []
        row = (
            db.session.query(ActivityLog)
            .filter(ActivityLog.type == 'notify_suppressed')
            .order_by(ActivityLog.id.desc())
            .first()
        )
        payload = json.loads(row.data)
        assert payload['suppress_reason'] == 'review_only_generic'
        assert payload['telegram_delivery'] == 'skipped'

        if old_secret is None:
            processor_routes_mod.os.environ.pop('PROCESSOR_SECRET', None)
        else:
            processor_routes_mod.os.environ['PROCESSOR_SECRET'] = old_secret


def test_system_observability_includes_delivery_and_fallback_counts(app, client):
    from app_config.app_config import app_config
    from models import ActivityLog, db

    with app.app_context():
        old_admin = app_config.get('general.settings_password')
        old_contrib = app_config.get('general.contributor_password')
        app_config.set('general.settings_password', '')
        app_config.set('general.contributor_password', '')
        try:
            db.session.add(ActivityLog(
                type='notify_preview',
                data=__import__('json').dumps({
                    'species': 'Black-crowned Night-Heron',
                    'preview_source': 'best_frame',
                    'telegram_delivery': 'photo',
                    'fallback_reason': None,
                }),
            ))
            db.session.add(ActivityLog(
                type='notify_preview',
                data=__import__('json').dumps({
                    'species': 'Black-crowned Night-Heron',
                    'preview_source': 'none',
                    'telegram_delivery': 'text_fallback',
                    'fallback_reason': 'telegram_photo_failed',
                }),
            ))
            db.session.add(ActivityLog(
                type='ingest_gate',
                data=json.dumps({'reason': 'video_file_missing', 'video_path': 'data/recordings/x.mp4'}),
            ))
            db.session.add(ActivityLog(
                type='notify_suppressed',
                data=json.dumps({'suppress_reason': 'review_only_generic', 'species': 'Bird'}),
            ))
            db.session.commit()

            response = client.get('/api/ui/system/observability')
            assert response.status_code == 200
            payload = response.get_json()
            assert payload['notify_preview_24h']['best_frame'] >= 1
            assert payload['notify_delivery_24h']['photo'] >= 1
            assert payload['notify_delivery_24h']['text_fallback'] >= 1
            assert payload['notify_fallback_24h']['telegram_photo_failed'] >= 1
            assert payload['ingest_gate_24h']['video_file_missing'] >= 1
            assert payload['notify_suppressed_24h']['review_only_generic'] >= 1
            assert 'rolling_7d' in payload['ml_health']
            assert 'config_fingerprint' in payload['model_lineage']
            assert 'json_summary' in payload['hub_metrics']
        finally:
            app_config.set('general.settings_password', old_admin)
            app_config.set('general.contributor_password', old_contrib)


def test_system_observability_ignores_processor_preview_generation_rows(app, client):
    from app_config.app_config import app_config
    from models import ActivityLog, db

    with app.app_context():
        old_admin = app_config.get('general.settings_password')
        old_contrib = app_config.get('general.contributor_password')
        app_config.set('general.settings_password', '')
        app_config.set('general.contributor_password', '')
        try:
            db.session.add(ActivityLog(
                type='notify_preview_generated',
                data=__import__('json').dumps({
                    'species': 'Eurasian Jay',
                    'preview_source': 'best_frame',
                    'has_image': True,
                }),
            ))
            db.session.add(ActivityLog(
                type='notify_preview',
                data=__import__('json').dumps({
                    'species': 'Eurasian Jay',
                    'preview_source': 'best_frame',
                    'telegram_delivery': 'photo',
                    'fallback_reason': None,
                }),
            ))
            db.session.commit()

            response = client.get('/api/ui/system/observability')
            assert response.status_code == 200
            payload = response.get_json()
            assert payload['notify_preview_generated_24h']['best_frame'] == 1
            assert payload['notify_preview_24h']['best_frame'] == 1
            assert payload['notify_delivery_24h']['photo'] == 1
            assert payload['notify_delivery_24h']['unknown'] == 0
            assert payload['ml_health']['rolling_30d']['window_days'] == 30
        finally:
            app_config.set('general.settings_password', old_admin)
            app_config.set('general.contributor_password', old_contrib)
