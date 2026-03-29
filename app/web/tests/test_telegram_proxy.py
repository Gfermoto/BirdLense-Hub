"""Telegram outgoing HTTP/SOCKS proxy config (notifications.telegram_proxy_url)."""

from web import util as util_mod


def test_telegram_http_proxies_empty(monkeypatch):
    def fake_get(key, default=None):
        if key == 'notifications.telegram_proxy_url':
            return ''
        return default

    monkeypatch.setattr(util_mod.app_config, 'get', fake_get)
    assert util_mod._telegram_http_proxies() is None


def test_telegram_http_proxies_set(monkeypatch):
    def fake_get(key, default=None):
        if key == 'notifications.telegram_proxy_url':
            return 'socks5h://127.0.0.1:9050'
        return default

    monkeypatch.setattr(util_mod.app_config, 'get', fake_get)
    assert util_mod._telegram_http_proxies() == {
        'http': 'socks5h://127.0.0.1:9050',
        'https': 'socks5h://127.0.0.1:9050',
    }
