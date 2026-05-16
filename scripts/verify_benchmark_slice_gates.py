#!/usr/bin/env python3
"""Verify benchmark quality gates per context slices (#391)."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any


def _load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(data, dict):
        raise ValueError(f'{path}: root must be object')
    return data


def _load_slice_map(path: Path) -> dict[str, dict[str, str]]:
    data = _load_json(path)
    by_basename = data.get('by_basename')
    if not isinstance(by_basename, dict):
        raise ValueError('slice map must contain by_basename object')
    out: dict[str, dict[str, str]] = {}
    for basename, row in by_basename.items():
        if isinstance(row, dict):
            out[str(basename)] = {str(k): str(v) for k, v in row.items()}
    return out


def verify_slices(
    report: dict[str, Any],
    *,
    slice_map: dict[str, dict[str, str]],
    group_by: list[str],
    min_gold_samples: int,
    min_recall: float,
) -> tuple[bool, dict[str, Any]]:
    """Evaluate recall gates grouped by context slices."""
    videos = report.get('videos')
    if not isinstance(videos, list):
        return False, {'errors': ['videos must be list']}

    groups: dict[str, dict[str, float]] = defaultdict(lambda: {'hits': 0.0, 'gold': 0.0, 'videos': 0.0})
    skipped = 0
    for row in videos:
        if not isinstance(row, dict):
            skipped += 1
            continue
        video = str(row.get('video') or '')
        if not video:
            skipped += 1
            continue
        basename = Path(video).name
        context = slice_map.get(basename)
        if not context:
            skipped += 1
            continue

        label_eval = row.get('label_eval')
        if not isinstance(label_eval, dict) or label_eval.get('skipped'):
            skipped += 1
            continue
        gold_species = label_eval.get('gold_species') or []
        pred_species = {
            str(x)
            for x in (label_eval.get('predicted_species_unique') or [])
            if str(x)
        }
        if not isinstance(gold_species, list) or not gold_species:
            skipped += 1
            continue

        key = '|'.join(f'{k}={context.get(k, "unknown")}' for k in group_by)
        for raw in gold_species:
            species = str(raw).strip()
            if not species:
                continue
            groups[key]['gold'] += 1.0
            if species in pred_species:
                groups[key]['hits'] += 1.0
        groups[key]['videos'] += 1.0

    failures: list[str] = []
    summary_groups: list[dict[str, Any]] = []
    for key, vals in sorted(groups.items()):
        gold = int(vals['gold'])
        hits = float(vals['hits'])
        recall = (hits / gold) if gold else 0.0
        row = {
            'slice': key,
            'video_count': int(vals['videos']),
            'gold_samples': gold,
            'recall': round(recall, 6),
        }
        summary_groups.append(row)
        if gold >= min_gold_samples and recall < min_recall:
            failures.append(
                f'slice_recall_below_threshold:{key}: '
                f'recall={recall:.6f} threshold={min_recall:.6f} gold={gold}',
            )

    ok = len(failures) == 0
    return ok, {
        'ok': ok,
        'group_by': group_by,
        'min_gold_samples': min_gold_samples,
        'min_recall': min_recall,
        'groups': summary_groups,
        'skipped_rows': skipped,
        'errors': failures,
    }


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', required=True, help='benchmark-track-regen JSON report')
    parser.add_argument('--slice-map', required=True, help='JSON with by_basename context mapping')
    parser.add_argument(
        '--group-by',
        action='append',
        default=[],
        help=(
            'Context field to aggregate by (repeatable, '
            'default: season,camera,domain)'
        ),
    )
    parser.add_argument('--min-gold-samples', type=int, default=5)
    parser.add_argument('--min-recall', type=float, default=0.7)
    return parser.parse_args()


def main() -> int:
    """CLI entrypoint."""
    args = parse_args()
    group_by = args.group_by or ['season', 'camera', 'domain']
    report = _load_json(Path(args.report).resolve())
    slice_map = _load_slice_map(Path(args.slice_map).resolve())
    ok, summary = verify_slices(
        report,
        slice_map=slice_map,
        group_by=group_by,
        min_gold_samples=int(args.min_gold_samples),
        min_recall=float(args.min_recall),
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
