"""Utilities for offline calibration and fusion quality metrics."""
from __future__ import annotations

from math import fsum
from statistics import mean
from typing import Iterable, Mapping, Sequence


def _safe_float(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _ece_bins(
    scores: Sequence[float],
    labels: Sequence[int],
    n_bins: int = 10,
) -> list[dict]:
    n_bins = max(1, int(n_bins or 10))
    bins: list[dict] = []
    total = len(scores)
    if total == 0:
        return bins

    edges = [i / n_bins for i in range(n_bins + 1)]
    for idx in range(n_bins):
        lo = edges[idx]
        hi = edges[idx + 1]
        if idx == n_bins - 1:
            mask = [lo <= s <= hi for s in scores]
        else:
            mask = [lo <= s < hi for s in scores]
        in_bin = [i for i, ok in enumerate(mask) if ok]
        if not in_bin:
            continue
        bin_scores = [scores[i] for i in in_bin]
        bin_labels = [labels[i] for i in in_bin]
        conf = mean(bin_scores)
        acc = mean(bin_labels)
        bins.append(
            {
                'bin': idx,
                'lo': lo,
                'hi': hi,
                'count': len(in_bin),
                'confidence': conf,
                'accuracy': acc,
                'gap': abs(acc - conf),
            }
        )
    return bins


def evaluate_binary_scores(
    rows: Iterable[Mapping[str, object]],
    *,
    score_key: str = 'score',
    label_key: str = 'label',
    n_bins: int = 10,
    thresholds: Sequence[float] = (0.5, 0.7, 0.8, 0.9, 0.95),
) -> dict:
    """Compute calibration and selective prediction metrics for a set of rows."""
    scores: list[float] = []
    labels: list[int] = []
    for row in rows or []:
        scores.append(_safe_float(row.get(score_key), 0.0))
        labels.append(1 if _safe_int(row.get(label_key), 0) > 0 else 0)

    total = len(scores)
    positive_rate = mean(labels) if labels else 0.0
    brier = mean([(s - y) ** 2 for s, y in zip(scores, labels)]) if scores else 0.0
    bins = _ece_bins(scores, labels, n_bins=n_bins)
    ece = 0.0
    if total:
        ece = fsum((bin_['count'] / total) * bin_['gap'] for bin_ in bins)

    threshold_metrics = {}
    risk_coverage = []
    for threshold in thresholds:
        covered = [
            (s, y)
            for s, y in zip(scores, labels)
            if s >= float(threshold)
        ]
        coverage = len(covered) / total if total else 0.0
        precision = mean([y for _s, y in covered]) if covered else 0.0
        recall = (
            sum(y for _s, y in covered) / sum(labels)
            if covered and sum(labels) > 0
            else 0.0
        )
        threshold_metrics[f'{float(threshold):.2f}'] = {
            'coverage': coverage,
            'precision': precision,
            'recall': recall,
            'risk': 1.0 - precision if covered else 1.0,
            'count': len(covered),
        }
        risk_coverage.append(
            {
                'threshold': float(threshold),
                'coverage': coverage,
                'precision': precision,
                'risk': 1.0 - precision if covered else 1.0,
            }
        )

    accuracy = (
        mean([int((s >= 0.5) == bool(y)) for s, y in zip(scores, labels)])
        if scores
        else 0.0
    )
    return {
        'n': total,
        'positive_rate': positive_rate,
        'accuracy_at_0_5': accuracy,
        'brier': brier,
        'ece': ece,
        'thresholds': threshold_metrics,
        'risk_coverage': risk_coverage,
        'bins': bins,
    }


def evaluate_by_slice(
    rows: Iterable[Mapping[str, object]],
    *,
    score_key: str = 'score',
    label_key: str = 'label',
    slice_field: str,
) -> dict:
    """Evaluate calibration metrics for each distinct value in `slice_field`."""
    grouped: dict[str, list[dict]] = {}
    for row in rows or []:
        value = row.get(slice_field)
        if value is None or value == '':
            value = '(missing)'
        grouped.setdefault(str(value), []).append(dict(row))
    return {
        key: evaluate_binary_scores(
            value_rows,
            score_key=score_key,
            label_key=label_key,
        )
        for key, value_rows in grouped.items()
    }

