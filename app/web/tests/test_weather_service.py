"""Weather service behavior tests."""

from types import SimpleNamespace

import weather_service


def test_fetch_weather_reuses_cached_fetcher(monkeypatch):
    """`fetch_weather` should reuse in-memory fetcher cache."""
    calls = {'n': 0}

    class _Resp:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                'weather': [{'main': 'Clouds', 'description': 'broken clouds'}],
                'main': {'temp': 21, 'humidity': 55, 'pressure': 1003},
                'clouds': {'all': 70},
                'wind': {'speed': 2.2},
            }

    def _fake_get(url, params=None, timeout=None):
        calls["n"] += 1
        return _Resp()

    monkeypatch.setattr(weather_service.requests, 'get', _fake_get)
    monkeypatch.setattr(
        weather_service,
        "app_config",
        SimpleNamespace(
            get=lambda key, default=None: {
                'weather.source': 'openweather',
                'secrets.latitude': '55.75',
                'secrets.longitude': '37.61',
                'secrets.openweather_api_key': 'token',
            }.get(key, default),
        ),
    )
    monkeypatch.setattr(weather_service, '_weather_fetcher', None)
    monkeypatch.setattr(weather_service, '_weather_fetcher_key', None)

    first = weather_service.fetch_weather()
    second = weather_service.fetch_weather()

    assert first['weather_main'] == 'Clouds'
    assert second['weather_temp'] == 21
    assert calls['n'] == 1
