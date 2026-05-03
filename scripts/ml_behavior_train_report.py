#!/usr/bin/env python3
"""Build behavior training/eval report from manifest and predictions."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _read_json(path: str) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding='utf-8'))
    if not isinstance(payload, dict):
        raise ValueError(f'{path}: expected JSON object')
    return payload


def _safe_div(n: float, d: float) -> float:
    if d <= 0:
        return 0.0
    return float(n) / float(d)


def build_behavior_train_report(
    *,
    manifest: dict[str, Any],
    predictions: dict[str, Any],
    split: str = 'val',
    min_macro_f1: float = 0.45,
) -> dict[str, Any]:
    if str(manifest.get('schema') or '') != 'behavior_dataset_manifest@v1':
        raise ValueError('manifest schema must be behavior_dataset_manifest@v1')

    labels = [str(row.get('label')) for row in (manifest.get('taxonomy') or []) if row.get('label')]
    labels = sorted(set(labels))
    if not labels:
        raise ValueError('manifest taxonomy labels are empty')

    pred_rows = predictions.get('predictions') or []
    pred_map: dict[str, dict[str, Any]] = {}
    for row in pred_rows:
        if not isinstance(row, dict):
            continue
        key = str(row.get('video_key') or '').strip()
        if not key:
            continue
        pred_map[key] = row

    eval_rows: list[dict[str, Any]] = []
    confusion = {t: {p: 0 for p in labels} for t in labels}
    for row in manifest.get('videos') or []:
        if not isinstance(row, dict):
            continue
        if str(row.get('split') or '') != split:
            continue
        video_key = str(row.get('video_key') or '').strip()
        gt_labels = [str(x) for x in (row.get('behavior_labels') or []) if str(x)]
        if not video_key or not gt_labels:
            continue
        gt_label = gt_labels[0]
        pred = pred_map.get(video_key, {})
        pred_label = str(pred.get('pred_label') or '').strip().lower()
        if pred_label not in labels:
            pred_label = labels[0]
        confidence = float(pred.get('confidence') or 0.0)
        if gt_label in confusion:
            confusion[gt_label][pred_label] += 1
        eval_rows.append(
            {
                'video_key': video_key,
                'gt_label': gt_label,
                'pred_label': pred_label,
                'confidence': round(confidence, 6),
                'is_correct': bool(gt_label == pred_label),
                'is_multilabel_gt': len(gt_labels) > 1,
            }
        )

    per_class: dict[str, dict[str, float]] = {}
    f1_values: list[float] = []
    total = len(eval_rows)
    correct = sum(1 for row in eval_rows if row['is_correct'])
    for label in labels:
        tp = float(confusion[label][label])
        fp = float(sum(confusion[t][label] for t in labels if t != label))
        fn = float(sum(confusion[label][p] for p in labels if p != label))
        precision = _safe_div(tp, tp + fp)
        recall = _safe_div(tp, tp + fn)
        f1 = _safe_div(2.0 * precision * recall, precision + recall)
        per_class[label] = {
            'precision': round(precision, 6),
            'recall': round(recall, 6),
            'f1': round(f1, 6),
            'support': int(sum(confusion[label].values())),
        }
        f1_values.append(f1)

    macro_f1 = _safe_div(sum(f1_values), len(f1_values))
    accuracy = _safe_div(correct, total)
    multi_gt = sum(1 for row in eval_rows if row.get('is_multilabel_gt'))
    gates = {
        'has_eval_rows': bool(total > 0),
        'macro_f1_ok': bool(macro_f1 >= float(min_macro_f1)),
    }
    return {
        'schema': 'behavior_train_report@v1',
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'inputs': {
            'split': split,
            'min_macro_f1': float(min_macro_f1),
            'manifest_dataset_id': manifest.get('dataset_id'),
        },
        'metrics': {
            'eval_rows': total,
            'accuracy': round(accuracy, 6),
            'macro_f1': round(macro_f1, 6),
            'multilabel_gt_rows': int(multi_gt),
        },
        'per_class': per_class,
        'confusion_matrix': confusion,
        'rows': eval_rows,
        'gates': gates,
        'ok': all(bool(v) for v in gates.values()),
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', required=True)
    parser.add_argument('--predictions', required=True)
    parser.add_argument('--split', default='val')
    parser.add_argument('--min-macro-f1', type=float, default=0.45)
    parser.add_argument('--out', required=True)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    manifest = _read_json(args.manifest)
    predictions = _read_json(args.predictions)
    report = build_behavior_train_report(
        manifest=manifest,
        predictions=predictions,
        split=str(args.split or 'val'),
        min_macro_f1=float(args.min_macro_f1),
    )
    out = Path(args.out).expanduser().resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if bool(report.get('ok')) else 2


if __name__ == '__main__':
    raise SystemExit(main())
