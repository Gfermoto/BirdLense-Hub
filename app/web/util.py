import ipaddress
import json
import logging
import os
import secrets
import threading
import time
from datetime import timedelta, datetime, timezone
from urllib.parse import urlparse

# Rate limit for verify-password: 5 failed attempts per 60 sec per IP
_verify_password_attempts: dict = {}
_verify_password_lock = threading.Lock()
VERIFY_PASSWORD_LIMIT = 5
VERIFY_PASSWORD_WINDOW = 60


def client_ip_for_rate_limit(request) -> str:
    """Client IP for throttling behind nginx. Prefer X-Real-IP / X-Forwarded-For, then remote_addr.

    Nginx sets ``X-Real-IP`` for ``/api`` (see ``nginx/standalone.conf.template``). If the app is
    reached **without** a trusted reverse proxy, clients could spoof these headers — use TLS and
    firewall so only nginx talks to Gunicorn.
    """
    def _parse_ip_fragment(raw: str):
        s = (raw or '').strip()
        if not s:
            return None
        if ',' in s:
            s = s.split(',')[0].strip()
        try:
            ipaddress.ip_address(s)
            return s
        except ValueError:
            return None

    for hdr in ('X-Real-IP', 'X-Forwarded-For'):
        parsed = _parse_ip_fragment(request.headers.get(hdr, ''))
        if parsed:
            return parsed
    ra = (getattr(request, 'remote_addr', None) or '').strip()
    return ra or 'unknown'


def _clear_verify_password_attempts(ip: str) -> None:
    """Reset failed-attempt counter after successful unlock."""
    with _verify_password_lock:
        _verify_password_attempts.pop(ip, None)


def _check_verify_password_rate_limit(ip: str) -> bool:
    """Return True if under limit, False if rate limited (too many failed attempts)."""
    with _verify_password_lock:
        now = time.monotonic()
        if ip not in _verify_password_attempts:
            return True
        attempts = [t for t in _verify_password_attempts[ip] if now - t < VERIFY_PASSWORD_WINDOW]
        _verify_password_attempts[ip] = attempts
        return len(attempts) < VERIFY_PASSWORD_LIMIT


def _record_verify_password_failure(ip: str) -> None:
    """Record a failed verify-password attempt for rate limiting."""
    with _verify_password_lock:
        now = time.monotonic()
        if ip not in _verify_password_attempts:
            _verify_password_attempts[ip] = []
        _verify_password_attempts[ip].append(now)


def verify_password_retry_after_seconds() -> int:
    """HTTP Retry-After (seconds) for 429 on verify-password."""
    return int(VERIFY_PASSWORD_WINDOW)

# Вид «Bird» / «bird» — птица без определения вида, всегда неопределённый объект
GENERIC_BIRD_SPECIES = 'Bird'


def _data_dir() -> str:
    """Base data directory (recordings, saved images, etc.)."""
    return os.environ.get('DATA_DIR') or os.path.join(
        os.path.dirname(__file__), '..', 'data'
    )


def data_dir() -> str:
    """Public access to base data directory. Use for dataset, retention, etc."""
    return _data_dir()


def _is_safe_image_path(path: str) -> bool:
    """Путь под DATA_DIR, файл существует. Защита от path traversal."""
    if not path or not isinstance(path, str) or path != os.path.normpath(path):
        return False
    base = os.path.realpath(_data_dir())
    try:
        full = os.path.realpath(path)
        return full.startswith(base) and os.path.isfile(full)
    except (OSError, ValueError):
        return False


def _safe_image_path_or_none(path: str | None) -> str | None:
    """Вернуть путь только после проверки (явный синг для потока данных CodeQL path-injection)."""
    if not path or not isinstance(path, str):
        return None
    return path if _is_safe_image_path(path) else None


