"""Weather service behavior tests."""

from types import SimpleNamespace

import weather_service


def test_fetch_weather_reuses_cached_fetcher(monkeypatch):
    """`fetch_weather` should reuse in-memory fetcher cache."""
    calls = {"n": 0}

    class _Resp:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "weather": [{"main": "Clouds", "description": "broken clouds"}],
                "main": {"temp": 21, "humidity": 55, "pressure": 1003},
                "clouds": {"all": 70},
                "wind": {"speed": 2.2},
            }

    def _fake_get(url, params=None, timeout=None):
        calls["n"] += 1
        return _Resp()

    monkeypatch.setattr(weather_service.requests, "get", _fake_get)
    monkeypatch.setattr(
        weather_service,
        "app_config",
        SimpleNamespace(
            get=lambda key, default=None: {
                "weather.source": "openweather",
                "secrets.latitude": "55.75",
                "secrets.longitude": "37.61",
                "secrets.openweather_api_key": "token",
            }.get(key, default),
        ),
    )
    monkeypatch.setattr(weather_service, "_weather_fetcher", None)
    monkeypatch.setattr(weather_service, "_weather_fetcher_key", None)

    first = weather_service.fetch_weather()
    second = weather_service.fetch_weather()

    assert first["weather_main"] == "Clouds"
    assert second["weather_temp"] == 21
    assert calls["n"] == 1


def test_fetch_weather_for_ingest_cache_miss_nonblocking(monkeypatch):
    calls = {"n": 0}

    def _fake_get(url, params=None, timeout=None):
        calls["n"] += 1
        raise AssertionError("ingest path must not call weather HTTP on cache miss")

    monkeypatch.setattr(weather_service.requests, "get", _fake_get)
    monkeypatch.setattr(
        weather_service,
        "app_config",
        SimpleNamespace(
            get=lambda key, default=None: {
                "weather.source": "openweather",
                "secrets.latitude": "55.75",
                "secrets.longitude": "37.61",
                "secrets.openweather_api_key": "token",
            }.get(key, default),
        ),
    )
    monkeypatch.setattr(weather_service, "_weather_fetcher", None)
    monkeypatch.setattr(weather_service, "_weather_fetcher_key", None)

    assert weather_service.fetch_weather_for_ingest(warm_cache_async=False) == {}
    assert calls["n"] == 0


def test_fetch_weather_for_ingest_cache_hit(monkeypatch):
    monkeypatch.setattr(
        weather_service,
        "app_config",
        SimpleNamespace(
            get=lambda key, default=None: {
                "weather.source": "openweather",
                "secrets.latitude": "55.75",
                "secrets.longitude": "37.61",
                "secrets.openweather_api_key": "token",
            }.get(key, default),
        ),
    )
    fetcher = weather_service.WeatherFetcher("http://example", "55.75", "37.61", "token")
    fetcher.cached_data = {"weather_main": "Clear", "weather_temp": 10}
    fetcher.last_fetched = weather_service.datetime.now()
    monkeypatch.setattr(weather_service, "_get_weather_fetcher", lambda: fetcher)

    data = weather_service.fetch_weather_for_ingest(warm_cache_async=False)
    assert data["weather_main"] == "Clear"
