#!/usr/bin/env python3
"""Validate minimal JSON shape from ``benchmark-track-regen.py`` (#372).

Used in CI after smoke runs — без закреплённых числовых baseline в репозитории.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any


def validate_report(data: dict[str, Any]) -> tuple[bool, list[str]]:
    """Проверить минимальную структуру отчёта; вернуть (успех, сообщения)."""
    errs: list[str] = []
    rf = data.get('report_format')
    if rf not in (None, 'benchmark_track_regen@v1'):
        errs.append(f'unexpected report_format: {rf!r}')
    videos = data.get('videos')
    if not isinstance(videos, list) or len(videos) < 1:
        errs.append('videos must be a non-empty list')
        return False, errs
    for i, row in enumerate(videos):
        if not isinstance(row, dict):
            errs.append(f'videos[{i}] must be object')
            continue
        if 'video' not in row:
            errs.append(f'videos[{i}] missing video')
        for key in ('raw_track_count', 'fused_track_count'):
            if key in row and not isinstance(row[key], (int, float)):
                errs.append(f'videos[{i}].{key} must be numeric')
        le = row.get('label_eval')
        if le is not None and not isinstance(le, dict):
            errs.append(f'videos[{i}].label_eval must be object or absent')
    ls = data.get('labels_sidecar')
    if ls is not None:
        if not isinstance(ls, dict):
            errs.append('labels_sidecar must be object')
        elif 'path' not in ls or 'schema' not in ls:
            errs.append('labels_sidecar must have path and schema')
    ok = len(errs) == 0
    return ok, errs


def main() -> int:
    """CLI."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '--report',
        required=True,
        help='Path to benchmark JSON',
    )
    args = parser.parse_args()
    try:
        with open(args.report, encoding='utf-8') as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError) as e:
        print(json.dumps({'ok': False, 'error': str(e)}), file=sys.stderr)
        return 2
    if not isinstance(data, dict):
        err = {'ok': False, 'error': 'root must be object'}
        print(json.dumps(err), file=sys.stderr)
        return 2
    ok, errs = validate_report(data)
    out = {'ok': ok, 'errors': errs}
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
