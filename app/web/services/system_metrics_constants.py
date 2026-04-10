"""Константы sampler/history и TTL кешей: system metrics, visitors (#265)."""
from __future__ import annotations

import os


def env_bounded_int(name: str, default: int, *, min_v: int, max_v: int) -> int:
    """Прочитать int из env, ограничить диапазоном; при ошибке — default."""
    raw = os.environ.get(name, '').strip()
    if not raw:
        return default
    try:
        v = int(raw)
    except ValueError:
        return default
    return max(min_v, min(max_v, v))


SYSTEM_METRICS_SAMPLE_INTERVAL_SEC = env_bounded_int(
    'BIRDLENSE_SYSTEM_METRICS_INTERVAL_SEC', 30, min_v=10, max_v=600,
)
SYSTEM_METRICS_RETENTION_HOURS = env_bounded_int(
    'BIRDLENSE_SYSTEM_METRICS_RETENTION_HOURS', 72, min_v=6, max_v=720,
)
SYSTEM_METRICS_HISTORY_MAX_HOURS = 168
SYSTEM_METRICS_HISTORY_MAX_POINTS_CAP = 2000
SYSTEM_METRICS_HISTORY_DEFAULT_MAX_POINTS = 500

_CACHE_SYSTEM_METRICS_SEC = 2.5
_CACHE_SYSTEM_VISITORS_SEC = 25
_CACHE_SYSTEM_METRICS_HIST_SEC = 12
_CACHE_STORAGE_STATS_SEC = 45
_CACHE_SYSTEM_ACTIVITY_SEC = 50
