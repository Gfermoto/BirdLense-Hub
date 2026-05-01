#!/usr/bin/env python3
# flake8: noqa
"""Sweep E3 shadow report across multiple time windows."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


def _parse_windows(raw: str) -> list[int]:
    vals: list[int] = []
    for chunk in (raw or '').split(','):
        s = chunk.strip()
        if not s:
            continue
        vals.append(max(1, int(s)))
    return vals


def _run_one(
    *,
    runner_path: Path,
    window_hours: int,
    video_limit: int,
    out_json: Path,
    thresholds: dict[str, float],
) -> dict[str, Any]:
    cmd = [
        sys.executable,
        str(runner_path),
        '--output-json',
        str(out_json),
        '--window-hours',
        str(window_hours),
        '--video-limit',
        str(video_limit),
        '--min-action-available-ratio',
        str(thresholds['min_action_available_ratio']),
        '--min-reid-available-ratio',
        str(thresholds['min_reid_available_ratio']),
        '--max-reid-reject-proxy-ratio',
        str(thresholds['max_reid_reject_proxy_ratio']),
    ]
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        return {
            'window_hours': window_hours,
            'runner_ok': False,
            'error': 'runner_failed',
            'stderr_tail': p.stderr[-500:],
        }
    if not out_json.is_file():
        return {
            'window_hours': window_hours,
            'runner_ok': False,
            'error': 'report_missing',
        }
    obj = json.loads(out_json.read_text(encoding='utf-8'))
    return {
        'window_hours': window_hours,
        'runner_ok': True,
        'ok': obj.get('ok'),
        'data_available': obj.get('data_available'),
        'videos_evaluated': obj.get('videos_evaluated'),
        'action_available_ratio': ((obj.get('action') or {}).get('available_ratio')),
        'reid_available_ratio': ((obj.get('reid') or {}).get('available_ratio')),
        'matches_total': ((obj.get('reid') or {}).get('matches_total')),
        'suggest_same_total': ((obj.get('reid') or {}).get('suggest_same_total')),
        'outcomes_proxy': ((obj.get('reid') or {}).get('outcomes_proxy')),
        'summary_contract_status': ((obj.get('reid') or {}).get('summary_contract_status')),
        'report_path': str(out_json),
    }


def _best_window(results: list[dict[str, Any]]) -> dict[str, Any] | None:
    good = [r for r in results if r.get('runner_ok') and r.get('data_available')]
    if not good:
        return None
    good.sort(
        key=lambda r: (
            int(r.get('suggest_same_total') or 0),
            int(r.get('matches_total') or 0),
            int(r.get('videos_evaluated') or 0),
        ),
        reverse=True,
    )
    return good[0]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runner-path', default='scripts/action/run_action_e3_shadow_report.py')
    parser.add_argument('--output-dir', required=True)
    parser.add_argument('--windows', default='24,48,72,120,168,336')
    parser.add_argument('--video-limit', type=int, default=1200)
    parser.add_argument('--min-action-available-ratio', type=float, default=0.95)
    parser.add_argument('--min-reid-available-ratio', type=float, default=0.90)
    parser.add_argument('--max-reid-reject-proxy-ratio', type=float, default=0.50)
    parser.add_argument('--require-suggestions', action='store_true')
    parser.add_argument('--output-json', required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    runner = Path(args.runner_path).resolve()
    out_dir = Path(args.output_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    windows = _parse_windows(args.windows)
    if not windows:
        raise SystemExit('No windows specified')

    thresholds = {
        'min_action_available_ratio': float(args.min_action_available_ratio),
        'min_reid_available_ratio': float(args.min_reid_available_ratio),
        'max_reid_reject_proxy_ratio': float(args.max_reid_reject_proxy_ratio),
    }
    results: list[dict[str, Any]] = []
    for w in windows:
        report_path = out_dir / f'action_e3_shadow_{w}h.json'
        one = _run_one(
            runner_path=runner,
            window_hours=w,
            video_limit=int(args.video_limit),
            out_json=report_path,
            thresholds=thresholds,
        )
        results.append(one)

    best = _best_window(results)
    suggestions = int(best.get('suggest_same_total') or 0) if best else 0
    ok = all(bool(r.get('runner_ok')) for r in results)
    if args.require_suggestions and suggestions <= 0:
        ok = False

    final = {
        'schema': 'action_e3_shadow_sweep@v1',
        'ok': ok,
        'require_suggestions': bool(args.require_suggestions),
        'windows': windows,
        'best_window': best,
        'results': results,
    }
    out_json = Path(args.output_json).resolve()
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(final, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(final, ensure_ascii=False, indent=2))
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
