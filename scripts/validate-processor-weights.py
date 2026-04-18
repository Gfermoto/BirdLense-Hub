#!/usr/bin/env python3
"""Validate BirdLense processor rollout artifacts before enabling custom weights."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import zipfile
from typing import Any


def _sha256(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, 'rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_16(path: str) -> str:
    return _sha256(path)[:16]


def _validate_pt(path: str) -> tuple[dict[str, Any], list[str]]:
    issues: list[str] = []
    record: dict[str, Any] = {
        'path': path,
        'exists': os.path.isfile(path),
        'bytes': None,
        'fingerprint_sha256_16': None,
        'zip_checkpoint': False,
    }
    if not record['exists']:
        issues.append(f'missing_file:{path}')
        return record, issues
    record['bytes'] = os.path.getsize(path)
    record['fingerprint_sha256_16'] = _sha256_16(path)
    if record['bytes'] < 4096:
        issues.append(f'file_too_small:{path}')
    if not zipfile.is_zipfile(path):
        issues.append(f'not_zip_checkpoint:{path}')
        return record, issues
    try:
        with zipfile.ZipFile(path, 'r') as zf:
            names = zf.namelist()
    except zipfile.BadZipFile:
        issues.append(f'bad_zip:{path}')
        return record, issues
    if not names:
        issues.append(f'empty_zip:{path}')
        return record, issues
    record['zip_checkpoint'] = True
    return record, issues


def _read_class_names(path: str | None) -> tuple[dict[str, Any], list[str]]:
    issues: list[str] = []
    record: dict[str, Any] = {
        'path': path,
        'exists': bool(path and os.path.isfile(path)),
        'class_count': 0,
        'fingerprint_sha256_16': None,
    }
    if not path:
        issues.append('class_names_missing')
        return record, issues
    if not record['exists']:
        issues.append(f'missing_file:{path}')
        return record, issues
    raw = open(path, 'rb').read()
    record['fingerprint_sha256_16'] = _sha256_16(path)
    try:
        text = raw.decode('utf-8')
    except UnicodeDecodeError:
        issues.append(f'class_names_not_utf8:{path}')
        return record, issues
    lines = [ln.split('#', 1)[0].strip() for ln in text.splitlines() if ln.split('#', 1)[0].strip()]
    record['class_count'] = len(lines)
    if not lines:
        issues.append('class_names_empty')
    if len(lines) != len(set(lines)):
        issues.append('class_names_duplicates')
    return record, issues


def _validate_dataset_info(path: str | None, *, require_train_ready: bool) -> tuple[dict[str, Any], list[str]]:
    issues: list[str] = []
    record: dict[str, Any] = {
        'path': path,
        'exists': bool(path and os.path.isfile(path)),
        'fingerprint_sha256_16': None,
        'schema': None,
        'ready_for_train': None,
        'strict_quality_ok': None,
    }
    if not path:
        issues.append('dataset_info_missing')
        return record, issues
    if not record['exists']:
        issues.append(f'missing_file:{path}')
        return record, issues
    record['fingerprint_sha256_16'] = _sha256_16(path)
    try:
        payload = json.loads(open(path, 'r', encoding='utf-8').read())
    except (OSError, ValueError) as exc:
        issues.append(f'dataset_info_invalid_json:{exc}')
        return record, issues
    manifest = payload.get('manifest') or {}
    split_params = manifest.get('split_params') or {}
    quality = payload.get('quality') or {}
    video_leakage = quality.get('video_leakage') or {}
    group_leakage = quality.get('group_leakage') or {}
    record['schema'] = manifest.get('schema')
    record['ready_for_train'] = bool(split_params.get('ready_for_train'))
    strict_ok = (
        int(quality.get('duplicate_track_count') or 0) == 0
        and int(video_leakage.get('train_val_shared') or 0) == 0
        and int(video_leakage.get('train_test_shared') or 0) == 0
        and int(video_leakage.get('val_test_shared') or 0) == 0
        and int(group_leakage.get('train_val_shared') or 0) == 0
        and int(group_leakage.get('train_test_shared') or 0) == 0
        and int(group_leakage.get('val_test_shared') or 0) == 0
    )
    record['strict_quality_ok'] = strict_ok
    if manifest.get('schema') != 'birdlense_dataset_export_v2':
        issues.append('dataset_info_schema_mismatch')
    if require_train_ready and not record['ready_for_train']:
        issues.append('dataset_info_not_ready_for_train')
    if not strict_ok:
        issues.append('dataset_info_quality_failed')
    return record, issues


def build_report(args) -> dict[str, Any]:
    binary, binary_issues = _validate_pt(args.binary)
    classifier, classifier_issues = _validate_pt(args.classifier)
    class_names, class_name_issues = _read_class_names(args.class_names)
    dataset_info, dataset_issues = _validate_dataset_info(
        args.dataset_info,
        require_train_ready=not args.allow_non_train_ready,
    )
    fusion = None
    fusion_issues: list[str] = []
    if args.fusion_model:
        fusion = {
            'path': args.fusion_model,
            'exists': os.path.isfile(args.fusion_model),
            'fingerprint_sha256_16': _sha256_16(args.fusion_model) if os.path.isfile(args.fusion_model) else None,
        }
        if not fusion['exists']:
            fusion_issues.append(f'missing_file:{args.fusion_model}')
    issues = binary_issues + classifier_issues + class_name_issues + dataset_issues + fusion_issues
    return {
        'ok': not issues,
        'rollout_profile': 'ready_for_train+strict_quality',
        'issues': issues,
        'artifacts': {
            'binary': binary,
            'classifier': classifier,
            'class_names': class_names,
            'dataset_info': dataset_info,
            'fusion_model': fusion,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', required=True, help='Path to binary detector .pt')
    parser.add_argument('--classifier', required=True, help='Path to classifier .pt')
    parser.add_argument('--class-names', dest='class_names', required=True, help='Path to class_names.txt')
    parser.add_argument('--dataset-info', help='Path to exported dataset_info.json')
    parser.add_argument('--fusion-model', help='Optional learned fusion model path')
    parser.add_argument(
        '--allow-non-train-ready',
        action='store_true',
        help='Allow dataset_info exports that were not created with ready_for_train',
    )
    parser.add_argument('--output', help='Write the JSON report to a file')
    args = parser.parse_args()

    report = build_report(args)
    body = json.dumps(report, ensure_ascii=False, indent=2)
    print(body)
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as handle:
            handle.write(body + '\n')
    return 0 if report['ok'] else 1


if __name__ == '__main__':
    sys.exit(main())
