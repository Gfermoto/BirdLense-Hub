#!/usr/bin/env python3
"""Verify BirdLense model registry entry gates for release train (#393)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


SCHEMA = 'birdlense_model_registry_entry@v1'
STAGE_ORDER = {'offline': 0, 'shadow': 1, 'canary': 2, 'full': 3}


def _load(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(data, dict):
        raise ValueError('entry root must be object')
    return data


def verify(
    entry: dict[str, Any],
    *,
    min_stage: str,
    require_benchmark: bool,
    require_dataset_ready: bool,
    require_dataset_quality: bool,
    require_hard_negatives: bool,
) -> tuple[bool, list[str]]:
    """Validate registry entry against required release gates."""
    errors: list[str] = []
    if entry.get('schema') != SCHEMA:
        errors.append(f'schema_mismatch:{entry.get("schema")}')

    candidate = entry.get('candidate')
    if not isinstance(candidate, dict):
        errors.append('candidate_missing')
        return False, errors

    stage = str(candidate.get('stage') or '')
    if stage not in STAGE_ORDER:
        errors.append(f'invalid_stage:{stage}')
    elif STAGE_ORDER[stage] < STAGE_ORDER[min_stage]:
        errors.append(f'stage_below_required:{stage}<{min_stage}')

    refs = entry.get('references')
    if not isinstance(refs, dict):
        errors.append('references_missing')
        return False, errors

    validation_ref = refs.get('validation_report')
    if not isinstance(validation_ref, dict):
        errors.append('validation_report_missing')
    else:
        if not validation_ref.get('ok'):
            errors.append('validation_not_ok')
        if not validation_ref.get('sha256'):
            errors.append('validation_sha256_missing')

    benchmark_ref = refs.get('benchmark_report')
    if require_benchmark:
        if not isinstance(benchmark_ref, dict):
            errors.append('benchmark_report_required')
        else:
            if benchmark_ref.get('report_format') != 'benchmark_track_regen@v1':
                errors.append(
                    'benchmark_report_format_invalid:'
                    f'{benchmark_ref.get("report_format")}',
                )
            if int(benchmark_ref.get('video_count') or 0) <= 0:
                errors.append('benchmark_video_count_invalid')

    dataset_quality_ref = refs.get('dataset_quality_report')
    if require_dataset_quality:
        if not isinstance(dataset_quality_ref, dict):
            errors.append('dataset_quality_report_required')
        else:
            if not dataset_quality_ref.get('ok'):
                errors.append('dataset_quality_report_not_ok')
            if not dataset_quality_ref.get('sha256'):
                errors.append('dataset_quality_report_sha256_missing')

    hard_negatives_ref = refs.get('hard_negatives_report')
    if require_hard_negatives:
        if not isinstance(hard_negatives_ref, dict):
            errors.append('hard_negatives_report_required')
        else:
            if not hard_negatives_ref.get('ok'):
                errors.append('hard_negatives_report_not_ok')
            if not hard_negatives_ref.get('sha256'):
                errors.append('hard_negatives_report_sha256_missing')

    artifacts = entry.get('artifacts')
    if not isinstance(artifacts, dict):
        errors.append('artifacts_missing')
        return False, errors

    binary = artifacts.get('binary')
    if not isinstance(binary, dict):
        errors.append('binary_artifact_missing')
    else:
        if not binary.get('exists'):
            errors.append('binary_not_found')
        if not binary.get('fingerprint_sha256_16'):
            errors.append('binary_fingerprint_missing')

    if require_dataset_ready:
        dataset_info = artifacts.get('dataset_info')
        if not isinstance(dataset_info, dict):
            errors.append('dataset_info_required')
        else:
            if dataset_info.get('schema') != 'birdlense_dataset_export_v2':
                errors.append(f'dataset_schema_invalid:{dataset_info.get("schema")}')
            if not dataset_info.get('ready_for_train'):
                errors.append('dataset_not_ready_for_train')
            if not dataset_info.get('strict_quality_ok'):
                errors.append('dataset_strict_quality_failed')

    return len(errors) == 0, errors


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '--entry',
        required=True,
        help='Model registry entry JSON path',
    )
    parser.add_argument(
        '--min-stage',
        default='offline',
        choices=tuple(STAGE_ORDER.keys()),
    )
    parser.add_argument('--require-benchmark', action='store_true')
    parser.add_argument('--require-dataset-ready', action='store_true')
    parser.add_argument('--require-dataset-quality', action='store_true')
    parser.add_argument('--require-hard-negatives', action='store_true')
    return parser.parse_args()


def main() -> int:
    """CLI entrypoint."""
    args = parse_args()
    path = Path(args.entry).resolve()
    try:
        entry = _load(path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({'ok': False, 'error': str(exc)}), file=sys.stderr)
        return 2
    ok, errors = verify(
        entry,
        min_stage=args.min_stage,
        require_benchmark=bool(args.require_benchmark),
        require_dataset_ready=bool(args.require_dataset_ready),
        require_dataset_quality=bool(args.require_dataset_quality),
        require_hard_negatives=bool(args.require_hard_negatives),
    )
    print(
        json.dumps({'ok': ok, 'errors': errors}, ensure_ascii=False, indent=2),
    )
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
