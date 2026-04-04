import hmac
import json
import logging
import os
import secrets
from datetime import timedelta, datetime, timezone
from functools import lru_cache

# Re-exports for backward compatibility — do not remove
from auth import (
    VERIFY_PASSWORD_LIMIT,
    VERIFY_PASSWORD_WINDOW,
    _check_verify_password_rate_limit,
    _clear_verify_password_attempts,
    _get_session_role,
    _has_contributor_password,
    _record_verify_password_failure,
    _verify_password_attempts,
    _verify_password_lock,
    client_ip_for_rate_limit,
    contributor_or_admin_access,
    settings_check_access,
    verify_password_retry_after_seconds,
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
from app_config.app_config import app_config

def metrics_bearer_denied(*, prometheus: bool = False):
    """If ``BIRDLENSE_METRICS_TOKEN`` is set, require ``Authorization: Bearer <token>``.

    Returns a Flask response tuple or Response to return from the view, or ``None`` if the
    request may proceed (token unset or bearer matches).
    """
    from flask import request, Response, jsonify

    expected = (os.environ.get('BIRDLENSE_METRICS_TOKEN') or '').strip()
    if not expected:
        return None
    auth = (request.headers.get('Authorization') or '').strip()
    scheme, _, credentials = auth.partition(' ')
    got = credentials.strip() if scheme.lower() == 'bearer' else ''
    if got and hmac.compare_digest(got, expected):
        return None
    if prometheus:
        return Response('# Unauthorized\n', status=401, mimetype='text/plain; charset=utf-8')
    return jsonify({'error': 'Unauthorized'}), 401


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


def _path_is_under_data_dir(base: str, full: str) -> bool:
    """Проверка вложенности без обхода через префикс-соседей (например data_evil при base=data)."""
    try:
        return os.path.commonpath([base, full]) == base
    except ValueError:
        return False


def _is_safe_image_path(path: str) -> bool:
    """Путь под DATA_DIR, файл существует. Защита от path traversal."""
    if not path or not isinstance(path, str) or path != os.path.normpath(path):
        return False
    try:
        base = os.path.realpath(_data_dir())
        full = os.path.realpath(path)
    except (OSError, ValueError):
        return False
    if not _path_is_under_data_dir(base, full):
        return False
    # SafeAccessCheck: startswith в отдельном if (не внутри not (or …)) — иначе CodeQL не видит барьер.
    if full != base and not full.startswith(base + os.sep):
        return False
    try:
        return os.path.isfile(full)  # lgtm[py/path-injection] realpath+commonpath+startswith(base+sep)
    except OSError:
        return False


def read_safe_image_bytes(path: str | None) -> tuple[bytes | None, str | None]:
    """Прочитать файл только под DATA_DIR. (bytes, None) или (None, причина).

    Проверки realpath + commonpath + ``full.startswith(base + os.sep)`` и обращение к ФС —
    в одной функции (требование модели CodeQL py/path-injection).
    """
    if not path or not isinstance(path, str) or path != os.path.normpath(path):
        return None, 'unsafe_path'
    try:
        base = os.path.realpath(_data_dir())
        full = os.path.realpath(path)
    except (OSError, ValueError):
        return None, 'unsafe_path'
    if not _path_is_under_data_dir(base, full):
        return None, 'unsafe_path'
    if full != base and not full.startswith(base + os.sep):
        return None, 'unsafe_path'
    try:
        if not os.path.isfile(full):  # lgtm[py/path-injection] validated under DATA_DIR
            return None, 'unsafe_path'
    except OSError:
        return None, 'unsafe_path'
    try:
        with open(full, 'rb') as f:  # lgtm[py/path-injection] validated under DATA_DIR
            return f.read(), None
    except OSError as e:
        logging.warning('Cannot read safe image: %s', e)
        return None, 'read_failed'


def remove_safe_image_file(path: str | None) -> None:
    """Удалить файл только если он под DATA_DIR (те же проверки, что для чтения)."""
    if not path or not isinstance(path, str) or path != os.path.normpath(path):
        return
    try:
        base = os.path.realpath(_data_dir())
        full = os.path.realpath(path)
    except (OSError, ValueError):
        return
    if not _path_is_under_data_dir(base, full):
        return
    if full != base and not full.startswith(base + os.sep):
        return
    try:
        if not os.path.isfile(full):  # lgtm[py/path-injection] validated under DATA_DIR
            return
    except OSError:
        return
    try:
        os.remove(full)  # lgtm[py/path-injection] validated under DATA_DIR
    except OSError:
        pass


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
        'timeline_kind': 'visit',
    }


def format_unlinked_video_for_timeline(video, *, fallback_species) -> dict:
    """Ролик за интервал без привязки к SpeciesVisit — тот же контракт, что у визита в /timeline."""
    v0 = ensure_utc(video.start_time)
    v1 = ensure_utc(video.end_time)
    video_duration_seconds = max(0, round((v1 - v0).total_seconds()))
    detections = []
    total_recording_seconds = 0.0
    vss = sorted(video.video_species, key=lambda x: x.created_at, reverse=True)
    for vs in vss:
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
    if vss:
        sp = vss[0].species
        species_block = {
            'id': sp.id,
            'name': sp.name,
            'image_url': sp.image_url,
            'parent_id': sp.parent_id,
        }
    elif fallback_species is not None:
        species_block = {
            'id': fallback_species.id,
            'name': fallback_species.name,
            'image_url': fallback_species.image_url,
            'parent_id': fallback_species.parent_id,
        }
    else:
        species_block = {
            'id': 0,
            'name': GENERIC_BIRD_SPECIES,
            'image_url': None,
            'parent_id': None,
        }
    if not detections:
        detections.append({
            'video_id': video.id,
            'start_time': v0.astimezone(timezone.utc).isoformat(),
            'end_time': v1.astimezone(timezone.utc).isoformat(),
            'confidence': 0.0,
            'source': 'video',
        })
    return {
        'id': -(video.id),
        'start_time': v0.isoformat(),
        'end_time': v1.isoformat(),
        'max_simultaneous': 1,
        'total_recording_seconds': round(total_recording_seconds) if total_recording_seconds else video_duration_seconds,
        'video_duration_seconds': video_duration_seconds,
        'weather': {
            'temp': video.weather_temp,
            'clouds': video.weather_clouds,
        },
        'species': species_block,
        'detections': detections,
        'timeline_kind': 'unlinked_video',
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


from species_metadata import (
    _extract_common_for_hierarchy,
    _extract_wiki_search_title,
    _host_is_inaturalist,
    _host_is_inaturalist_open_data_asset,
    _host_is_wikipedia_family,
    _url_hostname_lower,
    build_hierarchy_tree,
    filter_feeder_species,
    get_inaturalist_image_and_description,
    get_parent_name_for_species,
    infer_metadata_source_fields,
    load_species_canonical_mapping,
    normalize_species_to_canonical,
    update_species_info_from_wiki,
)
