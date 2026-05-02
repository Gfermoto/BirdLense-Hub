#!/usr/bin/env python3
"""Run detector-first offline benchmark gates for migration candidate (#407)."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from compare_benchmark_reports import compare_reports, species_recall_deltas
from ml_baseline_protocol import build_baseline_protocol_report


def _read_json(path: str) -> dict[str, Any]:
    with open(path, encoding='utf-8') as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        raise ValueError(f'{path}: root must be an object')
    return data


def _label_eval_sample_count(report: dict[str, Any]) -> int:
    rows = report.get('videos')
    if not isinstance(rows, list):
        return 0
    n = 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        label_eval = row.get('label_eval')
        if not isinstance(label_eval, dict):
            continue
        if label_eval.get('skipped'):
            continue
        if label_eval.get('gold_species_recall') is None:
            continue
        n += 1
    return n


def build_offline_benchmark_gate_report(
    *,
    baseline_report: dict[str, Any],
    candidate_report: dict[str, Any],
    continuity_report: dict[str, Any] | None,
    recall_tolerance: float,
    max_recall_drop: float,
    max_yolo_silent_clip_rate: float,
    require_label_eval_samples: int,
    match_by_basename: bool = True,
) -> dict[str, Any]:
    compare_ok, compare_errors = compare_reports(
        baseline_report,
        candidate_report,
        tolerance=float(recall_tolerance),
        match_by_basename=bool(match_by_basename),
        psi_fields=[],
        psi_threshold=0.25,
    )
    protocol = build_baseline_protocol_report(
        baseline_report=baseline_report,
        candidate_report=candidate_report,
        continuity_report=continuity_report,
        max_recall_drop=float(max_recall_drop),
        max_yolo_silent_clip_rate=float(max_yolo_silent_clip_rate),
    )
    baseline_samples = _label_eval_sample_count(baseline_report)
    candidate_samples = _label_eval_sample_count(candidate_report)
    enough_samples = baseline_samples >= int(require_label_eval_samples) and candidate_samples >= int(
        require_label_eval_samples
    )

    gates = {
        'compare_reports_ok': bool(compare_ok),
        'baseline_protocol_ok': bool(protocol.get('ok')),
        'label_eval_sample_gate_ok': bool(enough_samples),
    }
    errors: list[str] = []
    errors.extend(str(err) for err in compare_errors)
    if not enough_samples:
        errors.append(
            (
                'label_eval_samples_too_low: '
                f'baseline={baseline_samples} candidate={candidate_samples} '
                f'required={int(require_label_eval_samples)}'
            )
        )

    out = {
        'schema': 'offline_benchmark_gate@v1',
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'inputs': {
            'baseline_report_format': baseline_report.get('report_format'),
            'candidate_report_format': candidate_report.get('report_format'),
            'continuity_report_schema': (continuity_report or {}).get('schema'),
            'match_by_basename': bool(match_by_basename),
        },
        'thresholds': {
            'recall_tolerance': float(recall_tolerance),
            'max_recall_drop': float(max_recall_drop),
            'max_yolo_silent_clip_rate': float(max_yolo_silent_clip_rate),
            'require_label_eval_samples': int(require_label_eval_samples),
        },
        'sample_counts': {
            'baseline_label_eval_samples': baseline_samples,
            'candidate_label_eval_samples': candidate_samples,
        },
        'gates': gates,
        'compare_report_errors': errors,
        'species_recall_deltas': species_recall_deltas(
            baseline_report,
            candidate_report,
            match_by_basename=bool(match_by_basename),
        ),
        'baseline_protocol': protocol,
    }
    out['ok'] = all(bool(v) for v in gates.values())
    return out


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline-report', required=True)
    parser.add_argument('--candidate-report', required=True)
    parser.add_argument('--continuity-report', default='')
    parser.add_argument('--recall-tolerance', type=float, default=0.0)
    parser.add_argument('--max-recall-drop', type=float, default=0.02)
    parser.add_argument('--max-yolo-silent-clip-rate', type=float, default=0.2)
    parser.add_argument('--require-label-eval-samples', type=int, default=1)
    parser.add_argument('--no-match-by-basename', action='store_true')
    parser.add_argument('--out', default='')
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    baseline = _read_json(args.baseline_report)
    candidate = _read_json(args.candidate_report)
    continuity = _read_json(args.continuity_report) if str(args.continuity_report).strip() else None

    report = build_offline_benchmark_gate_report(
        baseline_report=baseline,
        candidate_report=candidate,
        continuity_report=continuity,
        recall_tolerance=float(args.recall_tolerance),
        max_recall_drop=float(args.max_recall_drop),
        max_yolo_silent_clip_rate=float(args.max_yolo_silent_clip_rate),
        require_label_eval_samples=max(0, int(args.require_label_eval_samples)),
        match_by_basename=not bool(args.no_match_by_basename),
    )
    text = json.dumps(report, ensure_ascii=False, indent=2)
    print(text)
    out = str(args.out or '').strip()
    if out:
        out_path = Path(out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text, encoding='utf-8')
    return 0 if bool(report.get('ok')) else 1


if __name__ == '__main__':
    raise SystemExit(main())
