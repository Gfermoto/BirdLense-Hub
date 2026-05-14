"""In-process HTTP request metrics for Prometheus exposition."""

from __future__ import annotations

from collections import defaultdict
import threading

_LOCK = threading.Lock()
_BUCKETS_MS = (50, 100, 250, 500, 1000, 2500, 5000)

_REQUEST_TOTAL: dict[tuple[str, str, str], int] = defaultdict(int)
_REQUEST_DURATION_SUM_MS: dict[tuple[str, str], float] = defaultdict(float)
_REQUEST_DURATION_COUNT: dict[tuple[str, str], int] = defaultdict(int)
_REQUEST_DURATION_BUCKETS: dict[tuple[str, str], dict[float, int]] = defaultdict(lambda: defaultdict(int))


def observe_http_request(*, method: str, route: str, status_code: int, duration_ms: float) -> None:
    m = str(method or "UNKNOWN").strip().upper() or "UNKNOWN"
    r = str(route or "unknown").strip() or "unknown"
    status = str(int(status_code) if isinstance(status_code, int) else status_code or "0")
    try:
        dur = max(0.0, float(duration_ms))
    except (TypeError, ValueError):
        dur = 0.0
    key = (m, r)
    with _LOCK:
        _REQUEST_TOTAL[(m, r, status)] += 1
        _REQUEST_DURATION_SUM_MS[key] += dur
        _REQUEST_DURATION_COUNT[key] += 1
        placed = False
        for b in _BUCKETS_MS:
            if dur <= float(b):
                _REQUEST_DURATION_BUCKETS[key][float(b)] += 1
                placed = True
                break
        if not placed:
            _REQUEST_DURATION_BUCKETS[key][float("inf")] += 1


def prometheus_http_request_metrics_lines() -> list[str]:
    lines: list[str] = [
        "# HELP birdlense_http_requests_total HTTP requests grouped by method/route/status",
        "# TYPE birdlense_http_requests_total counter",
    ]
    with _LOCK:
        for (method, route, status), count in sorted(_REQUEST_TOTAL.items()):
            lines.append(
                f'birdlense_http_requests_total{{method="{method}",route="{route}",status="{status}"}} {count}'
            )
        lines.extend(
            [
                "# HELP birdlense_http_request_duration_ms Request duration histogram in milliseconds",
                "# TYPE birdlense_http_request_duration_ms histogram",
            ]
        )
        for (method, route), bucket_counts in sorted(_REQUEST_DURATION_BUCKETS.items()):
            cumulative = 0
            for le in [*map(float, _BUCKETS_MS), float("inf")]:
                cumulative += int(bucket_counts.get(le, 0))
                le_tag = "+Inf" if le == float("inf") else str(int(le))
                lines.append(
                    f'birdlense_http_request_duration_ms_bucket{{method="{method}",route="{route}",le="{le_tag}"}} {cumulative}'
                )
            lines.append(
                f'birdlense_http_request_duration_ms_count{{method="{method}",route="{route}"}} '
                f'{int(_REQUEST_DURATION_COUNT.get((method, route), 0))}'
            )
            lines.append(
                f'birdlense_http_request_duration_ms_sum{{method="{method}",route="{route}"}} '
                f'{float(_REQUEST_DURATION_SUM_MS.get((method, route), 0.0))}'
            )
    return lines
