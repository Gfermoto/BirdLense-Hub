#!/usr/bin/env python3
"""Build shadow_rollout_report@v1 from shadow benchmark windows (#408)."""

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


def _window_disagreement_rate(
    report: dict[str, Any],
) -> tuple[float | None, int]:
    rows = report.get('videos')
    if not isinstance(rows, list):
        return None, 0
    mismatched = 0
    total = 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        le = row.get('label_eval')
        if not isinstance(le, dict) or bool(le.get('skipped')):
            continue
        gold = int(le.get('gold_count') or 0)
        matched = int(le.get('matched') or 0)
        total += gold
        mismatched += max(0, gold - matched)
    if total <= 0:
        return None, 0
    return float(mismatched) / float(total), total


def build_shadow_rollout_report(
    *,
    window_reports: list[dict[str, Any]],
    critical_incidents: int = 0,
    max_disagreement_rate: float = 0.05,
    min_windows: int = 2,
) -> dict[str, Any]:
    """Build shadow rollout gate report from window-level benchmark JSON."""
    windows: list[dict[str, Any]] = []
    disagreement_vals: list[float] = []
    sample_total = 0
    for idx, report in enumerate(window_reports, start=1):
        rate, samples = _window_disagreement_rate(report)
        if rate is not None:
            disagreement_vals.append(rate)
            sample_total += int(samples)
        windows.append(
            {
                'window_index': idx,
                'schema': report.get('schema'),
                'inference_backend': report.get('inference_backend'),
                'inference_device': report.get('inference_device'),
                'disagreement_rate': (
                    None if rate is None else round(rate, 6)
                ),
                'samples': int(samples),
            }
        )
    mean_disagreement = (
        sum(disagreement_vals) / len(disagreement_vals)
        if disagreement_vals
        else None
    )
    gates = {
        'min_windows_ok': bool(len(window_reports) >= int(min_windows)),
        'critical_incidents_ok': bool(int(critical_incidents) == 0),
        'disagreement_rate_ok': bool(
            mean_disagreement is None
            or mean_disagreement <= float(max_disagreement_rate)
        ),
    }
    out = {
        'schema': 'shadow_rollout_report@v1',
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'thresholds': {
            'max_disagreement_rate': float(max_disagreement_rate),
            'min_windows': int(min_windows),
        },
        'metrics': {
            'window_count': len(window_reports),
            'critical_incidents': int(critical_incidents),
            'mean_disagreement_rate': (
                None
                if mean_disagreement is None
                else round(mean_disagreement, 6)
            ),
            'disagreement_sample_count': int(sample_total),
        },
        'windows': windows,
        'gate_verdict': (
            'canary_ready'
            if all(bool(v) for v in gates.values())
            else 'hold'
        ),
        'gates': gates,
        'ok': all(bool(v) for v in gates.values()),
    }
    return out


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '--window-report',
        action='append',
        required=True,
        help=(
            'Path to one shadow window benchmark_track_regen@v1 JSON '
            '(repeatable).'
        ),
    )
    parser.add_argument('--critical-incidents', type=int, default=0)
    parser.add_argument('--max-disagreement-rate', type=float, default=0.05)
    parser.add_argument('--min-windows', type=int, default=2)
    parser.add_argument('--out', required=True)
    return parser.parse_args()


def main() -> int:
    """CLI entry point."""
    args = _parse_args()
    reports = [_load_json(path) for path in (args.window_report or [])]
    out = build_shadow_rollout_report(
        window_reports=reports,
        critical_incidents=int(args.critical_incidents),
        max_disagreement_rate=float(args.max_disagreement_rate),
        min_windows=max(1, int(args.min_windows)),
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
