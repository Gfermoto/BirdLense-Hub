#!/usr/bin/env python3
"""Compare two JSON outputs from ``benchmark-track-regen.py`` (#372).

Exit 1 if ``gold_species_recall`` drops beyond ``--tolerance`` for a matched
video (non-skipped ``label_eval``). Match by ``video`` path or basename.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any


def load_report(path: str) -> dict[str, Any]:
    """Load a benchmark JSON report from disk."""
    with open(path, encoding='utf-8') as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        raise ValueError('report root must be an object')
    return data


def _basename_index(videos: list[dict[str, Any]]) -> dict[str, str]:
    """First ``video`` path seen per basename (for fallback matching)."""
    out: dict[str, str] = {}
    for row in videos:
        vp = row.get('video')
        if not vp:
            continue
        bn = os.path.basename(str(vp))
        out.setdefault(bn, str(vp))
    return out


def compare_reports(
    baseline: dict[str, Any],
    current: dict[str, Any],
    *,
    tolerance: float,
    match_by_basename: bool,
) -> tuple[bool, list[str]]:
    """Compare recalls; return (all_ok, human-readable errors)."""
    errs: list[str] = []
    base_rows = baseline.get('videos')
    cur_rows = current.get('videos')
    if not isinstance(base_rows, list) or not isinstance(cur_rows, list):
        return False, ['invalid_report: videos must be lists']

    base_by_path = {
        str(r.get('video')): r for r in base_rows if r.get('video')
    }
    base_bn = _basename_index(base_rows) if match_by_basename else {}

    def _get_base(vp: str) -> dict[str, Any] | None:
        if vp in base_by_path:
            return base_by_path[vp]
        if match_by_basename:
            bn = os.path.basename(vp)
            alt = base_bn.get(bn)
            if alt and alt in base_by_path:
                return base_by_path[alt]
        return None

    for cur in cur_rows:
        vp = cur.get('video')
        if not vp:
            errs.append('current_row_missing_video')
            continue
        vp_s = str(vp)
        b_row = _get_base(vp_s)
        if b_row is None:
            errs.append(f'no_baseline_for_video:{vp_s}')
            continue
        ble = b_row.get('label_eval')
        cle = cur.get('label_eval')
        if isinstance(ble, dict) and ble.get('skipped'):
            continue
        if isinstance(cle, dict) and cle.get('skipped'):
            errs.append(f'label_eval_skipped_current:{vp_s}')
            continue
        if not isinstance(ble, dict) or not isinstance(cle, dict):
            continue
        br = ble.get('gold_species_recall')
        cr = cle.get('gold_species_recall')
        if br is None or cr is None:
            continue
        try:
            br_f = float(br)
            cr_f = float(cr)
        except (TypeError, ValueError):
            errs.append(f'non_numeric_recall:{vp_s}')
            continue
        if cr_f < br_f - tolerance:
            errs.append(
                f'recall_regression:{vp_s}: baseline={br_f} current={cr_f}',
            )
    ok = len(errs) == 0
    return ok, errs


def main() -> int:
    """CLI entry."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '--baseline',
        required=True,
        help='Baseline JSON report',
    )
    parser.add_argument(
        '--current',
        required=True,
        help='Current JSON report',
    )
    parser.add_argument(
        '--tolerance',
        type=float,
        default=0.0,
        help='Allowed absolute drop in gold_species_recall (default 0)',
    )
    parser.add_argument(
        '--match-by-basename',
        action='store_true',
        help='Match baseline rows by basename if path strings differ',
    )
    args = parser.parse_args()
    try:
        base = load_report(args.baseline)
        cur = load_report(args.current)
    except (OSError, ValueError, json.JSONDecodeError) as e:
        print(json.dumps({'ok': False, 'error': str(e)}), file=sys.stderr)
        return 2
    ok, errs = compare_reports(
        base,
        cur,
        tolerance=float(args.tolerance),
        match_by_basename=bool(args.match_by_basename),
    )
    summary = {
        'ok': ok,
        'errors': errs,
        'baseline_report_format': base.get('report_format'),
        'current_report_format': cur.get('report_format'),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
