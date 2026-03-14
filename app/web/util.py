import json
import logging
import os
from datetime import timedelta, datetime, timezone


def ensure_utc(dt: datetime) -> datetime:
    """Ensure datetime is timezone-aware (UTC). SQLite returns naive datetimes."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def recordings_dir():
    """Path to data/recordings directory."""
    base = os.environ.get(
        'DATA_DIR',
        os.path.join(os.path.dirname(__file__), '..', 'data')
    )
    return os.path.join(base, 'recordings')


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


def _extract_common_for_hierarchy(species_name: str) -> str:
    """
    Извлечь common name для поиска в иерархии.
    "Cardinalis cardinalis (Northern Cardinal)" -> "Northern Cardinal"
    "Northern Cardinal" -> "Northern Cardinal"
    """
    if not species_name or not isinstance(species_name, str):
        return species_name or ""
    s = species_name.strip()
    m = re.match(r"^.+?\s*\(([^)]+)\)\s*$", s)
    return m.group(1).strip() if m else s


def _load_hierarchy_parent_map():
    """Загрузить маппинг child -> parent из hierarchy_names.txt."""
    path = os.path.join(os.path.dirname(__file__), "seed", "hierarchy_names.txt")
    result = {}
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if "|" in line:
                child, parent = line.split("|", 1)
                result[child.strip()] = parent.strip()
    return result


_hierarchy_parent_map = None


def get_parent_name_for_species(species_name: str) -> str | None:
    """
    Найти родительскую категорию для вида по иерархии.

    Поддерживает формат "Scientific (Common)": извлекает common name для поиска.
    Используется при создании новых видов (Frigate, BirdNET, новый YOLO).

    Returns:
        Имя родителя (например "Cardinals, Grosbeaks, and Allies") или None.
    """
    global _hierarchy_parent_map
    if _hierarchy_parent_map is None:
        _hierarchy_parent_map = _load_hierarchy_parent_map()
    key = _extract_common_for_hierarchy(species_name)
    return _hierarchy_parent_map.get(key) or _hierarchy_parent_map.get(species_name)


def build_hierarchy_tree():
    species_dict = {}
    path = os.path.join(os.path.dirname(__file__), "seed", "hierarchy_names.txt")
    with open(path, "r", encoding="utf-8") as file:
        lines = file.readlines()
    for line in lines:
        if "|" in line:
            species_name, parent_name = line.strip().split("|", 1)
            species_dict[species_name.strip()] = parent_name.strip()

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
        headers = {'User-Agent': 'BirdLense-Hub/1.0 (Bird feeder monitoring app)'}
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
    """Update missing species data from Wikipedia. Returns True if updated.

    image_url from Wikipedia is a full URL (https://upload.wikimedia.org/...).
    Frontend must use resolveImageUrl() to handle both full URLs and relative paths.
    """
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


def _telegram_button_open_live(link, emoji='📺', style='primary', icon_custom_emoji_id=None):
    """Inline button 'Open Live' with emoji and style (Bot API 9.4+).
    icon_custom_emoji_id: optional, для Premium — кастомный эмодзи вместо Unicode.
    """
    btn = {'text': 'Open Live', 'url': link, 'style': style}
    if icon_custom_emoji_id:
        btn['icon_custom_emoji_id'] = icon_custom_emoji_id
    else:
        btn['text'] = f'{emoji} Open Live'
    return btn


def _get_button_custom_emoji_id(tags):
    """Возвращает icon_custom_emoji_id для кнопки, если use_custom_emoji и ID задан."""
    if not app_config.get('notifications.use_custom_emoji', False):
        return None
    key = 'custom_emoji_id_chipmunk' if tags == 'chipmunk' else (
        'custom_emoji_id_bird' if tags == 'bird' else 'custom_emoji_id_open_live'
    )
    val = (app_config.get(f'notifications.{key}') or '').strip()
    return val if val else None


def _telegram_send_message(token, chat_id, text, link=None, button_emoji='📺',
                          button_style='primary', button_tags=None, **kwargs):
    """Build and send Telegram message with HTML, keyboard, options."""
    link_preview = {'is_disabled': True}
    if link and app_config.get('notifications.link_preview_large', False):
        link_preview = {'is_disabled': False, 'prefer_large_media': True}
        text = f"{text}\n\n{link}"

    payload = {
        'chat_id': chat_id,
        'text': text,
        'parse_mode': 'HTML',
        'disable_notification': app_config.get(
            'notifications.disable_notification', False),
        'protect_content': app_config.get(
            'notifications.protect_content', False),
        'link_preview_options': link_preview,
    }
    thread_id = app_config.get('notifications.message_thread_id')
    if thread_id is not None and thread_id != '':
        try:
            payload['message_thread_id'] = int(thread_id)
        except (ValueError, TypeError):
            pass
    if link:
        custom_id = _get_button_custom_emoji_id(button_tags)
        payload['reply_markup'] = {
            'inline_keyboard': [[_telegram_button_open_live(
                link, button_emoji, button_style, icon_custom_emoji_id=custom_id)]]
        }
    payload.update(kwargs)
    return requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json=payload,
        timeout=10,
    )


def notify(message, link="live", tags=None, image_path=None, timestamp=None):
    """Send notification via Telegram. Requires token and chat_id in config.

    timestamp: datetime or Unix int for dynamic time <t:unix:R> (Bot API 9.5).
    """
    if not app_config.get('general.enable_notifications'):
        return
    token = (app_config.get('notifications.telegram_bot_token') or '').strip()
    chat_id = (app_config.get('notifications.telegram_chat_id') or '').strip()
    if not token or not chat_id:
        return
    base_url = (app_config.get('notifications.base_url') or '').strip().rstrip('/')
    link_url = f"{base_url}/{link}" if base_url else None
    text = message
    button_emoji = '📺'
    button_tags = tags
    if tags:
        emoji = {'chipmunk': '🐿️', 'bird': '🐦', 'rocket': '🚀'}.get(tags, '🐦')
        text = f"{emoji} {message}"
        button_emoji = emoji if tags in ('chipmunk', 'bird') else '📺'
    if timestamp is not None:
        unix_ts = int(timestamp.timestamp()) if hasattr(timestamp, 'timestamp') else int(timestamp)
        # Bot API 9.5: <tg-time> — динамическое время в часовом поясе подписчика
        text = f'{text} <tg-time unix="{unix_ts}" format="r">just now</tg-time>'
    try:
        send_photo = app_config.get('notifications.send_photo', True)
        if send_photo and image_path and os.path.exists(image_path):
            view_stars = app_config.get('notifications.paid_media_view_star_count')
            forward_stars = app_config.get('notifications.paid_media_forward_star_count')
            try:
                view_stars = int(view_stars) if view_stars else 0
            except (ValueError, TypeError):
                view_stars = 0
            try:
                forward_stars = int(forward_stars) if forward_stars else 0
            except (ValueError, TypeError):
                forward_stars = 0
            view_stars = max(0, min(25000, view_stars))
            forward_stars = max(0, min(25000, forward_stars))

            # protect_content: при бесплатном просмотре — запретить пересылку, если forward_stars > 0
            # (Telegram не поддерживает отдельную плату за пересылку)
            protect = app_config.get('notifications.protect_content', False)
            if view_stars == 0 and forward_stars > 0:
                protect = True

            payload = {
                'chat_id': chat_id,
                'caption': text,
                'parse_mode': 'HTML',
                'disable_notification': app_config.get(
                    'notifications.disable_notification', False),
                'protect_content': protect,
            }
            thread_id = app_config.get('notifications.message_thread_id')
            if thread_id not in (None, ''):
                try:
                    payload['message_thread_id'] = int(thread_id)
                except (ValueError, TypeError):
                    pass
            if link_url:
                custom_id = _get_button_custom_emoji_id(button_tags)
                payload['reply_markup'] = {
                    'inline_keyboard': [[_telegram_button_open_live(
                        link_url, button_emoji, 'primary',
                        icon_custom_emoji_id=custom_id)]]
                }

            if view_stars > 0:
                payload['star_count'] = view_stars
                payload['media'] = json.dumps([
                    {'type': 'photo', 'media': 'attach://photo'}
                ])
                with open(image_path, 'rb') as f:
                    r = requests.post(
                        f"https://api.telegram.org/bot{token}/sendPaidMedia",
                        data=payload,
                        files={'photo': f},
                        timeout=15,
                    )
            else:
                with open(image_path, 'rb') as f:
                    r = requests.post(
                        f"https://api.telegram.org/bot{token}/sendPhoto",
                        data=payload,
                        files={'photo': f},
                        timeout=15,
                    )
            try:
                os.remove(image_path)
            except OSError:
                pass
        else:
            r = _telegram_send_message(
                token, chat_id, text, link=link_url,
                button_emoji=button_emoji, button_style='primary',
                button_tags=button_tags)
        if not r.ok:
            logging.warning(
                "Telegram notify failed: %s %s", r.status_code, r.text[:200])
    except requests.RequestException as e:
        logging.warning("Telegram notify error: %s", e)


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
