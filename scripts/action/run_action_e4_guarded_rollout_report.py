#!/usr/bin/env python3
# flake8: noqa
"""Build E4 guarded rollout go/no-go report from E2+E3 artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _load_json(path: Path) -> dict[str, Any]:
    obj = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(obj, dict):
        raise ValueError(f'{path}: root must be object')
    return obj


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--e2-report', required=True, help='Path to action_e2_pipeline_report@v1 JSON')
    p.add_argument('--e3-sweep-report', required=True, help='Path to action_e3_shadow_sweep@v1 JSON')
    p.add_argument('--required-windows', default='120,168', help='Comma-separated E3 windows required for E4 gate')
    p.add_argument('--output-json', required=True)
    return p.parse_args()


def main() -> int:
    args = parse_args()
    e2 = _load_json(Path(args.e2_report).resolve())
    e3 = _load_json(Path(args.e3_sweep_report).resolve())

    req_windows = [int(x.strip()) for x in str(args.required_windows).split(',') if x.strip()]
    e3_results = e3.get('results') if isinstance(e3.get('results'), list) else []
    e3_by_win = {}
    for row in e3_results:
        if isinstance(row, dict) and row.get('window_hours') is not None:
            e3_by_win[int(row['window_hours'])] = row

    missing_windows = [w for w in req_windows if w not in e3_by_win]
    bad_windows: list[dict[str, Any]] = []
    for w in req_windows:
        row = e3_by_win.get(w) or {}
        if not bool(row.get('ok')) or not bool(row.get('data_available')):
            bad_windows.append({'window_hours': w, 'reason': 'window_not_ok_or_no_data', 'row': row})
            continue
        if int(row.get('suggest_same_total') or 0) <= 0:
            bad_windows.append({'window_hours': w, 'reason': 'no_suggestions', 'row': row})

    e2_ok = bool(e2.get('ok')) and bool(e2.get('passes_quality_bar'))
    e3_ok = bool(e3.get('ok')) and not missing_windows and not bad_windows

    go = e2_ok and e3_ok
    out = {
        'schema': 'action_e4_guarded_rollout@v1',
        'ok': bool(go),
        'decision': 'go' if go else 'no_go',
        'checks': {
            'e2_ok': bool(e2_ok),
            'e2_best_model_id': (e2.get('recommendation') or {}).get('best_model_id'),
            'e2_fallback_model_id': (e2.get('recommendation') or {}).get('fallback_model_id'),
            'e2_quality_bar': e2.get('quality_bar'),
            'e3_ok': bool(e3_ok),
            'required_windows': req_windows,
            'missing_windows': missing_windows,
            'bad_windows': bad_windows,
        },
        'artifacts': {
            'e2_report': str(Path(args.e2_report).resolve()),
            'e3_sweep_report': str(Path(args.e3_sweep_report).resolve()),
        },
    }

    out_path = Path(args.output_json).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if go else 1


if __name__ == '__main__':
    raise SystemExit(main())
