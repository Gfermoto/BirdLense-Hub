#!/usr/bin/env python3
"""Runtime performance gate: API burst + metrics scrape + short soak."""

from __future__ import annotations

import argparse
import json
import math
import os
import statistics
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


@dataclass
class ReqResult:
    """Single HTTP request measurement."""

    ok: bool
    status_code: int
    latency_ms: float
    path: str
    error: str = ''


def _auth_headers() -> dict[str, str]:
    key = (os.environ.get('BIRDLENSE_UI_API_KEY') or '').strip()
    token = (os.environ.get('MCP_TOKEN') or '').strip()
    if key:
        return {'X-Birdlense-Api-Key': key}
    if token:
        return {'Authorization': f'Bearer {token}'}
    return {}


def _request(
    base_url: str,
    path: str,
    headers: dict[str, str],
    timeout_sec: float,
) -> ReqResult:
    started = time.perf_counter()
    req = Request(f'{base_url.rstrip("/")}{path}', headers=headers, method='GET')
    try:
        with urlopen(req, timeout=timeout_sec) as resp:
            _ = resp.read()
            latency_ms = (time.perf_counter() - started) * 1000.0
            return ReqResult(
                ok=(200 <= resp.status < 300),
                status_code=int(resp.status),
                latency_ms=latency_ms,
                path=path,
            )
    except HTTPError as exc:
        latency_ms = (time.perf_counter() - started) * 1000.0
        return ReqResult(
            ok=False,
            status_code=int(getattr(exc, 'code', 0) or 0),
            latency_ms=latency_ms,
            path=path,
            error=f'HTTPError:{exc}',
        )
    except URLError as exc:
        latency_ms = (time.perf_counter() - started) * 1000.0
        return ReqResult(
            ok=False,
            status_code=0,
            latency_ms=latency_ms,
            path=path,
            error=f'URLError:{exc}',
        )
    except Exception as exc:  # pragma: no cover
        latency_ms = (time.perf_counter() - started) * 1000.0
        return ReqResult(
            ok=False,
            status_code=0,
            latency_ms=latency_ms,
            path=path,
            error=f'Exception:{exc}',
        )


def _percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    if p <= 0:
        return min(values)
    if p >= 100:
        return max(values)
    vals = sorted(values)
    k = (len(vals) - 1) * (p / 100.0)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return vals[int(k)]
    d0 = vals[f] * (c - k)
    d1 = vals[c] * (k - f)
    return d0 + d1


def _run_burst(
    *,
    base_url: str,
    path: str,
    headers: dict[str, str],
    timeout_sec: float,
    requests_total: int,
    concurrency: int,
) -> list[ReqResult]:
    results: list[ReqResult] = []
    with ThreadPoolExecutor(max_workers=max(1, concurrency)) as pool:
        futures = [
            pool.submit(_request, base_url, path, headers, timeout_sec)
            for _ in range(max(1, requests_total))
        ]
        for fut in as_completed(futures):
            results.append(fut.result())
    return results


def _run_soak(
    *,
    base_url: str,
    path: str,
    headers: dict[str, str],
    timeout_sec: float,
    duration_sec: int,
    interval_sec: float,
) -> list[ReqResult]:
    results: list[ReqResult] = []
    until = time.monotonic() + max(1, duration_sec)
    while time.monotonic() < until:
        results.append(_request(base_url, path, headers, timeout_sec))
        time.sleep(max(0.01, interval_sec))
    return results


def _summarize(results: list[ReqResult]) -> dict[str, Any]:
    total = len(results)
    ok = [r for r in results if r.ok]
    lat = [r.latency_ms for r in results]
    errors = [r for r in results if not r.ok]
    status_counts: dict[str, int] = {}
    for r in results:
        k = str(r.status_code)
        status_counts[k] = status_counts.get(k, 0) + 1
    return {
        'requests_total': total,
        'ok_total': len(ok),
        'error_total': len(errors),
        'error_rate': (len(errors) / total) if total else 1.0,
        'latency_ms': {
            'min': min(lat) if lat else 0.0,
            'mean': statistics.fmean(lat) if lat else 0.0,
            'p95': _percentile(lat, 95),
            'p99': _percentile(lat, 99),
            'max': max(lat) if lat else 0.0,
        },
        'status_counts': status_counts,
        'sample_errors': [
            {'status_code': e.status_code, 'path': e.path, 'error': e.error}
            for e in errors[:5]
        ],
    }