def ensure_utc(dt: datetime) -> datetime:
    """Ensure datetime is timezone-aware (UTC). SQLite returns naive datetimes."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def parse_utc_timestamp(param) -> datetime:
    """Parse Unix timestamp to naive UTC datetime for DB queries. Raises ValueError on invalid input."""
    if param is None:
        raise ValueError('Timestamp is required')
    ts = int(param)
    if not (0 <= ts <= 2147483647):  # Unix timestamp range 1970–2038
        raise ValueError('Timestamp out of range')
    return datetime.fromtimestamp(ts, timezone.utc).replace(tzinfo=None)


def get_primary_video_for_visit(visit) -> object | None:
    """First video for a SpeciesVisit (for weather, path). Returns None if no video_species."""
    if not visit or not getattr(visit, 'video_species', None):
        return None
    vs_list = visit.video_species
    return vs_list[0].video if vs_list else None


def format_visit_for_timeline(visit) -> dict:
    """Format SpeciesVisit to timeline API format (detections, weather, species)."""
    video = get_primary_video_for_visit(visit)
    video_duration_seconds = None
    if video:
        v0 = ensure_utc(video.start_time)
        v1 = ensure_utc(video.end_time)
        video_duration_seconds = max(0, round((v1 - v0).total_seconds()))
    detections = []
    total_recording_seconds = 0.0
    for vs in sorted(visit.video_species, key=lambda x: x.created_at, reverse=True):
        video_start = ensure_utc(vs.video.start_time)
        seg_dur = max(0, vs.end_time - vs.start_time) if vs.end_time > vs.start_time else 0
        total_recording_seconds += seg_dur
        det = {
            'id': vs.id,
            'video_id': vs.video_id,
            'start_time': (video_start + timedelta(seconds=vs.start_time)).astimezone(timezone.utc).isoformat(),
            'end_time': (video_start + timedelta(seconds=vs.end_time)).astimezone(timezone.utc).isoformat(),
            'confidence': vs.confidence,
            'source': vs.source,
        }
        if vs.detection_provider:
            det['detection_provider'] = vs.detection_provider
        detections.append(det)
    return {
        'id': visit.id,
        'start_time': ensure_utc(visit.start_time).isoformat(),
        'end_time': ensure_utc(visit.end_time).isoformat(),
        'max_simultaneous': visit.max_simultaneous,
        'total_recording_seconds': round(total_recording_seconds),
        'video_duration_seconds': video_duration_seconds,
        'weather': {
            'temp': video.weather_temp if video else None,
            'clouds': video.weather_clouds if video else None,
        } if video else None,
        'species': {
            'id': visit.species.id,
            'name': visit.species.name,
            'image_url': visit.species.image_url,
            'parent_id': visit.species.parent_id,
        },
        'detections': detections,
    }


def recordings_dir():
    """Path to data/recordings directory."""
    return os.path.join(_data_dir(), 'recordings')


def full_path_for_video(video_path: str) -> str | None:
    """Полный путь по video_path из БД (data/recordings/YYYY/MM/DD/...)."""
    if not video_path:
        return None
    base = _data_dir()
    app_base = os.path.dirname(base)
    return os.path.normpath(os.path.join(app_base, video_path))


def _get_session_role():
    """Return 'admin' | 'contributor' | None from session."""
    from flask import session
    return session.get('access_role')


def _has_contributor_password():
    """True if contributor tier is configured (two-password mode)."""
    return bool((app_config.get('general.contributor_password') or '').strip())


def settings_check_access():
    """Check if admin access (settings, feed, system). Backward compat: no password = full access.
    Also accepts MCP token (Authorization: Bearer) for server-to-server calls."""
    from flask import session, request
    admin_pw = (app_config.get('general.settings_password') or '').strip()
    contrib_pw = (app_config.get('general.contributor_password') or '').strip()

    # MCP token из настроек — для вызовов MCP-сервера к API (Get_app_settings и т.д.)
    mcp_token = (os.environ.get('MCP_TOKEN') or app_config.get('mcp.token') or '').strip()
    if mcp_token:
        auth = request.headers.get('Authorization') or ''
        if auth.startswith('Bearer '):
            token = auth[7:].strip()
            if secrets.compare_digest(token, mcp_token):
                return True

    if not admin_pw and not contrib_pw:
        return True
    role = session.get('access_role')
    if role == 'admin':
        return True
    if not contrib_pw and role and session.get('settings_unlocked'):
        return True  # legacy: single password
    return False


def contributor_or_admin_access():
    """Check if contributor or admin (correction, reports, iNaturalist, exports)."""
    from flask import session
    admin_pw = (app_config.get('general.settings_password') or '').strip()
    contrib_pw = (app_config.get('general.contributor_password') or '').strip()
    if not admin_pw and not contrib_pw:
        return True
    role = session.get('access_role')
    if role in ('admin', 'contributor'):
        return True
    if not contrib_pw and session.get('settings_unlocked'):
        return True  # legacy
    return False


import requests
import re
import time
from app_config.app_config import app_config
from models import Species, db

_wiki_meta_cache = {}
_wiki_title_overrides = {
    'cardinals, grosbeaks, and allies': 'Cardinalidae',
    'frigatebirds, boobies, cormorants, darters, and allies': 'Suliformes',
    'grouse, quail, and allies': 'Galliformes',
    'gulls, terns, and allies': 'Laridae',
    'mockingbirds, thrashers, and allies': 'Mimidae',
    'new world sparrows and allies': 'Passerellidae',
    'old world warblers': 'Sylviidae',
    'pelicans, herons, ibises, and allies': 'Pelecaniformes',
    'skuas and alcids': 'Alcidae',
    'swifts and hummingbirds': 'Apodiformes',
    'jacobin pigeon': 'Jacobin (pigeon)',
    'jacobin pigeon ': 'Jacobin (pigeon)',
    'grey headed fish eagle': 'Grey-headed fish eagle',
}

_manual_image_overrides = {
    'jacobin pigeon': 'https://upload.wikimedia.org/wikipedia/commons/thumb/5/5c/A_Jacobin_Pigeon.JPG/330px-A_Jacobin_Pigeon.JPG',
}


def _url_hostname_lower(url: str) -> str | None:
    """Разбор hostname без небезопасной подстроковой проверки URL (CodeQL py/incomplete-url-substring-sanitization)."""
    u = (url or '').strip()
    if not u:
        return None
    try:
        parsed = urlparse(u if '://' in u else f'//{u}', allow_fragments=True)
        h = (parsed.hostname or '').lower()
        return h or None
    except ValueError:
        return None


def _host_is_wikipedia_family(hostname: str | None) -> bool:
    if not hostname:
        return False
    return hostname == 'wikipedia.org' or hostname.endswith(
        '.wikipedia.org'
    ) or hostname == 'wikimedia.org' or hostname.endswith('.wikimedia.org')


def _host_is_inaturalist(hostname: str | None) -> bool:
    if not hostname:
        return False
    return hostname == 'inaturalist.org' or hostname.endswith('.inaturalist.org')


def _url_suggests_inaturalist_asset(url: str) -> bool:
    """iNaturalist сайт или типичный open-data CDN (S3 и т.п.)."""
    h = _url_hostname_lower(url)
    if h and _host_is_inaturalist(h):
        return True
    low = url.lower()
    return 'inaturalist-open-data' in low


def infer_metadata_source_fields(
    species_name: str | None,
    image_url: str | None,
    source_url: str | None,
) -> tuple[str | None, str | None]:
    """
    Infer canonical metadata source and source URL from known URL patterns.
    """
    img = (image_url or '').strip()
    src = (source_url or '').strip()
    title = ((species_name or '').strip() or 'bird').replace(' ', '_')

    img_host = _url_hostname_lower(img)
    src_host = _url_hostname_lower(src)

    if _host_is_wikipedia_family(img_host) or _host_is_wikipedia_family(src_host):
        return 'wikipedia', (src or f'https://en.wikipedia.org/wiki/{title}')
    if _url_suggests_inaturalist_asset(img) or _url_suggests_inaturalist_asset(src):
        return 'inaturalist', (src or 'https://www.inaturalist.org/')
    return None, source_url


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
                response.raise_for_status()
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


def fetch_sun_times(date_str: str) -> dict | None:
    """Sunrise, sunset, dawn, dusk for date at configured location. Returns None if no coords."""
    from datetime import date

    lat = _normalize_coord(app_config.get('secrets.latitude'))
    lon = _normalize_coord(app_config.get('secrets.longitude'))
    if not lat or not lon:
        return None
    try:
        lat_f = float(str(lat).replace(',', '.'))
        lon_f = float(str(lon).replace(',', '.'))
    except (ValueError, TypeError):
        return None
    try:
        year, month, day = map(int, date_str.split('-'))
        d = date(year, month, day)
    except (ValueError, TypeError):
        return None
    try:
        from astral import LocationInfo
        from astral.sun import sun
        import zoneinfo

        tz = zoneinfo.ZoneInfo('UTC')
        loc = LocationInfo('', '', 'UTC', lat_f, lon_f)
        s = sun(loc.observer, date=d, tzinfo=tz)
        date_str = d.isoformat()
        return {
            'dawn': f"{date_str}T{s['dawn'].strftime('%H:%M:%S')}Z",
            'sunrise': f"{date_str}T{s['sunrise'].strftime('%H:%M:%S')}Z",
            'noon': f"{date_str}T{s['noon'].strftime('%H:%M:%S')}Z",
            'sunset': f"{date_str}T{s['sunset'].strftime('%H:%M:%S')}Z",
            'dusk': f"{date_str}T{s['dusk'].strftime('%H:%M:%S')}Z",
        }
    except Exception as e:
        logging.warning(f"Sun times calculation failed: {e}")
        return None


def _extract_common_for_hierarchy(species_name: str) -> str:
    """
    Извлечь common name для поиска в иерархии.
    "Cardinalis cardinalis (Northern Cardinal)" -> "Northern Cardinal"
    "Northern Cardinal" -> "Northern Cardinal"
    """
    if not species_name or not isinstance(species_name, str):
        return species_name or ""
    s = species_name.strip()
    if len(s) > 512:
        s = s[:512]
    if not s.endswith(')'):
        return s
    open_idx = s.rfind('(')
    if open_idx <= 0:
        return s
    inner = s[open_idx + 1 : -1].strip()
    return inner if inner else s


def _extract_wiki_search_title(species_name: str) -> str:
    """
    Choose best-effort Wikipedia title.

    - "Corvus cornix (Hooded Crow)" -> "Hooded Crow"
    - "Bald Eagle (Adult, subadult)" -> "Bald Eagle"
    """
    if not species_name or not isinstance(species_name, str):
        return species_name or ""
    s = species_name.strip()
    key = s.lower().strip()
    if key in _wiki_title_overrides:
        return _wiki_title_overrides[key]
    m = re.match(r"^(.*?)\s*\(([^)]+)\)\s*$", s)
    if not m:
        return s
    left = (m.group(1) or "").strip()
    right = (m.group(2) or "").strip()
    # Scientific binomial (Genus species) on the left -> use right common name.
    if re.match(r"^[A-Z][a-z]+ [a-z][a-z-]+$", left):
        return right or left or s
    # Otherwise parentheses are usually morph/age/sex; use base species name.
    return left or right or s


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


def load_species_canonical_mapping():
    """
    Загрузить маппинг variant -> canonical из species_canonical_mapping.txt.
    Возвращает dict: variant_name -> canonical_name (Common).
    """
    path = os.path.join(os.path.dirname(__file__), "seed", "species_canonical_mapping.txt")
    result = {}
    if not os.path.isfile(path):
        return result
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "|" not in line:
                continue
            variant, canonical = line.split("|", 1)
            result[variant.strip()] = canonical.strip()
    return result


def normalize_species_to_canonical(name: str, mapping: dict | None = None) -> str:
    """
    Нормализовать имя вида в каноническое (Common name).
    mapping: variant -> canonical. Если None — загружается из seed.
    """
    mapping = mapping or load_species_canonical_mapping()
    return mapping.get(name, name)


_hierarchy_parent_map = None


def get_parent_name_for_species(species_name: str) -> str | None:
    """Родительская категория для вида по иерархии (Frigate/BirdNET/YOLO)."""
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

    children_map = {}
    for child, parent in species_dict.items():
        children_map.setdefault(parent, []).append(child)

    def build_tree_from_parent(parent):
        if parent not in children_map:
            return {}
        return {child: build_tree_from_parent(child) for child in children_map[parent]}

    root_nodes = set(species_dict.values()) - set(species_dict.keys())
    return {root: build_tree_from_parent(root) for root in root_nodes}


def get_wikipedia_image_and_description(title):
    """Fetch image and description from Wikipedia. Returns (None, None) on any error."""
    cache_key = (title or "").strip().lower()
    if cache_key in _wiki_meta_cache:
        return _wiki_meta_cache[cache_key]
    try:
        url = "https://en.wikipedia.org/w/api.php"
        params = {
            "action": "query",
            "prop": "pageimages|pageprops|extracts",
            "format": "json",
            "piprop": "thumbnail",
            "titles": title,
            "pithumbsize": 300,
            "redirects": 1,
            "exintro": 1,
        }
        headers = {'User-Agent': 'BirdLense-Hub/1.0 (Bird feeder monitoring app)'}
        response = requests.get(url, params=params, timeout=10, headers=headers)
        response.raise_for_status()
        if 'json' not in (response.headers.get('Content-Type') or '').lower():
            logging.warning("Wikipedia API non-JSON response for '%s' (content-type=%s)",
                            title, response.headers.get('Content-Type'))
            result = (None, None)
            _wiki_meta_cache[cache_key] = result
            return result
        data = response.json()
        pages_dict = (data.get("query") or {}).get("pages") or {}
        pages = list(pages_dict.values())
        if not pages:
            result = (None, None)
            _wiki_meta_cache[cache_key] = result
            return result
        page = pages[0]
        image_url = page.get("thumbnail", {}).get("source")
        description = re.sub(r'<[^>]*>', '', page.get("extract", "")).strip() or None
        result = (image_url, description)
        _wiki_meta_cache[cache_key] = result
        return result
    except requests.RequestException as e:
        logging.warning(f"Wikipedia API HTTP failed for '{title}': {e}")
        result = (None, None)
        _wiki_meta_cache[cache_key] = result
        return result
    except ValueError as e:
        logging.warning(f"Wikipedia API decode failed for '{title}': {e}")
        result = (None, None)
        _wiki_meta_cache[cache_key] = result
        return result
    except Exception as e:
        logging.warning(f"Wikipedia API failed for '{title}': {e}")
        result = (None, None)
        _wiki_meta_cache[cache_key] = result
        return result


def get_inaturalist_image_and_description(title):
    """
    Fallback metadata source via iNaturalist taxa API.
    Returns (image_url, description, source_url) or (None, None, None).
    """
    try:
        query = (title or "").strip()
        if not query:
            return None, None, None
        url = "https://api.inaturalist.org/v1/taxa"
        params = {
            "q": query,
            "per_page": 3,
            "locale": "en",
            "is_active": "true",
        }
        headers = {'User-Agent': 'BirdLense-Hub/1.0 (Bird feeder monitoring app)'}
        response = requests.get(url, params=params, timeout=10, headers=headers)
        response.raise_for_status()
        data = response.json() or {}
        results = data.get("results") or []
        if not results:
            return None, None, None
        top = results[0]
        image_url = ((top.get("default_photo") or {}).get("medium_url")
                     or (top.get("default_photo") or {}).get("square_url"))
        description = (top.get("wikipedia_summary")
                       or (top.get("taxon_schemes_count") and top.get("name"))
                       or None)
        if description and isinstance(description, str):
            description = description.strip() or None
        taxon_id = top.get("id")
        source_url = f"https://www.inaturalist.org/taxa/{taxon_id}" if taxon_id else None
        return image_url, description, source_url
    except Exception as e:
        logging.warning("iNaturalist API failed for '%s': %s", title, e)
        return None, None, None


def update_species_info_from_wiki(sp):
    """Update missing species data from Wikipedia. Returns True if updated.

    image_url from Wikipedia is a full URL (https://upload.wikimedia.org/...).
    Frontend must use resolveImageUrl() to handle both full URLs and relative paths.
    Prefer common name for lookup (Eurasian Jay) — Wikipedia often has image on common-name page.
    """
    if sp.image_url and sp.description:
        return False
    metadata_source = None
    metadata_source_url = None
    # Prefer canonical wiki title from taxon registry when available.
    taxon = getattr(sp, "taxon", None)
    search_title = (getattr(taxon, "wiki_title", None) or "").strip()
    if search_title:
        search_title = _extract_wiki_search_title(search_title)
    if not search_title:
        # Robust extraction for both scientific/common and morph variants.
        search_title = _extract_wiki_search_title(sp.name) or sp.name
    image_url, description = get_wikipedia_image_and_description(search_title)
    if image_url or description:
        metadata_source = 'wikipedia'
        metadata_source_url = f"https://en.wikipedia.org/wiki/{search_title.replace(' ', '_')}"

    # Fallback chain: scientific/common aliases for better wiki hit-rate.
    scientific = re.sub(r'\(.*\)', '', sp.name).strip()
    fallback_titles = []
    if search_title != sp.name:
        fallback_titles.append(sp.name)
    if scientific and scientific not in (search_title, sp.name):
        fallback_titles.append(scientific)
    # Common problematic crow aliases.
    if search_title.lower() == "hooded crow" and "Corvus cornix" not in fallback_titles:
        fallback_titles.append("Corvus cornix")
    if search_title.lower() == "corvus cornix" and "Hooded Crow" not in fallback_titles:
        fallback_titles.append("Hooded Crow")
    if "jacobin pigeon" in search_title.lower():
        fallback_titles.extend(["Columba livia domestica", "Rock Dove"])

    for alt in fallback_titles:
        if image_url and description:
            break
        img2, desc2 = get_wikipedia_image_and_description(alt)
        if img2 and not image_url:
            image_url = img2
            metadata_source = metadata_source or 'wikipedia'
            metadata_source_url = metadata_source_url or f"https://en.wikipedia.org/wiki/{alt.replace(' ', '_')}"
        if desc2 and not description:
            description = desc2
            metadata_source = metadata_source or 'wikipedia'
            metadata_source_url = metadata_source_url or f"https://en.wikipedia.org/wiki/{alt.replace(' ', '_')}"

    # Secondary source fallback: iNaturalist (photo + wikipedia_summary)
    if not image_url or not description:
        inat_titles = [search_title] + [t for t in fallback_titles if t != search_title]
        for alt in inat_titles:
            if image_url and description:
                break
            img3, desc3, src3 = get_inaturalist_image_and_description(alt)
            if img3 and not image_url:
                image_url = img3
                metadata_source = metadata_source or 'inaturalist'
                metadata_source_url = metadata_source_url or src3
            if desc3 and not description:
                description = desc3
                metadata_source = metadata_source or 'inaturalist'
                metadata_source_url = metadata_source_url or src3

    # Final deterministic description fallback for taxonomy buckets / rare pages.
    if not description:
        title = _extract_wiki_search_title(sp.name) or sp.name
        if "and allies" in (sp.name or "").lower():
            description = (
                f"{title} is a higher-level taxonomic bird group used in the BirdLense "
                "hierarchy for organizing related species."
            )
        elif "(" in (sp.name or "") and ")" in (sp.name or ""):
            base = (sp.name or "").split("(", 1)[0].strip() or title
            description = (
                f"{sp.name} is a morphology/age/sex variant entry for {base} in the "
                "BirdLense species taxonomy."
            )
        else:
            description = f"{title} is a bird taxon represented in the BirdLense registry."

    if not image_url:
        key = (sp.name or '').strip().lower()
        image_url = _manual_image_overrides.get(key) or image_url
    if image_url and not sp.image_url:
        sp.image_url = image_url
    if description and not sp.description:
        sp.description = description
    inferred_source, inferred_url = infer_metadata_source_fields(
        getattr(sp, 'name', None),
        image_url or getattr(sp, 'image_url', None),
        metadata_source_url or getattr(sp, 'metadata_source_url', None),
    )
    if (metadata_source or inferred_source) and not getattr(sp, 'metadata_source', None):
        sp.metadata_source = metadata_source or inferred_source
    if (metadata_source_url or inferred_url) and not getattr(sp, 'metadata_source_url', None):
        sp.metadata_source_url = metadata_source_url or inferred_url
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


def _get_telegram_api_base():
    """Base URL для Telegram Bot API. Прокси/альтернатива при троттлинге."""
    base = (app_config.get('notifications.telegram_api_base') or '').strip().rstrip('/')
    return base or 'https://api.telegram.org'


def _telegram_http_proxies():
    """Прокси для исходящих запросов к Telegram (SOCKS5h, HTTP). Пусто — без прокси."""
    url = (app_config.get('notifications.telegram_proxy_url') or '').strip()
    if not url:
        return None
    return {'http': url, 'https': url}


def _telegram_timeouts():
    """(timeout_text, timeout_media) — текст легче, медиа тяжелее. В РФ таймауты большие (блокировки)."""
    t = int(app_config.get('notifications.telegram_timeout') or 300)
    t = max(30, min(600, t))  # до 10 мин при блокировках
    return t // 2, t


def _telegram_request(method, url, timeout, retries=None, **kwargs):
    """Запрос к Telegram API с повторами при таймауте/сетевой ошибке."""
    retries = retries or int(app_config.get('notifications.telegram_retries') or 3)
    retries = max(1, min(5, retries))
    last_exc = None
    proxies = _telegram_http_proxies()
    if proxies and 'proxies' not in kwargs:
        kwargs = {**kwargs, 'proxies': proxies}
    for attempt in range(retries):
        try:
            r = requests.request(method, url, timeout=timeout, **kwargs)
            return r
        except (requests.Timeout, requests.ConnectionError, OSError) as e:
            last_exc = e
            if attempt < retries - 1:
                delay = 2 ** attempt
                logging.warning(
                    "Telegram attempt %d/%d failed (%s), retry in %ds",
                    attempt + 1, retries, type(e).__name__, delay)
                time.sleep(delay)
    raise last_exc


def _payload_for_telegram_multipart(payload):
    """Для multipart/form-data Telegram ожидает булевы как строки 'true'/'false'."""
    out = {}
    for k, v in payload.items():
        if isinstance(v, bool):
            out[k] = 'true' if v else 'false'
        elif isinstance(v, dict):
            out[k] = json.dumps(v)
        else:
            out[k] = v
    return out


def _compress_image_for_telegram(image_bytes):
    """Сжать и/или уменьшить JPEG для Telegram. В уведомлениях уже шлём кропы (bounding box) с процессора."""
    max_side = int(app_config.get('notifications.telegram_max_side_px') or 0)
    limit_kb = int(app_config.get('notifications.compress_photo_over_kb') or 0)
    if max_side <= 0 and (limit_kb <= 0 or len(image_bytes) <= limit_kb * 1024):
        return image_bytes
    try:
        from PIL import Image
        import io
        img = Image.open(io.BytesIO(image_bytes))
        if img.mode in ('RGBA', 'P'):
            img = img.convert('RGB')
        w, h = img.size
        if max_side > 0 and max(w, h) > max_side:
            ratio = max_side / max(w, h)
            new_size = (int(w * ratio), int(h * ratio))
            img = img.resize(new_size, Image.Resampling.LANCZOS)
            logging.debug("Telegram: resized to %s (max_side=%s)", new_size, max_side)
        buf = io.BytesIO()
        img.save(buf, 'JPEG', quality=85, optimize=True)
        out = buf.getvalue()
        if limit_kb > 0 and len(out) > limit_kb * 1024:
            buf2 = io.BytesIO()
            img.save(buf2, 'JPEG', quality=78, optimize=True)
            out = buf2.getvalue()
        if len(out) < len(image_bytes):
            logging.debug("Telegram: %d -> %d bytes", len(image_bytes), len(out))
        return out
    except Exception as e:
        logging.debug("Telegram image process skip: %s", e)
    return image_bytes


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
    base = _get_telegram_api_base()
    timeout_text, _ = _telegram_timeouts()
    url = f"{base}/bot{token}/sendMessage"
    return _telegram_request('POST', url, timeout=timeout_text, json=payload)


def notify_telegram_test(message="Test notification from BirdLense"):
    """Отправить тестовое сообщение в Telegram. Возвращает (success, error_message)."""
    if not app_config.get('general.enable_notifications'):
        return False, 'Notifications disabled'
    token = (app_config.get('notifications.telegram_bot_token') or '').strip()
    chat_id = (app_config.get('notifications.telegram_chat_id') or '').strip()
    if not token or not chat_id:
        return False, 'Telegram bot token or chat_id not configured'
    text = f"🚀 {message}"
    try:
        r = _telegram_send_message(token, chat_id, text, link=None)
        if r.ok:
            return True, None
        err = r.json() if r.text else {}
        desc = err.get('description', r.text[:200] if r.text else str(r.status_code))
        return False, desc
    except requests.RequestException as e:
        return False, str(e)


def notify_app_startup(app=None):
    """Send 'App is UP!' on startup. Skips when TESTING (pytest creates app 45×).
    Skips when startup is due to 'restart processor' from UI (marker file .startup_notify_skip
    in data_dir with recent mtime). Skips when already sent in this container run (marker in
    /tmp — survives worker restarts but not container restart) to avoid TG spam.
    Marker is created BEFORE notify() so that if we crash during send, we don't send again."""
    import os as _os
    if _os.environ.get('FLASK_TESTING') or (app and app.config.get('TESTING')):
        return
    sent_marker = '/tmp/.birdlense_startup_notify_sent'  # not in volume → one send per container
    try:
        if os.path.exists(sent_marker):
            logging.info(
                "notify_app_startup: skip (marker exists, pid=%s)",
                os.getpid(),
            )
            return  # already sent this container run (e.g. after gunicorn worker restart)
        skip_marker = os.path.join(_data_dir(), '.startup_notify_skip')
        if os.path.exists(skip_marker):
            age_sec = time.time() - os.path.getmtime(skip_marker)
            if age_sec <= 120:
                try:
                    os.remove(skip_marker)
                except OSError:
                    pass
                logging.info("notify_app_startup: skip (restart processor, pid=%s)", os.getpid())
                return  # restart was from UI "restart processor", skip TG
            try:
                os.remove(skip_marker)
            except OSError:
                pass
        # Create marker BEFORE notify so crash during send doesn't cause resend on next start
        try:
            open(sent_marker, 'a').close()
        except OSError:
            pass
        logging.info("notify_app_startup: sending (pid=%s)", os.getpid())
        # Web Push / DB (PushSubscription) need Flask application context
        if app is not None:
            with app.app_context():
                notify("App is UP!", tags="rocket", timestamp=datetime.now(timezone.utc))
        else:
            notify("App is UP!", tags="rocket", timestamp=datetime.now(timezone.utc))
    except Exception as e:
        logging.warning("notify_app_startup failed: %s", e)


def notify(message, link="live", tags=None, image_path=None, image_bytes=None, timestamp=None):
    """Send notification via Telegram and/or Web Push. Requires token+chat_id or Web Push subscribers.

    image_path: path to image file (must pass _is_safe_image_path when used).
    image_bytes: raw JPEG bytes (alternative to image_path, preferred when processor sends base64).
    timestamp: datetime or Unix int for dynamic time <t:unix:R> (Bot API 9.5).
    """
    if not app_config.get('general.enable_notifications'):
        return
    # Web Push (параллельно с Telegram)
    try:
        from services.web_push_service import send_web_push
        icon = "chipmunk" if tags and any(s in (tags or "").lower() for s in (
            "squirrel", "chipmunk", "mouse", "мышь", "белка")) else "bird"
        send_web_push(message, link=link, tag=icon)
    except Exception as e:
        logging.warning("Web Push notify error: %s", e)
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
        # Prefer image_bytes (from processor base64) — не зависит от общего файлового пространства
        image_to_send = None
        if send_photo and image_bytes and isinstance(image_bytes, bytes) and len(image_bytes) > 0:
            image_to_send = image_bytes
        elif send_photo and image_path:
            safe_img_path = _safe_image_path_or_none(image_path)
            if safe_img_path:
                try:
                    with open(safe_img_path, 'rb') as f:
                        image_to_send = f.read()
                except OSError as e:
                    logging.warning("Cannot read image for Telegram: %s", e)
                    image_to_send = None
        if image_to_send:
            image_to_send = _compress_image_for_telegram(image_to_send)
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

            caption = text
            if link_url and app_config.get('notifications.link_preview_large', False):
                caption = f"{text}\n\n{link_url}"
            payload = {
                'chat_id': chat_id,
                'caption': caption,
                'parse_mode': 'HTML',
                'disable_notification': app_config.get(
                    'notifications.disable_notification', False),
                'protect_content': protect,
            }
            if link_url and app_config.get('notifications.link_preview_large', False):
                payload['link_preview_options'] = {'is_disabled': False, 'prefer_large_media': True}
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

            base = _get_telegram_api_base()
            _, timeout_media = _telegram_timeouts()
            logging.info(
                "Telegram: sending photo (%d bytes), timeout=%ds",
                len(image_to_send),
                timeout_media,
            )
            photo_failed = False
            r = None
            try:
                data = _payload_for_telegram_multipart(payload)
                if view_stars > 0:
                    data['star_count'] = view_stars
                    data['media'] = json.dumps([
                        {'type': 'photo', 'media': 'attach://photo'}
                    ])
                    r = _telegram_request(
                        'POST', f"{base}/bot{token}/sendPaidMedia",
                        timeout=timeout_media,
                        data=data,
                        files={'photo': ('photo.jpg', image_to_send, 'image/jpeg')},
                    )
                else:
                    r = _telegram_request(
                        'POST', f"{base}/bot{token}/sendPhoto",
                        timeout=timeout_media,
                        data=data,
                        files={'photo': ('photo.jpg', image_to_send, 'image/jpeg')},
                    )
            except (requests.Timeout, requests.ConnectionError, OSError) as e:
                logging.warning(
                    "Telegram photo failed (timeout/network): %s — fallback to text",
                    e,
                )
                photo_failed = True
            if r is not None and not r.ok:
                logging.warning(
                    "Telegram sendPhoto HTTP %s: %s",
                    r.status_code,
                    (r.text or "")[:500],
                )
                photo_failed = True
            if photo_failed:
                try:
                    r = _telegram_send_message(
                        token, chat_id, text, link=link_url,
                        button_emoji=button_emoji, button_style='primary',
                        button_tags=button_tags)
                except requests.RequestException as fallback_e:
                    logging.warning("Telegram text fallback also failed: %s", fallback_e)
                    r = None
            if r is None:
                return
            safe_rm = _safe_image_path_or_none(image_path)
            if safe_rm and os.path.isfile(safe_rm):
                try:
                    os.remove(safe_rm)
                except OSError:
                    pass
        else:
            r = _telegram_send_message(
                token, chat_id, text, link=link_url,
                button_emoji=button_emoji, button_style='primary',
                button_tags=button_tags)
        if r is not None and not r.ok:
            logging.warning(
                "Telegram notify failed: %s %s",
                r.status_code,
                (getattr(r, "text", "") or "")[:300],
            )
    except requests.RequestException as e:
        logging.warning("Telegram notify error: %s", e)


def filter_feeder_species(species_names):
    """Фильтр по семействам из processor.included_bird_families."""
    included_families = app_config.get('processor.included_bird_families', [])
    if not included_families:
        return species_names

    all_species = Species.query.all()
    children_by_parent = {}
    name_to_species = {}
    for species in all_species:
        children_by_parent.setdefault(
            species.parent_id, set()).add(species.name)
        name_to_species[species.name] = species

    birds_category = name_to_species.get('Birds')
    if not birds_category:
        return species_names

    included_species = set()

    def add_descendants(parent_name):
        species = name_to_species.get(parent_name)
        if not species:
            return
        children = children_by_parent.get(species.id, set())
        included_species.update(children)
        for child in children:
            add_descendants(child)

    for family in included_families:
        if family in children_by_parent.get(birds_category.id, set()):
            add_descendants(family)
            included_species.add(family)

    return [name for name in species_names if name in included_species]
