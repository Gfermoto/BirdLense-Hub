#!/usr/bin/env python3
"""Build BirdLense model registry entry from rollout artifacts (#393)."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA = 'birdlense_model_registry_entry@v1'
STAGES = ('offline', 'shadow', 'canary', 'full')


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(data, dict):
        raise ValueError(f'{path}: root must be object')
    return data


def _artifact_ref(artifact: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(artifact, dict):
        return None
    path = str(artifact.get('path') or '')
    if not path:
        return None
    return {
        'path': path,
        'fingerprint_sha256_16': artifact.get('fingerprint_sha256_16'),
        'exists': bool(artifact.get('exists')),
    }


def _dataset_ref(dataset_info: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(dataset_info, dict):
        return None
    path = str(dataset_info.get('path') or '')
    if not path:
        return None
    return {
        'path': path,
        'fingerprint_sha256_16': dataset_info.get('fingerprint_sha256_16'),
        'ready_for_train': dataset_info.get('ready_for_train'),
        'strict_quality_ok': dataset_info.get('strict_quality_ok'),
        'schema': dataset_info.get('schema'),
    }


def _benchmark_ref(path: Path | None) -> dict[str, Any] | None:
    """Build compact reference to benchmark report."""
    if path is None:
        return None
    report = _load_json(path)
    videos = report.get('videos')
    if not isinstance(videos, list):
        raise ValueError('benchmark report: videos must be list')
    return {
        'path': str(path),
        'sha256': _sha256(path),
        'report_format': report.get('report_format'),
        'inference_backend': report.get('inference_backend'),
        'video_count': len(videos),
    }


def _gate_report_ref(
    *,
    path: Path | None,
    report_kind: str,
) -> dict[str, Any] | None:
    """Build compact ref for generic gate reports with top-level ``ok`` flag."""
    if path is None:
        return None
    report = _load_json(path)
    return {
        'path': str(path),
        'sha256': _sha256(path),
        'report_kind': report_kind,
        'ok': bool(report.get('ok')),
    }


def build_entry(args: argparse.Namespace) -> dict[str, Any]:
    """Build registry entry payload from input artifacts."""
    validate_path = Path(args.validation_report).resolve()
    validation = _load_json(validate_path)
    artifacts = validation.get('artifacts') or {}

    benchmark_path = (
        Path(args.benchmark_report).resolve()
        if args.benchmark_report
        else None
    )
    benchmark = _benchmark_ref(benchmark_path) if benchmark_path else None
    dataset_quality_path = (
        Path(args.dataset_quality_report).resolve()
        if args.dataset_quality_report
        else None
    )
    dataset_quality_ref = _gate_report_ref(
        path=dataset_quality_path,
        report_kind='detector_dataset_quality@v1',
    )
    hard_negatives_path = (
        Path(args.hard_negatives_report).resolve()
        if args.hard_negatives_report
        else None
    )
    hard_negatives_ref = _gate_report_ref(
        path=hard_negatives_path,
        report_kind='hard_negatives_manifest_quality@v1',
    )

    entry: dict[str, Any] = {
        'schema': SCHEMA,
        'created_at': datetime.now(timezone.utc).isoformat(),
        'candidate': {
            'name': args.name,
            'stage': args.stage,
            'source_issue': args.source_issue,
            'notes': args.notes or '',
        },
        'references': {
            'validation_report': {
                'path': str(validate_path),
                'sha256': _sha256(validate_path),
                'ok': bool(validation.get('ok')),
            },
            'benchmark_report': benchmark,
            'dataset_quality_report': dataset_quality_ref,
            'hard_negatives_report': hard_negatives_ref,
            'detector_package_url': args.detector_package_url or '',
            'classifier_package_url': args.classifier_package_url or '',
        },
        'artifacts': {
            'binary': _artifact_ref(artifacts.get('binary')),
            'classifier': _artifact_ref(artifacts.get('classifier')),
            'class_names': _artifact_ref(artifacts.get('class_names')),
            'fusion_model': _artifact_ref(artifacts.get('fusion_model')),
            'dataset_info': _dataset_ref(artifacts.get('dataset_info')),
        },
        'gates': {
            'validation_ok': bool(validation.get('ok')),
            'dataset_ready_for_train': bool(
                (artifacts.get('dataset_info') or {}).get('ready_for_train'),
            ),
            'dataset_strict_quality_ok': bool(
                (artifacts.get('dataset_info') or {}).get('strict_quality_ok'),
            ),
            'benchmark_present': benchmark is not None,
            'dataset_quality_present': dataset_quality_ref is not None,
            'hard_negatives_present': hard_negatives_ref is not None,
        },
    }
    return entry


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '--name',
        required=True,
        help='Candidate identifier (e.g. detector-20260429)',
    )
    parser.add_argument('--stage', default='offline', choices=STAGES)
    parser.add_argument('--source-issue', default='', help='Tracking issue URL/ID')
    parser.add_argument(
        '--validation-report',
        required=True,
        help='JSON from validate-processor-weights.py',
    )
    parser.add_argument(
        '--benchmark-report',
        default='',
        help='Optional JSON from benchmark-track-regen.py',
    )
    parser.add_argument(
        '--dataset-quality-report',
        default='',
        help='Optional JSON from verify_detector_dataset_quality.py',
    )
    parser.add_argument(
        '--hard-negatives-report',
        default='',
        help='Optional JSON from verify_hard_negatives_manifest.py',
    )
    parser.add_argument(
        '--detector-package-url',
        default='',
        help='Detector package URL (HF/model registry)',
    )
    parser.add_argument(
        '--classifier-package-url',
        default='',
        help='Classifier package URL (HF/model registry)',
    )
    parser.add_argument('--notes', default='', help='Optional free-form note')
    parser.add_argument('--output', required=True, help='Output path for registry entry JSON')
    return parser.parse_args()


def main() -> int:
    """CLI entrypoint."""
    args = parse_args()
    entry = build_entry(args)
    out_path = Path(args.output).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(entry, ensure_ascii=False, indent=2) + '\n',
        encoding='utf-8',
    )
    print(str(out_path))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
