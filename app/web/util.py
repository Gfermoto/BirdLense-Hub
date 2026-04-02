import ipaddress
import json
import logging
import os
import secrets
import threading
import time
from datetime import timedelta, datetime, timezone
from functools import lru_cache
from urllib.parse import urlparse

# Re-exports for backward compatibility — do not remove
from auth import (
    _get_session_role,
    _has_contributor_password,
    settings_check_access,
    contributor_or_admin_access,
)
from notifications import (
    notify,
    notify_app_startup,
    notify_telegram_test,
    _telegram_http_proxies,
    _telegram_request,
    _telegram_send_message,
    _telegram_button_open_live,
    _get_button_custom_emoji_id,
    _get_telegram_api_base,
    _telegram_timeouts,
    _payload_for_telegram_multipart,
    _compress_image_for_telegram,
)
from weather_service import (
    _normalize_coord,
    WeatherFetcher,
    HAWeatherFetcher,
    _create_weather_fetcher,
    weather_fetcher,
    fetch_weather,
)

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

    trusted_proxy = (os.environ.get('TRUSTED_PROXY') or '').strip().lower() in (
        '1', 'true', 'yes',
    )
    if trusted_proxy:
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
    """Deterministically pick the earliest video for a SpeciesVisit."""
    return get_primary_video_for_visit_in_window(visit)


def get_primary_video_for_visit_in_window(
    visit,
    window_start: datetime | None = None,
    window_end: datetime | None = None,
) -> object | None:
    """Pick the earliest visit video, optionally constrained to a time window."""
    if not visit or not getattr(visit, 'video_species', None):
        return None
    vs_list = [
        vs for vs in visit.video_species
        if getattr(vs, 'video', None) and getattr(vs.video, 'start_time', None)
    ]
    if window_start is not None or window_end is not None:
        filtered_vs = []
        for vs in vs_list:
            video_start = ensure_utc(vs.video.start_time).replace(tzinfo=None)
            video_end = ensure_utc(vs.video.end_time).replace(tzinfo=None)
            if window_start is not None and video_end <= window_start:
                continue
            if window_end is not None and video_start >= window_end:
                continue
            filtered_vs.append(vs)
        vs_list = filtered_vs
    if not vs_list:
        return None
    primary = min(
        vs_list,
        key=lambda vs: (
            ensure_utc(vs.video.start_time),
            getattr(vs.video, 'id', 0) or 0,
        ),
    )
    return primary.video


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
    if _host_is_inaturalist(src_host) or _host_is_inaturalist(img_host):
        return 'inaturalist', (src or img)
    if _url_suggests_inaturalist_asset(img) or _url_suggests_inaturalist_asset(src):
        return 'inaturalist', None
    return None, source_url


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


@lru_cache(maxsize=32)
def _observer_timezone_name_cached(lat: str, lon: str) -> str:
    import zoneinfo
    from timezonefinder import TimezoneFinder

    try:
        lat_f = float(str(lat).replace(',', '.'))
        lon_f = float(str(lon).replace(',', '.'))
        tf = TimezoneFinder()
        tz_name = tf.timezone_at(lat=lat_f, lng=lon_f) or 'UTC'
        zoneinfo.ZoneInfo(tz_name)
        return tz_name
    except Exception:
        return 'UTC'


def get_observer_timezone_name() -> str:
    lat = _normalize_coord(app_config.get('secrets.latitude'))
    lon = _normalize_coord(app_config.get('secrets.longitude'))
    if not lat or not lon:
        return 'UTC'
    return _observer_timezone_name_cached(str(lat), str(lon))


def get_observer_timezone():
    import zoneinfo

    try:
        return zoneinfo.ZoneInfo(get_observer_timezone_name())
    except Exception:
        return timezone.utc


def observer_local_day_bounds(date_str: str) -> tuple[datetime, datetime]:
    local_day = datetime.strptime(date_str, '%Y-%m-%d')
    tz = get_observer_timezone()
    start_local = local_day.replace(tzinfo=tz)
    end_local = start_local + timedelta(days=1) - timedelta(microseconds=1)
    return (
        start_local.astimezone(timezone.utc).replace(tzinfo=None),
        end_local.astimezone(timezone.utc).replace(tzinfo=None),
    )


def observer_local_range(
    date_str: str,
    *,
    time_of_day: str = 'all',
    hour: int | None = None,
) -> tuple[datetime, datetime]:
    local_day = datetime.strptime(date_str, '%Y-%m-%d')
    tz = get_observer_timezone()
    start_local = local_day.replace(tzinfo=tz)

    if hour is not None:
        if hour < 0 or hour > 23:
            raise ValueError('hour must be in range 0..23')
        range_start = start_local.replace(
            hour=hour,
            minute=0,
            second=0,
            microsecond=0,
        )
        range_end = start_local.replace(
            hour=hour,
            minute=59,
            second=59,
            microsecond=999999,
        )
    elif time_of_day == 'all':
        range_start = start_local.replace(hour=0, minute=0, second=0, microsecond=0)
        range_end = start_local.replace(
            hour=23, minute=59, second=59, microsecond=999999,
        )
    else:
        ranges = {
            'night': (0, 6),
            'morning': (6, 10),
            'day': (10, 14),
            'afternoon': (14, 18),
            'evening': (18, 22),
        }
        if time_of_day not in ranges:
            raise ValueError('invalid time_of_day')
        start_hour, end_hour = ranges[time_of_day]
        range_start = start_local.replace(
            hour=start_hour,
            minute=0,
            second=0,
            microsecond=0,
        )
        range_end = start_local.replace(
            hour=end_hour,
            minute=0,
            second=0,
            microsecond=0,
        ) - timedelta(microseconds=1)

    return (
        range_start.astimezone(timezone.utc).replace(tzinfo=None),
        range_end.astimezone(timezone.utc).replace(tzinfo=None),
    )


def observer_local_hour(dt: datetime | None) -> int:
    if dt is None:
        return 0
    local = ensure_utc(dt).astimezone(get_observer_timezone())
    return int(local.hour)


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
            "iconic_taxa": "Aves",
        }
        headers = {'User-Agent': 'BirdLense-Hub/1.0 (Bird feeder monitoring app)'}
        response = requests.get(url, params=params, timeout=10, headers=headers)
        response.raise_for_status()
        data = response.json() or {}
        results = data.get("results") or []
        if not results:
            return None, None, None
        top = next(
            (row for row in results if (row.get("iconic_taxon_name") or "") == "Aves"),
            None,
        )
        if not top:
            return None, None, None
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
