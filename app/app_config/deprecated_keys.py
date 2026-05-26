"""Deprecated dot-path keys still allowed in user_config (SOTA-03 audit)."""

DEPRECATED_USER_CONFIG_KEYS: tuple[str, ...] = (
    "gallery.enabled",
    "gallery.min_confidence",
    "gallery.only_manually_corrected",
    "gallery.upload_url",
    "general.heimdall_url",
    "notifications.enabled",
    "notifications.excluded_species",
    "notifications.rate_limit_per_minute",
    "processor.detection_device",
    "processor.detection_frame_interval",
    "weather.ha_token",
    "weather.ha_url",
)
