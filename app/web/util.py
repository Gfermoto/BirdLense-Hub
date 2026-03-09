import logging
import os
from datetime import timedelta, datetime, timezone


def ensure_utc(dt: datetime) -> datetime:
    """Ensure datetime is timezone-aware (UTC). SQLite returns naive datetimes."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def settings_check_access():
    """Check if settings access is allowed (no password or session unlocked)."""
    from flask import session
    pw = (app_config.get('general.settings_password') or '').strip()
    if not pw:
        return True
    return session.get('settings_unlocked') is True


import requests
import re
import time
from app_config.app_config import app_config
from models import Species, db


def _normalize_coord(v):
    """Replace comma with dot for OpenWeather API (e.g. 55,934 -> 55.934)."""
    if v is None:
        return None
    s = str(v).strip().replace(',', '.')
    return s if s else None


class WeatherFetcher:
    def __init__(self, api_url, latitude, longitude, api_key, cache_duration=timedelta(minutes=10)):
        self.api_url = api_url
        self.latitude = _normalize_coord(latitude)
        self.longitude = _normalize_coord(longitude)
        self.api_key = api_key
        self.cache_duration = cache_duration
        self.last_fetched = None
        self.cached_data = None
        self.default_params = {
            'lat': self.latitude,
            'lon': self.longitude,
            'appid': self.api_key,
            'units': 'metric'
        }

    def _is_cache_valid(self):
        """Check if the cached data is still valid."""
        if not self.cached_data or not self.last_fetched:
            return False
        return datetime.now() - self.last_fetched < self.cache_duration

    def _fetch_weather_data(self, params=None, retries=3, backoff_factor=2):
        """
        Fetches weather data from the API with retry logic.
        """
        params = params or self.default_params
        if not params.get('appid'):
            return {}
        lat = _normalize_coord(params.get('lat'))
        lon = _normalize_coord(params.get('lon'))
        if not lat or not lon:
            return {}
        params = {**params, 'lat': lat, 'lon': lon}
        delay = 1
        for attempt in range(retries):
            try:
                response = requests.get(self.api_url, params=params)
                response.raise_for_status()  # Raise an HTTPError for bad responses (4xx and 5xx)
                data = response.json()
                return {
                    'weather_main': data['weather'][0]['main'],
                    'weather_description': data['weather'][0]['description'],
                    'weather_temp': data['main']['temp'],
                    'weather_humidity': data['main']['humidity'],
                    'weather_pressure': data['main']['pressure'],
                    'weather_clouds': data['clouds']['all'],
                    'weather_wind_speed': data['wind']['speed']
                }
            except requests.RequestException as e:
                if attempt < retries - 1:
                    time.sleep(delay)
                    delay *= backoff_factor
                else:
                    logging.error(
                        f"All retries failed. Returning empty object. Error: {e}")
                    return {}

    def fetch(self):
        """
        Returns cached weather data if valid, otherwise fetches new data.
        """
        if self._is_cache_valid():
            return self.cached_data
        new_data = self._fetch_weather_data()
        self.cached_data = new_data
        self.last_fetched = datetime.now()
        return new_data


class HAWeatherFetcher:
    """Fetch weather from Home Assistant REST API."""

    def __init__(self, ha_url, entity_id, token, cache_duration=timedelta(minutes=10)):
        self.ha_url = (ha_url or '').rstrip('/')
        self.entity_id = entity_id or 'weather.home'
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
                headers={'Authorization': f'Bearer {self.token}'},
                timeout=10,
            )
            r.raise_for_status()
            data = r.json()
            attrs = data.get('attributes', {})
            return {
                'weather_main': attrs.get('condition', 'unknown'),
                'weather_description': attrs.get('condition', ''),
                'weather_temp': attrs.get('temperature'),
                'weather_humidity': attrs.get('humidity'),
                'weather_pressure': attrs.get('pressure'),
                'weather_clouds': attrs.get('cloud_coverage'),
                'weather_wind_speed': attrs.get('wind_speed'),
            }
        except Exception as e:
            logging.error(f"HA weather fetch failed: {e}")
            return {}

    def fetch(self):
        if self._is_cache_valid():
            return self.cached_data
        new_data = self._fetch()
        self.cached_data = new_data
        self.last_fetched = datetime.now()
        return new_data


def _create_weather_fetcher():
    source = app_config.get('weather.source', 'openweather')
    if source == 'homeassistant':
        ha_url = os.environ.get('HA_URL') or app_config.get('weather.ha_url')
        return HAWeatherFetcher(
            ha_url=ha_url,
            entity_id=app_config.get('weather.ha_entity_id', 'weather.home'),
            token=os.environ.get('HA_TOKEN') or app_config.get('weather.ha_token'),
        )
    lat = _normalize_coord(app_config.get('secrets.latitude'))
    lon = _normalize_coord(app_config.get('secrets.longitude'))
    return WeatherFetcher(
        api_url='https://api.openweathermap.org/data/2.5/weather',
        latitude=lat,
        longitude=lon,
        api_key=os.environ.get('OPENWEATHER_API_KEY') or app_config.get('secrets.openweather_api_key'),
    )


weather_fetcher = _create_weather_fetcher()


def fetch_weather():
    """Fetch weather using current app_config (picks up settings changes without restart)."""
    fetcher = _create_weather_fetcher()
    return fetcher.fetch()


def build_hierarchy_tree():
    species_dict = {}

    with open("seed/hierarchy_names.txt", "r") as file:
        lines = file.readlines()
    for line in lines:
        species_name, parent_name = line.strip().split("|")
        species_dict[species_name] = parent_name

    # Step 1: Create a map to store child-parent relationships
    children_map = {}
    for child, parent in species_dict.items():
        if parent not in children_map:
            children_map[parent] = []
        children_map[parent].append(child)

    # Step 2: Define a recursive function to build the tree
    def build_tree_from_parent(parent):
        if parent not in children_map:
            return {}
        return {child: build_tree_from_parent(child) for child in children_map[parent]}

    # Find the root nodes (those which are parents but not children)
    root_nodes = set(species_dict.values()) - set(species_dict.keys())

    # Build the tree for each root node
    return {root: build_tree_from_parent(root) for root in root_nodes}


def get_wikipedia_image_and_description(title):
    """Fetch image and description from Wikipedia. Returns (None, None) on any error."""
    try:
        url = f"https://en.wikipedia.org/w/api.php?action=query&prop=pageimages|pageprops|extracts&format=json&piprop=thumbnail&titles={title}&pithumbsize=300&redirects&exintro"
        headers = {'User-Agent': 'BirdLense/1.0 (Bird feeder monitoring app)'}
        response = requests.get(url, timeout=10, headers=headers)
        data = response.json()
        page = list(data.get("query", {}).get("pages", {}).values())[0]
        image_url = page.get("thumbnail", {}).get("source")
        description = re.sub(r'<[^>]*>', '', page.get("extract", "")).strip() or None
        return image_url, description
    except Exception as e:
        logging.warning(f"Wikipedia API failed for '{title}': {e}")
        return None, None


def update_species_info_from_wiki(sp):
    """Update missing species data from Wikipedia. Returns True if updated."""
    if sp.image_url and sp.description:
        return False
    image_url, description = get_wikipedia_image_and_description(
        re.sub(r'\(.*\)', '', sp.name).strip()
    )
    if image_url and not sp.image_url:
        sp.image_url = image_url
    if description and not sp.description:
        sp.description = description
    return bool(image_url or description)


def notify(message, link="live", tags=None):
    if app_config.get('general.enable_notifications'):
        requests.post("http://ntfy/birdlense",
                      data=message.encode(
                          'utf-8'),
                      headers={
                          "Title": "BirdLense",
                          "Click": f"http://birdlense.local/{link}",
                          "Tags": tags
                      })


def filter_feeder_species(species_names):
    """
    Filter out species that are unlikely to visit bird feeders based on their family categories.
    Uses configuration to determine which bird families to include.
    """
    # Get included families from config
    included_families = app_config.get('processor.included_bird_families', [])

    # Early return if no inclusion
    if not included_families:
        return species_names

    # Fetch all species in one query
    all_species = Species.query.all()

    # Build parent-child relationships map
    children_by_parent = {}
    name_to_species = {}
    for species in all_species:
        children_by_parent.setdefault(
            species.parent_id, set()).add(species.name)
        name_to_species[species.name] = species

    # Find the Birds category
    birds_category = name_to_species.get('Birds')
    if not birds_category:
        return species_names

    # Get all descendants of included families
    included_species = set()

    def add_descendants(parent_name):
        species = name_to_species.get(parent_name)
        if not species:
            return
        children = children_by_parent.get(species.id, set())
        included_species.update(children)
        for child in children:
            add_descendants(child)

    # Process each included family
    for family in included_families:
        if family in children_by_parent.get(birds_category.id, set()):
            add_descendants(family)
            included_species.add(family)

    # Filter out included species
    return [name for name in species_names if name in included_species]
