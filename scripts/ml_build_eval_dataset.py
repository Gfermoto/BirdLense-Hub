#!/usr/bin/env python3
"""Build versioned eval dataset manifest for ML migration (#404)."""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from benchmark_regen_labels import load_gold_by_basename

_DEFAULT_VIDEO_GLOBS = ('*.mp4', '*.mkv', '*.avi', '*.mov')


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as fh:
        while True:
            chunk = fh.read(1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def _iter_videos(root: Path, patterns: tuple[str, ...]) -> list[Path]:
    files: list[Path] = []
    for item in sorted(root.rglob('*')):
        if not item.is_file():
            continue
        if any(fnmatch.fnmatch(item.name.lower(), p.lower()) for p in patterns):
            files.append(item)
    return files


def build_eval_dataset_manifest(
    *,
    videos_root: str,
    labels_json: str | None = None,
    dataset_id: str | None = None,
    patterns: tuple[str, ...] = _DEFAULT_VIDEO_GLOBS,
) -> dict[str, Any]:
    root = Path(videos_root).resolve()
    if not root.is_dir():
        raise ValueError(f'videos_root is not a directory: {root}')
    now = _utc_now()
    ds_id = (dataset_id or now.strftime('%Y%m%dT%H%M%SZ')).strip()
    if not ds_id:
        raise ValueError('dataset_id must not be empty')

    videos = _iter_videos(root, patterns)
    files: list[dict[str, Any]] = []
    total_bytes = 0
    basenames: list[str] = []
    for video_path in videos:
        rel = video_path.relative_to(root).as_posix()
        stat = video_path.stat()
        size = int(stat.st_size)
        total_bytes += size
        basenames.append(video_path.name)
        files.append(
            {
                'relative_path': rel,
                'basename': video_path.name,
                'size_bytes': size,
                'mtime_utc': datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
                'sha256': _sha256_file(video_path),
            }
        )

    labels_payload: dict[str, Any] | None = None
    coverage = {
        'labels_provided': False,
        'labeled_basename_count': 0,
        'video_count': len(files),
        'label_coverage_ratio': 0.0,
        'videos_without_labels': [],
        'labels_without_videos': [],
    }
    if labels_json:
        gold = load_gold_by_basename(labels_json)
        labeled_names = set(gold.keys())
        present_names = set(basenames)
        matched_names = sorted(present_names & labeled_names)
        unlabeled = sorted(present_names - labeled_names)
        orphan = sorted(labeled_names - present_names)
        coverage = {
            'labels_provided': True,
            'labeled_basename_count': len(matched_names),
            'video_count': len(files),
            'label_coverage_ratio': round((len(matched_names) / len(files)) if files else 1.0, 6),
            'videos_without_labels': unlabeled,
            'labels_without_videos': orphan,
        }
        labels_payload = {
            'schema_version': 1,
            'gold_by_basename': {name: gold[name] for name in matched_names},
        }

    return {
        'schema': 'eval_dataset_manifest@v1',
        'dataset_id': ds_id,
        'created_at': now.isoformat(),
        'videos_root': str(root),
        'video_globs': list(patterns),
        'video_count': len(files),
        'total_size_bytes': total_bytes,
        'files': files,
        'labels_coverage': coverage,
        'gold_labels': labels_payload,
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--videos-root', required=True, help='Root directory with eval videos')
    parser.add_argument('--labels-json', default='', help='Optional gold labels JSON (gold_by_basename@v1)')
    parser.add_argument('--dataset-id', default='', help='Dataset version id (default: UTC timestamp)')
    parser.add_argument(
        '--video-glob',
        action='append',
        default=[],
        help='Repeatable glob for video files (default: *.mp4,*.mkv,*.avi,*.mov)',
    )
    parser.add_argument('--out-dir', required=True, help='Directory to write <dataset_id>/manifest.json')
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    patterns = tuple(args.video_glob) if args.video_glob else _DEFAULT_VIDEO_GLOBS
    manifest = build_eval_dataset_manifest(
        videos_root=args.videos_root,
        labels_json=(args.labels_json or '').strip() or None,
        dataset_id=(args.dataset_id or '').strip() or None,
        patterns=patterns,
    )
    out_root = Path(args.out_dir).resolve()
    out_dir = out_root / str(manifest['dataset_id'])
    out_dir.mkdir(parents=True, exist_ok=True)

    manifest_path = out_dir / 'manifest.json'
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    labels_payload = manifest.get('gold_labels')
    if isinstance(labels_payload, dict):
        labels_path = out_dir / 'gold_labels.json'
        labels_path.write_text(json.dumps(labels_payload, ensure_ascii=False, indent=2), encoding='utf-8')

    print(json.dumps({'ok': True, 'dataset_id': manifest['dataset_id'], 'manifest_path': str(manifest_path)}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
