#!/usr/bin/env python3
"""Build action-model shortlist and MVP recipe for issue #406."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _default_candidates() -> list[dict[str, Any]]:
    return [
        {
            'id': 'mobilenetv3_small_tsm',
            'name': 'MobileNetV3-Small + TSM',
            'params_m': 2.9,
            'latency_class': 'fast',
            'small_data_bias': 'good',
            'domain_shift_risk': 'medium',
            'notes': (
                'Good edge latency; robust baseline for small feeder datasets.'
            ),
        },
        {
            'id': 'x3d_xs',
            'name': 'X3D-XS',
            'params_m': 3.8,
            'latency_class': 'fast-medium',
            'small_data_bias': 'medium',
            'domain_shift_risk': 'medium',
            'notes': (
                'Strong temporal inductive bias with manageable compute budget.'
            ),
        },
        {
            'id': 'videomae_v2_small_distilled',
            'name': 'VideoMAE-v2 Small (distilled)',
            'params_m': 22.0,
            'latency_class': 'slow',
            'small_data_bias': 'medium',
            'domain_shift_risk': 'low-medium',
            'notes': (
                'High quality candidate for next stage, '
                'not MVP latency profile.'
            ),
        },
    ]


def _score_candidate(row: dict[str, Any]) -> float:
    latency = str(row.get('latency_class') or '').lower()
    small_data = str(row.get('small_data_bias') or '').lower()
    shift = str(row.get('domain_shift_risk') or '').lower()
    score = 0.0
    if latency == 'fast':
        score += 3.0
    elif latency == 'fast-medium':
        score += 2.0
    elif latency == 'medium':
        score += 1.0
    if small_data == 'good':
        score += 3.0
    elif small_data == 'medium':
        score += 2.0
    if shift in {'low', 'low-medium'}:
        score += 2.0
    elif shift == 'medium':
        score += 1.0
    return score


def build_action_model_shortlist(
    *,
    candidates: list[dict[str, Any]] | None = None,
    min_dataset_clips: int = 800,
) -> dict[str, Any]:
    """Build shortlist report with candidate ranking and training recipe."""
    rows = list(candidates or _default_candidates())
    scored = sorted(
        (
            {
                **row,
                'score': round(_score_candidate(row), 6),
            }
            for row in rows
        ),
        key=lambda x: x['score'],
        reverse=True,
    )
    mvp = scored[0] if scored else None
    recipe = {
        'optimizer': 'adamw',
        'epochs': 40,
        'batch_size': 16,
        'learning_rate': 3e-4,
        'weight_decay': 1e-2,
        'sampler': 'weighted_random_sampler',
        'loss': {
            'type': 'focal_cross_entropy',
            'gamma': 1.5,
            'label_smoothing': 0.05,
        },
        'augmentations': [
            'random_resized_crop',
            'color_jitter',
            'temporal_jitter',
            'mixup(alpha=0.2)',
        ],
        'metrics': ['macro_f1', 'balanced_accuracy', 'calibration_ece'],
        'early_stopping': {'monitor': 'macro_f1', 'patience': 6},
    }
    risks = [
        {
            'risk': 'domain_shift_lighting',
            'mitigation': (
                'night/day balanced sampler + periodic recalibration '
                'on feeder clips'
            ),
        },
        {
            'risk': 'class_imbalance_rare_actions',
            'mitigation': (
                'weighted sampler + focal loss + hard-negative replay'
            ),
        },
        {
            'risk': 'camera_angle_shift',
            'mitigation': (
                'camera-specific validation split + lightweight '
                'test-time augmentation'
            ),
        },
    ]
    gates = {
        'mvp_selected': bool(mvp is not None),
        'recipe_defined': True,
        'dataset_minimum_ok': bool(int(min_dataset_clips) >= 600),
    }
    return {
        'schema': 'action_model_shortlist@v1',
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'inputs': {'min_dataset_clips': int(min_dataset_clips)},
        'mvp_model': {
            'id': (mvp or {}).get('id'),
            'name': (mvp or {}).get('name'),
            'score': (mvp or {}).get('score'),
        },
        'candidates': scored,
        'mvp_training_recipe': recipe,
        'domain_shift_risks': risks,
        'gates': gates,
        'ok': all(bool(v) for v in gates.values()),
    }


def _load_candidates(path: str | None) -> list[dict[str, Any]] | None:
    if not path:
        return None
    with open(path, encoding='utf-8') as f:
        payload = json.load(f)
    if not isinstance(payload, list):
        raise ValueError('Candidate JSON must be a list')
    out: list[dict[str, Any]] = []
    for row in payload:
        if isinstance(row, dict):
            out.append(dict(row))
    return out


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidates-json', default='')
    parser.add_argument('--min-dataset-clips', type=int, default=800)
    parser.add_argument('--out', required=True)
    return parser.parse_args()


def main() -> int:
    """CLI entry point."""
    args = _parse_args()
    candidates = _load_candidates((args.candidates_json or '').strip() or None)
    out = build_action_model_shortlist(
        candidates=candidates,
        min_dataset_clips=max(0, int(args.min_dataset_clips)),
    )
    out_path = Path(args.out).expanduser().resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(out, ensure_ascii=False, indent=2),
        encoding='utf-8',
    )
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if bool(out.get('ok')) else 3


if __name__ == '__main__':
    raise SystemExit(main())
