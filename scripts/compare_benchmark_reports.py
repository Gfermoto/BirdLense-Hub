#!/usr/bin/env python3
"""Compare two JSON outputs from ``benchmark-track-regen.py`` (#372).

Exit 1 if ``gold_species_recall`` drops beyond ``--tolerance`` for a matched
video (non-skipped ``label_eval``). Match by ``video`` path or basename.
"""

from __future__ import annotations

import argparse
import json
import math
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


def _to_float_list(value: Any) -> list[float]:
    """Coerce scalar/list metric value to finite floats."""
    raw = value if isinstance(value, list) else [value]
    out: list[float] = []
    for item in raw:
        try:
            x = float(item)
        except (TypeError, ValueError):
            continue
        if x == x and x not in (float('inf'), float('-inf')):
            out.append(x)
    return out


def _get_path(row: dict[str, Any], dotted: str) -> Any:
    cur: Any = row
    for part in dotted.split('.'):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
    return cur


def collect_metric_values(report: dict[str, Any], field_path: str) -> list[float]:
    """Collect numeric values from ``videos[*].<field_path>``."""
    vals: list[float] = []
    videos = report.get('videos')
    if not isinstance(videos, list):
        return vals
    for row in videos:
        if isinstance(row, dict):
            vals.extend(_to_float_list(_get_path(row, field_path)))
    return vals


def _quantile(vals: list[float], q: float) -> float:
    vals = sorted(vals)
    if not vals:
        return 0.0
    pos = (len(vals) - 1) * max(0.0, min(1.0, q))
    lo = int(pos)
    hi = min(lo + 1, len(vals) - 1)
    frac = pos - lo
    return vals[lo] * (1.0 - frac) + vals[hi] * frac


def _psi_edges(base: list[float], bins: int) -> list[float]:
    if not base:
        return []
    edges = [_quantile(base, i / bins) for i in range(1, bins)]
    uniq = []
    for edge in edges:
        if not uniq or edge > uniq[-1]:
            uniq.append(edge)
    return uniq


def population_stability_index(
    baseline_values: list[float],
    current_values: list[float],
    *,
    bins: int = 10,
    eps: float = 1e-6,
) -> float | None:
    """Return PSI between two numeric distributions, or None if insufficient."""
    if len(baseline_values) < 2 or len(current_values) < 2:
        return None
    edges = _psi_edges(baseline_values, max(2, int(bins or 10)))
    base_counts = [0] * (len(edges) + 1)
    cur_counts = [0] * (len(edges) + 1)

    def bucket(v: float) -> int:
        for i, edge in enumerate(edges):
            if v <= edge:
                return i
        return len(edges)

    for v in baseline_values:
        base_counts[bucket(v)] += 1
    for v in current_values:
        cur_counts[bucket(v)] += 1

    total_b = float(len(baseline_values))
    total_c = float(len(current_values))
    psi = 0.0
    for b, c in zip(base_counts, cur_counts, strict=True):
        bp = max(b / total_b, eps)
        cp = max(c / total_c, eps)
        psi += (cp - bp) * math.log(cp / bp)
    return float(psi)


def compare_psi(
    baseline: dict[str, Any],
    current: dict[str, Any],
    *,
    fields: list[str],
    threshold: float,
    bins: int = 10,
) -> tuple[list[dict[str, Any]], list[str]]:
    """Compare configured distribution fields with PSI."""
    metrics: list[dict[str, Any]] = []
    errs: list[str] = []
    for field in fields:
        base_vals = collect_metric_values(baseline, field)
        cur_vals = collect_metric_values(current, field)
        psi = population_stability_index(base_vals, cur_vals, bins=bins)
        row = {
            'field': field,
            'baseline_n': len(base_vals),
            'current_n': len(cur_vals),
            'psi': None if psi is None else round(psi, 6),
        }
        metrics.append(row)
        if psi is not None and psi > threshold:
            errs.append(f'psi_drift:{field}: psi={psi:.6f} threshold={threshold}')
    return metrics, errs


def compare_reports(
    baseline: dict[str, Any],
    current: dict[str, Any],
    *,
    tolerance: float,
    match_by_basename: bool,
    psi_fields: list[str] | None = None,
    psi_threshold: float | None = None,
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
    if psi_fields:
        _metrics, psi_errs = compare_psi(
            baseline,
            current,
            fields=list(psi_fields),
            threshold=float(psi_threshold if psi_threshold is not None else 0.25),
        )
        errs.extend(psi_errs)
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
    parser.add_argument(
        '--psi-field',
        action='append',
        default=[],
        help='Dotted videos[*] metric path for PSI drift (repeatable)',
    )
    parser.add_argument(
        '--psi-threshold',
        type=float,
        default=0.25,
        help='PSI drift threshold for --psi-field (default 0.25)',
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
        psi_fields=list(args.psi_field or []),
        psi_threshold=float(args.psi_threshold),
    )
    psi_metrics, _psi_errs = compare_psi(
        base,
        cur,
        fields=list(args.psi_field or []),
        threshold=float(args.psi_threshold),
    )
    summary = {
        'ok': ok,
        'errors': errs,
        'baseline_report_format': base.get('report_format'),
        'current_report_format': cur.get('report_format'),
        'psi': psi_metrics,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
