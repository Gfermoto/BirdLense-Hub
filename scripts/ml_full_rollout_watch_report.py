#!/usr/bin/env python3
"""Build full rollout watch artifact for issue #410."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _load_json(path: str) -> dict[str, Any]:
    with open(path, encoding='utf-8') as f:
        payload = json.load(f)
    if not isinstance(payload, dict):
        raise ValueError(f'JSON object expected: {path}')
    return payload


def _safe_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return float(default)


def _collect_window_ok(
    window: dict[str, Any],
    max_error_rate: float,
    max_p95_latency_ms: float,
) -> tuple[bool, dict[str, Any]]:
    p95 = _safe_float(window.get('p95_latency_ms'), 0.0)
    err = _safe_float(window.get('error_rate'), 0.0)
    uptime = _safe_float(window.get('uptime_ratio'), 1.0)
    ok = bool(
        (p95 <= max_p95_latency_ms)
        and (err <= max_error_rate)
        and (uptime >= 0.995)
    )
    return ok, {
        'window': window.get('window'),
        'p95_latency_ms': round(p95, 6),
        'error_rate': round(err, 6),
        'uptime_ratio': round(uptime, 6),
        'ok': ok,
    }


def build_full_rollout_watch_report(
    *,
    before_report: dict[str, Any],
    after_report: dict[str, Any],
    watch_windows: list[dict[str, Any]],
    min_watch_hours: int = 72,
    max_error_rate: float = 0.01,
    max_p95_latency_ms: float = 450.0,
) -> dict[str, Any]:
    """Build full rollout verdict using before/after and 72h watch windows."""
    before_recall = _safe_float(before_report.get('mean_recall_kpi'), 0.0)
    after_recall = _safe_float(after_report.get('mean_recall_kpi'), 0.0)
    before_runtime = _safe_float(before_report.get('mean_runtime_seconds'), 0.0)
    after_runtime = _safe_float(after_report.get('mean_runtime_seconds'), 0.0)
    recall_delta_pp = (after_recall - before_recall) * 100.0
    latency_gain = (
        (before_runtime - after_runtime) / before_runtime
        if before_runtime > 0
        else None
    )
    checked_windows: list[dict[str, Any]] = []
    window_ok_flags: list[bool] = []
    for row in watch_windows:
        ok, normalized = _collect_window_ok(
            row,
            max_error_rate=float(max_error_rate),
            max_p95_latency_ms=float(max_p95_latency_ms),
        )
        checked_windows.append(normalized)
        window_ok_flags.append(ok)
    watch_hours = len(watch_windows) * 24
    gates = {
        'watch_window_count_ok': bool(watch_hours >= int(min_watch_hours)),
        'watch_sli_ok': bool(all(window_ok_flags)) if window_ok_flags else False,
        'quality_non_regression_ok': bool(recall_delta_pp >= -1.0),
    }
    go_no_go = 'go' if all(bool(v) for v in gates.values()) else 'no_go'
    backlog = [
        'Tune detector confidence thresholds for seasonal lighting shifts.',
        'Collect additional hard negatives for false-positive-heavy feeders.',
        'Automate weekly continuity + canary drift checks.',
    ]
    return {
        'schema': 'full_rollout_watch_report@v1',
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'thresholds': {
            'min_watch_hours': int(min_watch_hours),
            'max_error_rate': float(max_error_rate),
            'max_p95_latency_ms': float(max_p95_latency_ms),
            'max_quality_drop_pp': 1.0,
        },
        'metrics': {
            'watch_hours_observed': int(watch_hours),
            'mean_recall_before': round(before_recall, 6),
            'mean_recall_after': round(after_recall, 6),
            'recall_delta_pp': round(recall_delta_pp, 6),
            'mean_runtime_seconds_before': round(before_runtime, 6),
            'mean_runtime_seconds_after': round(after_runtime, 6),
            'runtime_improvement_ratio': (
                None if latency_gain is None else round(latency_gain, 6)
            ),
        },
        'watch_windows': checked_windows,
        'gates': gates,
        'go_no_go': go_no_go,
        'next_iteration_backlog': backlog,
        'ok': all(bool(v) for v in gates.values()),
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '--before-report',
        required=True,
        help='baseline benchmark_track_regen-like JSON.',
    )
    parser.add_argument(
        '--after-report',
        required=True,
        help='post-rollout benchmark_track_regen-like JSON.',
    )
    parser.add_argument(
        '--watch-window',
        action='append',
        required=True,
        help=(
            'JSON path with per-day SLI snapshot '
            '(p95_latency_ms, error_rate, uptime_ratio). '
            'Repeat for each day.'
        ),
    )
    parser.add_argument('--min-watch-hours', type=int, default=72)
    parser.add_argument('--max-error-rate', type=float, default=0.01)
    parser.add_argument('--max-p95-latency-ms', type=float, default=450.0)
    parser.add_argument('--out', required=True)
    return parser.parse_args()


def main() -> int:
    """CLI entry point."""
    args = _parse_args()
    before = _load_json(args.before_report)
    after = _load_json(args.after_report)
    watch = [_load_json(path) for path in (args.watch_window or [])]
    out = build_full_rollout_watch_report(
        before_report=before,
        after_report=after,
        watch_windows=watch,
        min_watch_hours=max(24, int(args.min_watch_hours)),
        max_error_rate=float(args.max_error_rate),
        max_p95_latency_ms=float(args.max_p95_latency_ms),
    )
    out_path = Path(args.out).expanduser().resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(out, ensure_ascii=False, indent=2),
        encoding='utf-8',
    )
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if bool(out.get('ok')) else 3


if __name__ == '__main__':
    raise SystemExit(main())
