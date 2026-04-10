#!/usr/bin/env python3
"""Offline calibration evaluation for fusion / BirdNET priors.

Reads a CSV exported from `scripts/export_fusion_training_data.py` or any
compatible table, computes score calibration metrics, and optionally slices by
one or more categorical fields.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'app' / 'processor' / 'src'
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def _load_csv_rows(path: Path) -> list[dict]:
    with path.open('r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        return [dict(row) for row in reader]


def _score_rows(rows: list[dict], model_path: str | None, score_col: str | None) -> list[dict]:
    from fusion_model import FusionScorer  # type: ignore

    if score_col:
        scored = []
        for row in rows:
            out = dict(row)
            out['score'] = row.get(score_col)
            scored.append(out)
        return scored

    scorer = FusionScorer(model_path=model_path)
    scored = []
    for row in rows:
        features = {
            'detector_conf': row.get('detector_conf') or row.get('detector_confidence') or 0.0,
            'classifier_conf': row.get('classifier_conf') or row.get('classifier_confidence') or 0.0,
            'birdnet_prior': row.get('birdnet_prior') or row.get('_birdnet_prior') or 0.0,
            'key_frame_score': row.get('key_frame_score') or row.get('best_frame_score') or 0.0,
            'key_frame_count': row.get('key_frame_count') or 0.0,
            'multi_camera_count': row.get('multi_camera_count') or row.get('_multi_camera_count') or 0.0,
        }
        out = dict(row)
        out['score'] = scorer.score(features)
        scored.append(out)
    return scored


def main(argv: list[str] | None = None) -> int:
    from fusion_metrics import evaluate_binary_scores, evaluate_by_slice  # type: ignore

    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--data',
        '-d',
        type=Path,
        required=True,
        help='CSV exported from decision traces or fusion features',
    )
    parser.add_argument(
        '--model-path',
        type=str,
        default=None,
        help='Optional saved fusion state to score rows',
    )
    parser.add_argument(
        '--score-col',
        type=str,
        default=None,
        help='Use an existing score column instead of scoring with FusionScorer',
    )
    parser.add_argument('--label-col', type=str, default='label', help='Label column to evaluate')
    parser.add_argument(
        '--slice-field',
        action='append',
        default=[],
        help='Optional categorical field to slice metrics by',
    )
    parser.add_argument('--bins', type=int, default=10)
    parser.add_argument(
        '--threshold',
        action='append',
        type=float,
        default=[],
        help='Confidence thresholds for selective metrics',
    )
    parser.add_argument(
        '--json-out',
        type=Path,
        default=None,
        help='Optional path to write JSON report',
    )
    args = parser.parse_args(argv)

    rows = _load_csv_rows(args.data)
    if not rows:
        raise SystemExit(f'No rows found in {args.data}')

    thresholds = tuple(args.threshold) if args.threshold else (0.5, 0.7, 0.8, 0.9, 0.95)
    scored = _score_rows(rows, args.model_path, args.score_col)
    report = evaluate_binary_scores(
        scored,
        score_key='score',
        label_key=args.label_col,
        n_bins=args.bins,
        thresholds=thresholds,
    )
    if args.slice_field:
        report['slices'] = {
            field: evaluate_by_slice(
                scored,
                score_key='score',
                label_key=args.label_col,
                slice_field=field,
            )
            for field in args.slice_field
        }

    text = json.dumps(report, indent=2, ensure_ascii=False)
    print(text)
    if args.json_out:
        args.json_out.write_text(text, encoding='utf-8')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

