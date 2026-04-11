"""Backward-compatible facade (#222)."""

from compat_reexports import *  # noqa: F401, F403

from app_config.app_config import app_config  # noqa: F401
from metrics_auth import metrics_bearer_denied  # noqa: F401
from species_constants import GENERIC_BIRD_SPECIES  # noqa: F401
from time_util import ensure_utc, parse_timeline_iso, parse_utc_timestamp  # noqa: F401

from data_paths import (  # noqa: E402, F401
    _data_dir,
    _is_safe_image_path,
    _path_is_under_data_dir,
    data_dir,
    full_path_for_video,
    read_safe_image_bytes,
    recordings_dir,
    remove_safe_image_file,
    resolve_recording_video_file,
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
    bust_feeder_species_filter_cache,
    build_hierarchy_tree,
    filter_feeder_species,
    get_inaturalist_image_and_description,
    get_parent_name_for_species,
    infer_metadata_source_fields,
    load_species_canonical_mapping,
    normalize_species_to_canonical,
    refresh_species_metadata_from_sources,
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
