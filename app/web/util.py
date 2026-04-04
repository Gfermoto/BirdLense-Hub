"""Backward-compatible facade: auth, paths, timeline, metadata, time (#222)."""

# Re-exports — do not remove
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
)  # noqa: F401
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
)  # noqa: F401
from weather_service import (
    WeatherFetcher,
    HAWeatherFetcher,
    _create_weather_fetcher,
    weather_fetcher,
    fetch_weather,
)  # noqa: F401
from app_config.app_config import app_config  # noqa: F401
from metrics_auth import metrics_bearer_denied  # noqa: F401
from time_util import ensure_utc, parse_utc_timestamp  # noqa: F401

# Вид «Bird» / «bird» — без вида
GENERIC_BIRD_SPECIES = 'Bird'

from data_paths import (  # noqa: E402, F401
    _data_dir,
    _is_safe_image_path,
    _path_is_under_data_dir,
    data_dir,
    full_path_for_video,
    read_safe_image_bytes,
    recordings_dir,
    remove_safe_image_file,
)
from timeline_payloads import (  # noqa: E402, F401
    format_unlinked_video_for_timeline,
    format_visit_for_timeline,
    get_primary_video_for_visit,
    get_primary_video_for_visit_in_window,
)
from species_metadata import (  # noqa: E402, F401
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
from observer_time import (  # noqa: E402, F401
    fetch_sun_times,
    get_observer_timezone,
    get_observer_timezone_name,
    observer_local_day_bounds,
    observer_local_hour,
    observer_local_range,
)
