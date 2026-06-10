"""Deprecated dot-path keys still allowed in user_config (SOTA-03 + Refactor-0.4 audit)."""

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
    "processor.camera_overrides",
    "processor.motion_verified_detection_enabled",
    "processor.background_subtraction_enabled",
    "processor.static_object_suppression_enabled",
    "processor.static_square_hard_reject_max_conf",
    "processor.motion_global_max_mean_absdiff",
    "detection.camera_overrides",
    "detection.frigate_standalone_when_no_yolo",
    "weather.ha_token",
    "weather.ha_url",
)

# processor.pipeline_mode value "legacy" is deprecated (linear is the only supported path).
DEPRECATED_PIPELINE_MODE_VALUE = "legacy"
