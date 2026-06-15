"""Single source for processor defaults — must match app/app_config/default_config.yaml.

Runtime code must use these when app_config omits a key; never invent orphan literals
(0.22, 0.30, 180, etc.). CI: test_processor_config_defaults.py.
"""

from __future__ import annotations

# processor.*
PIPELINE_MODE = "linear"
MIN_CONFIDENCE_TO_PROCESS = 0.08
MIN_CONFIDENCE_TO_NOTIFY = 0.46
MIN_CONFIDENCE_BINARY = 0.08
MIN_CONFIDENCE_BINARY_BIRD = 0.06
CLASSIFIER_BEST_GUESS_MIN_CONFIDENCE = 0.10
BIRDER_EU_MIN_CONFIDENCE = 0.15
AUTO_UNSTICK_NO_TRACK_FRAMES = 10
AUTO_UNSTICK_MIN_CONFIDENCE_BINARY = 0.04
AUTO_UNSTICK_MIN_CONFIDENCE_BINARY_BIRD = 0.025
AUTO_UNSTICK_MIN_BOX_SIZE_PX = 14
AUTO_UNSTICK_MIN_CENTER_DIST = 0.01
MIN_BOX_SIZE_PX = 14
MIN_CENTER_DIST = 0.01
MIN_TRACK_DURATION = 0.6
TRACKER_REMEMBER_SECONDS = 1.6
ULTRA_WEAK_BOX_SALVAGE_ENABLED = False
TRACK_TO_PREDICT_FALLBACK_ENABLED = True
TRACKER_ADAPTIVE_MIN_BUFFER = 6
TRACKER_ADAPTIVE_MAX_BUFFER = 16
TRACKER_LOW_FPS_THRESHOLD = 10.0
OPENVO_BINARY_TRACK_ULTRALYTICS_CONF = 0.06

# detection.*
MIN_CONFIDENCE_TO_STORE = 0.08
ABSORB_GENERIC_BIRD_MIN_CLASSIFIER_CONFIDENCE = 0.24
BBOX_IOU_GATE_ACTION = "reject"
YOLO_BLIND_MIN_FRAMES = 180
YOLO_BLIND_MIN_FRIGATE_ONLY_FRAMES = 120


def config_float(app_config, key: str, default: float) -> float:
    raw = app_config.get(key)
    if raw is None:
        return float(default)
    try:
        return float(raw)
    except (TypeError, ValueError):
        return float(default)


def config_int(app_config, key: str, default: int) -> int:
    raw = app_config.get(key)
    if raw is None:
        return int(default)
    try:
        return int(raw)
    except (TypeError, ValueError):
        return int(default)
