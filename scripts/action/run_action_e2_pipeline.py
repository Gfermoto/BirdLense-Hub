#!/usr/bin/env python3
# flake8: noqa
"""Run consolidated E2 benchmark and recommendation pipeline."""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any


def _load_module(path: Path, module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, path)
    if not spec or not spec.loader:
        raise RuntimeError(f'Failed to load module: {path}')
    mod = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = mod
    spec.loader.exec_module(mod)
    return mod


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for ln in path.read_text(encoding='utf-8').splitlines():
        if not ln.strip():
            continue
        obj = json.loads(ln)
        if isinstance(obj, dict):
            rows.append(obj)
    return rows


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ground-truth-jsonl', required=True)
    parser.add_argument('--predictions-jsonl', required=True)
    parser.add_argument('--output-json', required=True)
    parser.add_argument('--tolerance-sec', type=float, default=1.5)
    parser.add_argument('--quality-min-f1', type=float, default=0.70)
    parser.add_argument('--quality-max-delay-p95-sec', type=float, default=1.5)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = Path(__file__).resolve().parents[2]
    out_path = Path(args.output_json).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    benchmark_mod = _load_module(
        root / 'scripts' / 'action' / 'benchmark_action_candidates.py',
        'benchmark_action_candidates',
    )
    gt_rows = _read_jsonl(Path(args.ground_truth_jsonl).resolve())
    pred_rows = _read_jsonl(Path(args.predictions_jsonl).resolve())
    report = benchmark_mod.benchmark_candidates(
        ground_truth_rows=gt_rows,
        prediction_rows=pred_rows,
        tolerance_sec=float(args.tolerance_sec),
    )

    models = list(report.get('models') or [])
    best = models[0] if models else None
    fallback = models[1] if len(models) > 1 else None
    passes_quality_bar = False
    if best:
        delay = best.get('boundary_delay_p95_sec')
        delay_ok = (delay is None) or (float(delay) <= float(args.quality_max_delay_p95_sec))
        passes_quality_bar = (
            float(best.get('f1') or 0.0) >= float(args.quality_min_f1)
            and delay_ok
        )

    result = {
        'schema': 'action_e2_pipeline_report@v1',
        'ok': bool(best is not None),
        'passes_quality_bar': bool(passes_quality_bar),
        'quality_bar': {
            'min_f1': float(args.quality_min_f1),
            'max_boundary_delay_p95_sec': float(args.quality_max_delay_p95_sec),
            'tolerance_sec': float(args.tolerance_sec),
        },
        'recommendation': {
            'best_model_id': best.get('model_id') if best else None,
            'fallback_model_id': fallback.get('model_id') if fallback else None,
        },
        'benchmark': report,
        'input': {
            'ground_truth_jsonl': str(Path(args.ground_truth_jsonl).resolve()),
            'predictions_jsonl': str(Path(args.predictions_jsonl).resolve()),
            'ground_truth_rows': len(gt_rows),
            'prediction_rows': len(pred_rows),
        },
    }
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
