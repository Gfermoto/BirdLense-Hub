import hmac
import json
import logging
import os
import secrets
from datetime import datetime, timezone

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


from data_paths import (
    _data_dir,
    _is_safe_image_path,
    _path_is_under_data_dir,
    data_dir,
    full_path_for_video,
    read_safe_image_bytes,
    recordings_dir,
    remove_safe_image_file,
)
from timeline_payloads import (
    format_unlinked_video_for_timeline,
    format_visit_for_timeline,
    get_primary_video_for_visit,
    get_primary_video_for_visit_in_window,
)
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
from observer_time import (
    fetch_sun_times,
    get_observer_timezone,
    get_observer_timezone_name,
    observer_local_day_bounds,
    observer_local_hour,
    observer_local_range,
)
