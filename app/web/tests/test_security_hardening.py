"""Security hardening regressions for issue #199."""

from datetime import datetime, timezone

import pytest

import util as util_mod
from routes import processor_routes as processor_routes_mod
from auth import settings_check_access


class TestTrustedProxyIpParsing:
    """Trusted proxy handling for rate-limit source IP."""

    @pytest.fixture(autouse=True)
    def _reset_env(self, monkeypatch):
        monkeypatch.delenv('TRUSTED_PROXY', raising=False)

    def test_ignores_forwarded_headers_without_trusted_proxy(self):
        """Ignore X-Real-IP unless TRUSTED_PROXY is explicitly enabled."""
        class _Req:
            headers = {'X-Real-IP': '198.51.100.22'}
            remote_addr = '127.0.0.1'

        assert util_mod.client_ip_for_rate_limit(_Req()) == '127.0.0.1'

    def test_uses_forwarded_headers_with_trusted_proxy(self, monkeypatch):
        """Honor proxy headers only when deployment marks the proxy as trusted."""
        monkeypatch.setenv('TRUSTED_PROXY', '1')

        class _Req:
            headers = {'X-Real-IP': '198.51.100.22'}
            remote_addr = '127.0.0.1'

        assert util_mod.client_ip_for_rate_limit(_Req()) == '198.51.100.22'


class TestPushSubscribeAuth:
    """Web Push subscription endpoint access checks."""

    def test_push_subscribe_requires_settings_access_when_password_set(
        self, client, monkeypatch,
    ):
        """Subscription must not mutate config without settings access."""
        from app_config.app_config import app_config

        general = dict(app_config.config.get('general') or {})
        general['enable_notifications'] = True
        general['settings_password'] = 'top-secret'
        monkeypatch.setitem(app_config.config, 'general', general)

        r = client.post(
            '/api/ui/push/subscribe',
            json={
                'subscription': {
                    'endpoint': 'https://example.com/push/1',
                    'keys': {'p256dh': 'abc', 'auth': 'def'},
                },
            },
        )
        assert r.status_code == 401


class TestProductionSettingsAccess:
    """Production defaults must not leave system routes open."""

    def test_settings_access_denied_in_production_when_passwords_missing(
        self, app, monkeypatch,
    ):
        from app_config.app_config import app_config

        general = dict(app_config.config.get('general') or {})
        general['settings_password'] = ''
        general['contributor_password'] = ''
        monkeypatch.setitem(app_config.config, 'general', general)
        monkeypatch.setenv('BIRDLENSE_ENV', 'production')
        monkeypatch.delenv('FLASK_ENV', raising=False)

        with app.test_request_context('/api/ui/system/db/backup'):
            assert settings_check_access() is False

    def test_settings_verify_password_rejects_empty_password_bootstrap_in_production(
        self, client, monkeypatch,
    ):
        from app_config.app_config import app_config

        general = dict(app_config.config.get('general') or {})
        general['settings_password'] = ''
        general['contributor_password'] = ''
        monkeypatch.setitem(app_config.config, 'general', general)
        monkeypatch.setenv('BIRDLENSE_ENV', 'production')
        monkeypatch.delenv('FLASK_ENV', raising=False)

        response = client.post('/api/ui/settings/verify-password', json={'password': ''})
        assert response.status_code == 401
        assert response.get_json()['ok'] is False

    def test_settings_requires_password_reports_true_in_production_without_passwords(
        self, client, monkeypatch,
    ):
        from app_config.app_config import app_config

        general = dict(app_config.config.get('general') or {})
        general['settings_password'] = ''
        general['contributor_password'] = ''
        monkeypatch.setitem(app_config.config, 'general', general)
        monkeypatch.setenv('BIRDLENSE_ENV', 'production')
        monkeypatch.delenv('FLASK_ENV', raising=False)

        response = client.get('/api/ui/settings/requires-password')
        assert response.status_code == 200
        assert response.get_json()['requires'] is True

    def test_settings_access_denied_in_prod_alias_when_passwords_missing(
        self, app, monkeypatch,
    ):
        from app_config.app_config import app_config

        general = dict(app_config.config.get('general') or {})
        general['settings_password'] = ''
        general['contributor_password'] = ''
        monkeypatch.setitem(app_config.config, 'general', general)
        monkeypatch.setenv('BIRDLENSE_ENV', 'PROD')
        monkeypatch.delenv('FLASK_ENV', raising=False)

        with app.test_request_context('/api/ui/system/db/backup'):
            assert settings_check_access() is False


