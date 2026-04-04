"""Telegram outgoing HTTP/SOCKS proxy config (notifications.telegram_proxy_url)."""

import util as util_mod


def test_telegram_http_proxies_empty(monkeypatch):
    def fake_get(key, default=None):
        if key == 'notifications.telegram_proxy_url':
            return ''
        if key == 'notifications.telegram_proxy_type':
            return 'socks_http'
        return default

    monkeypatch.setattr(util_mod.app_config, 'get', fake_get)
    assert util_mod._telegram_http_proxies() is None


def test_telegram_http_proxies_set(monkeypatch):
    def fake_get(key, default=None):
        if key == 'notifications.telegram_proxy_url':
            return 'socks5h://127.0.0.1:9050'
        if key == 'notifications.telegram_proxy_type':
            return 'socks_http'
        return default

    monkeypatch.setattr(util_mod.app_config, 'get', fake_get)
    assert util_mod._telegram_http_proxies() == {
        'http': 'socks5h://127.0.0.1:9050',
        'https': 'socks5h://127.0.0.1:9050',
    }


def test_telegram_http_proxies_mtproto_ignores_url(monkeypatch):
    def fake_get(key, default=None):
        if key == 'notifications.telegram_proxy_url':
            return 'socks5h://127.0.0.1:9050'
        if key == 'notifications.telegram_proxy_type':
            return 'mtproto'
        return default

    monkeypatch.setattr(util_mod.app_config, 'get', fake_get)
    assert util_mod._telegram_http_proxies() is None
