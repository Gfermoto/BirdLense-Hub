#!/usr/bin/env python3
"""Build behavior training/eval report from manifest and predictions."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _write_confusion_matrix_csv(confusion: dict[str, dict[str, int]], labels: list[str], path: Path) -> None:
    """Flatten confusion dict to CSV (gt rows, pred columns)."""
    header = ["gt_label"] + labels
    lines = [",".join(header)]
    for gt in labels:
        row = [gt] + [str(int(confusion[gt].get(p, 0))) for p in labels]
        lines.append(",".join(row))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _binary_prf(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
    precision = _safe_div(float(tp), float(tp + fp))
    recall = _safe_div(float(tp), float(tp + fn))
    f1 = _safe_div(2.0 * precision * recall, precision + recall)
    return precision, recall, f1


def _best_ovr_threshold(scores: list[float], y_true_binary: list[int]) -> dict[str, float]:
    """One-vs-rest: threshold maximizing binary F1 on scores ∈ [0,1]."""
    best_t = 0.5
    best_f1 = -1.0
    best_p = best_r = 0.0
    for i in range(51):
        t = i / 50.0
        tp = fp = fn = 0
        for s, y in zip(scores, y_true_binary, strict=False):
            pred_pos = bool(s >= t)
            if y == 1:
                if pred_pos:
                    tp += 1
                else:
                    fn += 1
            else:
                if pred_pos:
                    fp += 1
        p, r, f1 = _binary_prf(tp, fp, fn)
        if f1 > best_f1:
            best_f1 = f1
            best_t = t
            best_p = p
            best_r = r
    return {"threshold": round(best_t, 6), "f1": round(best_f1, 6), "precision": round(best_p, 6), "recall": round(best_r, 6)}


def _threshold_suggestions_from_eval(
    eval_rows: list[dict[str, Any]],
    labels: list[str],
) -> dict[str, Any]:
    """Пороги по полным proba (если есть в predictions)."""
    rows_with_proba = [r for r in eval_rows if isinstance(r.get("proba"), dict)]
    if not rows_with_proba:
        return {"available": False, "reason": "predictions lack per-class proba (re-run ml_behavior_train_baseline)"}

    per_class: dict[str, Any] = {}
    scores_for_median: list[float] = []
    max_probs = [float(r.get("confidence") or 0.0) for r in rows_with_proba]

    for c in labels:
        scores = []
        y_bin = []
        for r in rows_with_proba:
            prob = r["proba"]
            assert isinstance(prob, dict)
            scores.append(float(prob.get(c, 0.0)))
            y_bin.append(1 if str(r.get("gt_label") or "") == c else 0)
        ovr = _best_ovr_threshold(scores, y_bin)
        per_class[c] = ovr
        scores_for_median.append(float(ovr["threshold"]))

    median_thr = scores_for_median[len(scores_for_median) // 2] if scores_for_median else 0.45

    # Глобальный порог по max(proba): минимизировать долю ошибок среди «уверенных» предсказаний (max_prob ≥ τ).
    best_global = 0.45
    best_acc = -1.0
    for i in range(51):
        t = i / 50.0
        ok = 0
        tot = 0
        for r in rows_with_proba:
            mp = float(r.get("confidence") or 0.0)
            if mp < t:
                continue
            tot += 1
            if bool(r.get("is_correct")):
                ok += 1
        acc = _safe_div(float(ok), float(tot)) if tot > 0 else -1.0
        if tot > 0 and acc > best_acc:
            best_acc = acc
            best_global = t

    mp_sorted = sorted(max_probs)
    mid = len(mp_sorted) // 2
    p95_conf = float(mp_sorted[int(0.95 * (len(mp_sorted) - 1))]) if mp_sorted else 0.0

    return {
        "available": True,
        "per_class_ovr": per_class,
        "median_ovr_threshold": round(float(median_thr), 6),
        "confidence_gate": {
            "best_threshold_max_prob_ge": round(best_global, 6),
            "subset_accuracy_at_best_threshold": round(best_acc, 6),
            "note": "accuracy только среди строк с max_prob ≥ τ; подсказка для confidence_review_threshold",
        },
        "distribution_hints": {
            "median_max_prob": round(float(mp_sorted[mid]), 6) if mp_sorted else 0.0,
            "p95_max_prob": round(p95_conf, 6),
        },
    }

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
    confusion_csv: Path | None = None,
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
        raw_proba = pred.get('proba')
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
                **(
                    {'proba': {str(k): float(v) for k, v in raw_proba.items()}}
                    if isinstance(raw_proba, dict)
                    else {}
                ),
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
    threshold_suggestions = _threshold_suggestions_from_eval(eval_rows, labels)
    out_obj = {
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
        'threshold_suggestions': threshold_suggestions,
        'rows': eval_rows,
        'gates': gates,
        'ok': all(bool(v) for v in gates.values()),
    }
    if confusion_csv is not None:
        ordered = sorted(confusion.keys())
        _write_confusion_matrix_csv(confusion, ordered, confusion_csv)
    return out_obj


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', required=True)
    parser.add_argument('--predictions', required=True)
    parser.add_argument('--split', default='val')
    parser.add_argument('--min-macro-f1', type=float, default=0.45)
    parser.add_argument('--out', required=True)
    parser.add_argument('--confusion-csv', default='', help='Optional confusion matrix CSV path')
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    manifest = _read_json(args.manifest)
    predictions = _read_json(args.predictions)
    csv_path = Path(args.confusion_csv).expanduser().resolve() if str(args.confusion_csv or '').strip() else None
    report = build_behavior_train_report(
        manifest=manifest,
        predictions=predictions,
        split=str(args.split or 'val'),
        min_macro_f1=float(args.min_macro_f1),
        confusion_csv=csv_path,
    )
    out = Path(args.out).expanduser().resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if bool(report.get('ok')) else 2


if __name__ == '__main__':
    raise SystemExit(main())