def _build_report(args: argparse.Namespace) -> dict[str, Any]:
    auth_h = _auth_headers()
    public_h: dict[str, str] = {}
    private_h = auth_h.copy()

    burst_status = _run_burst(
        base_url=args.base_url,
        path='/api/ui/status',
        headers=private_h,
        timeout_sec=args.timeout_sec,
        requests_total=args.burst_requests,
        concurrency=args.burst_concurrency,
    )
    burst_metrics = _run_burst(
        base_url=args.base_url,
        path='/metrics',
        headers=private_h,
        timeout_sec=args.timeout_sec,
        requests_total=args.metrics_scrapes,
        concurrency=args.metrics_concurrency,
    )
    soak_health = _run_soak(
        base_url=args.base_url,
        path='/api/ui/health',
        headers=public_h,
        timeout_sec=args.timeout_sec,
        duration_sec=args.soak_seconds,
        interval_sec=args.soak_interval_sec,
    )
    soak_readiness = _run_soak(
        base_url=args.base_url,
        path='/api/ui/readiness',
        headers=public_h,
        timeout_sec=args.timeout_sec,
        duration_sec=args.soak_seconds,
        interval_sec=args.soak_interval_sec,
    )

    status_sum = _summarize(burst_status)
    metrics_sum = _summarize(burst_metrics)
    health_sum = _summarize(soak_health)
    readiness_sum = _summarize(soak_readiness)

    gates = {
        'status_burst_error_rate_ok': (
            status_sum['error_rate'] <= args.max_error_rate
        ),
        'status_burst_p95_ok': status_sum['latency_ms']['p95'] <= args.max_p95_ms,
        'status_burst_p99_ok': status_sum['latency_ms']['p99'] <= args.max_p99_ms,
        'metrics_scrape_error_rate_ok': (
            metrics_sum['error_rate'] <= args.max_error_rate
        ),
        'soak_health_error_rate_ok': health_sum['error_rate'] <= args.max_error_rate,
        'soak_readiness_error_rate_ok': (
            readiness_sum['error_rate'] <= args.max_error_rate
        ),
    }

    return {
        'schema': 'runtime_perf_gate@v1',
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'base_url': args.base_url,
        'thresholds': {
            'max_error_rate': args.max_error_rate,
            'max_p95_ms': args.max_p95_ms,
            'max_p99_ms': args.max_p99_ms,
        },
        'config': {
            'burst_requests': args.burst_requests,
            'burst_concurrency': args.burst_concurrency,
            'metrics_scrapes': args.metrics_scrapes,
            'metrics_concurrency': args.metrics_concurrency,
            'soak_seconds': args.soak_seconds,
            'soak_interval_sec': args.soak_interval_sec,
            'auth_mode': (
                'api_key'
                if os.environ.get('BIRDLENSE_UI_API_KEY')
                else ('mcp_token' if os.environ.get('MCP_TOKEN') else 'none')
            ),
        },
        'checks': {
            'status_burst': status_sum,
            'metrics_scrape_storm': metrics_sum,
            'soak_health': health_sum,
            'soak_readiness': readiness_sum,
        },
        'gates': gates,
        'ok': all(bool(v) for v in gates.values()),
    }


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        '--base-url',
        default=os.environ.get('BASE_URL', 'http://127.0.0.1:8085'),
    )
    p.add_argument('--timeout-sec', type=float, default=10.0)
    p.add_argument('--burst-requests', type=int, default=200)
    p.add_argument('--burst-concurrency', type=int, default=20)
    p.add_argument('--metrics-scrapes', type=int, default=120)
    p.add_argument('--metrics-concurrency', type=int, default=12)
    p.add_argument('--soak-seconds', type=int, default=60)
    p.add_argument('--soak-interval-sec', type=float, default=0.75)
    p.add_argument('--max-error-rate', type=float, default=0.02)
    p.add_argument('--max-p95-ms', type=float, default=3000.0)
    p.add_argument('--max-p99-ms', type=float, default=5000.0)
    p.add_argument('--out', default='')
    return p.parse_args()


def main() -> int:
    """Run runtime performance gate and return process exit code."""

    args = _parse_args()
    report = _build_report(args)
    text = json.dumps(report, ensure_ascii=False, indent=2)
    print(text)
    if (args.out or '').strip():
        with open(args.out, 'w', encoding='utf-8') as f:
            f.write(text + '\n')
    return 0 if bool(report.get('ok')) else 3


if __name__ == '__main__':
    raise SystemExit(main())
