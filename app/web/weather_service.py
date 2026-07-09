"""Weather data fetching (OpenWeather, Home Assistant).

Extracted from util.py. util.py re-exports everything here for backward compatibility.
"""

import logging
import os
import threading
import time
from datetime import timedelta, datetime

import requests

from app_config.app_config import app_config
from services.homeassistant_config import (
    get_homeassistant_token,
    get_homeassistant_url,
)


def _normalize_coord(v):
    """Replace comma with dot for OpenWeather API (e.g. 55,934 -> 55.934)."""
    if v is None:
        return None
    s = str(v).strip().replace(",", ".")
    return s if s else None


class WeatherFetcher:
    """OpenWeather: запрос текущей погоды по lat/lon с коротким TTL-кэшем в памяти."""

    def __init__(self, api_url, latitude, longitude, api_key, cache_duration=timedelta(minutes=10)):
        self.api_url = api_url
        self.latitude = _normalize_coord(latitude)
        self.longitude = _normalize_coord(longitude)
        self.api_key = api_key
        self.cache_duration = cache_duration
        self.last_fetched = None
        self.cached_data = None
        self.default_params = {"lat": self.latitude, "lon": self.longitude, "appid": self.api_key, "units": "metric"}

    def _is_cache_valid(self):
        """Check if the cached data is still valid."""
        if not self.cached_data or not self.last_fetched:
            return False
        return datetime.now() - self.last_fetched < self.cache_duration

    def _fetch_weather_data(self, params=None, retries=3, backoff_factor=2):
        params = params or self.default_params
        if not params.get("appid"):
            return {}
        lat = _normalize_coord(params.get("lat"))
        lon = _normalize_coord(params.get("lon"))
        if not lat or not lon:
            return {}
        params = {**params, "lat": lat, "lon": lon}
        delay = 1
        for attempt in range(retries):
            try:
                response = requests.get(self.api_url, params=params, timeout=15)
                response.raise_for_status()
                data = response.json()
                return {
                    "weather_main": data["weather"][0]["main"],
                    "weather_description": data["weather"][0]["description"],
                    "weather_temp": data["main"]["temp"],
                    "weather_humidity": data["main"]["humidity"],
                    "weather_pressure": data["main"]["pressure"],
                    "weather_clouds": data["clouds"]["all"],
                    "weather_wind_speed": data["wind"]["speed"],
                }
            except requests.RequestException as e:
                if attempt < retries - 1:
                    time.sleep(delay)
                    delay *= backoff_factor
                else:
                    logging.error(f"All retries failed. Returning empty object. Error: {e}")
                    return {}

    def fetch(self):
        """Вернуть закэшированные или свежие поля ``weather_*`` для сохранения в Video."""
        if self._is_cache_valid():
            return self.cached_data
        new_data = self._fetch_weather_data()
        self.cached_data = new_data
        self.last_fetched = datetime.now()
        return new_data


class HAWeatherFetcher:
    """Fetch weather from Home Assistant REST API."""

    def __init__(self, ha_url, entity_id, token, cache_duration=timedelta(minutes=10)):
        self.ha_url = (ha_url or "").rstrip("/")
        self.entity_id = entity_id or "weather.home"
        self.token = token
        self.cache_duration = cache_duration
        self.last_fetched = None
        self.cached_data = None

    def _is_cache_valid(self):
        if not self.cached_data or not self.last_fetched:
            return False
        return datetime.now() - self.last_fetched < self.cache_duration

    def _fetch(self):
        if not self.ha_url or not self.token:
            return {}
        url = f"{self.ha_url}/api/states/{self.entity_id}"
        try:
            r = requests.get(
                url,
                headers={"Authorization": f"Bearer {self.token}"},
                timeout=10,
            )
            r.raise_for_status()
            data = r.json()
            attrs = data.get("attributes", {})
            return {
                "weather_main": attrs.get("condition", "unknown"),
                "weather_description": attrs.get("condition", ""),
                "weather_temp": attrs.get("temperature"),
                "weather_humidity": attrs.get("humidity"),
                "weather_pressure": attrs.get("pressure"),
                "weather_clouds": attrs.get("cloud_coverage"),
                "weather_wind_speed": attrs.get("wind_speed"),
            }
        except Exception as e:
            logging.error(f"HA weather fetch failed: {e}")
            return {}

    def fetch(self):
        """Вернуть состояние сущности HA ``weather.*`` в том же формате, что и OpenWeather."""
        if self._is_cache_valid():
            return self.cached_data
        new_data = self._fetch()
        self.cached_data = new_data
        self.last_fetched = datetime.now()
        return new_data


def _create_weather_fetcher():
    source = app_config.get("weather.source", "openweather")
    if source == "homeassistant":
        return HAWeatherFetcher(
            ha_url=get_homeassistant_url(),
            entity_id=app_config.get("weather.ha_entity_id", "weather.home"),
            token=get_homeassistant_token(),
        )
    lat = _normalize_coord(app_config.get("secrets.latitude"))
    lon = _normalize_coord(app_config.get("secrets.longitude"))
    return WeatherFetcher(
        api_url="https://api.openweathermap.org/data/2.5/weather",
        latitude=lat,
        longitude=lon,
        api_key=os.environ.get("OPENWEATHER_API_KEY") or app_config.get("secrets.openweather_api_key"),
    )


_weather_fetcher = None
_weather_fetcher_key = None


class _WeatherFetcherProxy:
    """Compatibility proxy for legacy imports of ``weather_fetcher``."""

    def fetch(self):
        return _get_weather_fetcher().fetch()


def _current_weather_fetcher_key():
    source = app_config.get("weather.source", "openweather")
    if source == "homeassistant":
        return (
            "homeassistant",
            get_homeassistant_url(),
            app_config.get("weather.ha_entity_id", "weather.home"),
            get_homeassistant_token(),
        )
    return (
        "openweather",
        _normalize_coord(app_config.get("secrets.latitude")),
        _normalize_coord(app_config.get("secrets.longitude")),
        os.environ.get("OPENWEATHER_API_KEY") or app_config.get("secrets.openweather_api_key"),
    )


def _get_weather_fetcher():
    """Return a cached fetcher, recreating only when weather config changes."""
    global _weather_fetcher, _weather_fetcher_key
    key = _current_weather_fetcher_key()
    if _weather_fetcher is None or key != _weather_fetcher_key:
        _weather_fetcher = _create_weather_fetcher()
        _weather_fetcher_key = key
    return _weather_fetcher


def fetch_weather():
    """Fetch weather using current app_config (picks up settings changes without restart)."""
    fetcher = _get_weather_fetcher()
    return fetcher.fetch()


def fetch_weather_for_ingest(*, warm_cache_async: bool = True) -> dict:
    """Return cached weather only; never block processor finalize on HTTP (#586)."""
    fetcher = _get_weather_fetcher()
    if fetcher._is_cache_valid():
        return dict(fetcher.cached_data or {})
    if warm_cache_async:
        threading.Thread(target=fetch_weather, daemon=True).start()
    return {}


# Backward compatibility: ``compat_reexports`` imports this symbol.
weather_fetcher = _WeatherFetcherProxy()