class TestWebhookUrlValidation:
    """Webhook SSRF guardrails."""

    def test_rejects_private_ip_webhook(self):
        """Private IP webhook targets must be blocked."""
        assert processor_routes_mod._is_safe_webhook_url('http://127.0.0.1/hook') is False

    def test_rejects_non_http_scheme_webhook(self):
        """Only http/https webhook schemes are allowed."""
        assert processor_routes_mod._is_safe_webhook_url('file:///tmp/hook') is False

    def test_create_video_skips_unsafe_webhook_url(self, app, client, monkeypatch):
        """Unsafe webhook config must not result in outbound POST."""
        from app_config.app_config import app_config
        from models import BirdFood

        with app.app_context():
            BirdFood.query.delete()
            app_config.set('webhook.url', 'http://127.0.0.1:9999/hook')

        monkeypatch.setattr(processor_routes_mod, '_check_processor_secret', lambda: True)
        posted = []
        monkeypatch.setattr(processor_routes_mod.requests, 'post', lambda *args, **kwargs: posted.append((args, kwargs)))
        monkeypatch.setattr(processor_routes_mod, 'fetch_weather', lambda: {})

        response = client.post('/api/processor/videos', json={
            'processor_version': '1',
            'start_time': datetime.now(timezone.utc).isoformat(),
            'end_time': datetime.now(timezone.utc).isoformat(),
            'video_path': 'data/recordings/2026/03/30/120000/video.mp4',
            'spectrogram_path': '',
            'species': [{
                'species_name': 'Great Tit',
                'confidence': 0.99,
                'start_time': 0,
                'end_time': 1,
                'source': 'video',
                'frames': [],
            }],
        })

        assert response.status_code == 201
        assert posted == []


class TestSpeciesImageProxyAllowlist:
    """Регрессии по замечаниям CodeRabbit к PR #218 (прокси /species-image)."""

    def test_rejects_inaturalist_open_data_substring_on_evil_host(self, client):
        """Query/path с подстрокой open-data не открывает произвольный host."""
        r = client.get(
            '/api/ui/species-image',
            query_string={'url': 'https://evil.example/x?tag=inaturalist-open-data'},
        )
        assert r.status_code == 400
        err = (r.get_json() or {}).get('error', '')
        assert 'allowed' in err.lower() or 'invalid' in err.lower()

    def test_rejects_malformed_ipv6_url(self, client):
        r = client.get(
            '/api/ui/species-image',
            query_string={'url': 'https://[::1/not-a-url'},
        )
        assert r.status_code == 400

    def test_rejects_wikimedia_url_with_invalid_port(self, client):
        r = client.get(
            '/api/ui/species-image',
            query_string={
                'url': 'https://upload.wikimedia.org:99999/wikipedia/commons/1/1x/x.png',
            },
        )
        assert r.status_code == 400


class TestSafeImagePathDataDirBoundary:
    """Префикс data vs data_evil — не обходить через startswith."""

    def test_safe_image_rejects_sibling_directory_prefix(self, tmp_path, monkeypatch):
        data = tmp_path / 'data'
        data.mkdir()
        evil = tmp_path / 'data_evil'
        evil.mkdir()
        img = evil / 'x.jpg'
        img.write_bytes(b'x')
        monkeypatch.setenv('DATA_DIR', str(data))
        assert util_mod._safe_image_path_or_none(str(img)) is None
        assert util_mod._is_safe_image_path(str(img)) is False
