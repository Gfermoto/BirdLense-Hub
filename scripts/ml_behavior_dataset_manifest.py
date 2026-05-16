#!/usr/bin/env python3
"""Build behavior dataset manifest with taxonomy and deterministic splits."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_TAXONOMY = [
    {'id': 1, 'source_name': 'Alert', 'label': 'alert'},
    {'id': 2, 'source_name': 'Feeding', 'label': 'feeding'},
    {'id': 3, 'source_name': 'Flying', 'label': 'flying'},
    {'id': 4, 'source_name': 'Preening', 'label': 'preening'},
    {'id': 5, 'source_name': 'Resting', 'label': 'resting'},
    {'id': 6, 'source_name': 'Swimming', 'label': 'swimming'},
    {'id': 7, 'source_name': 'Walking', 'label': 'walking'},
]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _load_taxonomy(path: str | None) -> list[dict[str, Any]]:
    if not path:
        return list(DEFAULT_TAXONOMY)
    payload = json.loads(Path(path).read_text(encoding='utf-8'))
    if not isinstance(payload, list):
        raise ValueError('taxonomy json must be a list')
    out: list[dict[str, Any]] = []
    for row in payload:
        if not isinstance(row, dict):
            continue
        bid = int(row.get('id'))
        label = str(row.get('label') or '').strip().lower()
        source_name = str(row.get('source_name') or label or f'behavior_{bid}')
        if not label:
            raise ValueError(f'taxonomy row has empty label (id={bid})')
        out.append({'id': bid, 'source_name': source_name, 'label': label})
    if not out:
        raise ValueError('taxonomy must not be empty')
    return out


def _collect_annotation_rows(
    annotations_root: Path,
    *,
    taxonomy_by_id: dict[int, str],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted(annotations_root.rglob('*')):
        if not path.is_file() or path.suffix.lower() != '.csv':
            continue
        video_key = path.stem
        behavior_ids: Counter[int] = Counter()
        subjects: set[str] = set()
        species_names: set[str] = set()
        frame_rows = 0
        with path.open('r', encoding='utf-8') as fh:
            reader = csv.reader(fh)
            for row in reader:
                if len(row) < 6:
                    continue
                try:
                    behavior_id = int(float((row[4] or '').strip()))
                except (TypeError, ValueError):
                    continue
                if behavior_id not in taxonomy_by_id:
                    continue
                frame_rows += 1
                behavior_ids[behavior_id] += 1
                subject_id = str(row[5] or '').strip()
                if subject_id:
                    subjects.add(subject_id)
                if len(row) >= 7:
                    species = str(row[6] or '').strip()
                    if species:
                        species_names.add(species)
        if frame_rows <= 0:
            continue
        labels = sorted({taxonomy_by_id[k] for k in behavior_ids.keys()})
        rows.append(
            {
                'video_key': video_key,
                'annotation_path': path.relative_to(annotations_root).as_posix(),
                'behavior_counts': dict(sorted(behavior_ids.items())),
                'behavior_labels': labels,
                'frame_rows': frame_rows,
                'subject_count': len(subjects),
                'species_names': sorted(species_names),
            }
        )
    return rows


def _split_for_video(video_key: str, *, seed: int, train_ratio: float, val_ratio: float) -> str:
    h = hashlib.sha1(f'{seed}:{video_key}'.encode('utf-8')).hexdigest()
    bucket = int(h[:8], 16) / 0xFFFFFFFF
    if bucket < train_ratio:
        return 'train'
    if bucket < (train_ratio + val_ratio):
        return 'val'
    return 'test'


def build_behavior_dataset_manifest(
    *,
    annotations_root: str,
    dataset_id: str | None = None,
    taxonomy_json: str | None = None,
    split_seed: int = 42,
    train_ratio: float = 0.7,
    val_ratio: float = 0.15,
    test_ratio: float = 0.15,
) -> dict[str, Any]:
    root = Path(annotations_root).resolve()
    if not root.is_dir():
        raise ValueError(f'annotations_root is not a directory: {root}')
    total = float(train_ratio + val_ratio + test_ratio)
    if abs(total - 1.0) > 1e-6:
        raise ValueError('split ratios must sum to 1.0')

    taxonomy = _load_taxonomy(taxonomy_json)
    taxonomy_by_id = {int(row['id']): str(row['label']) for row in taxonomy}
    entries = _collect_annotation_rows(root, taxonomy_by_id=taxonomy_by_id)
    now = _utc_now()
    ds_id = (dataset_id or now.strftime('%Y%m%dT%H%M%SZ')).strip()
    if not ds_id:
        raise ValueError('dataset_id must not be empty')

    split_counts: Counter[str] = Counter()
    label_counts: Counter[str] = Counter()
    label_split_counts: dict[str, Counter[str]] = defaultdict(Counter)
    for row in entries:
        split = _split_for_video(
            row['video_key'],
            seed=int(split_seed),
            train_ratio=float(train_ratio),
            val_ratio=float(val_ratio),
        )
        row['split'] = split
        split_counts[split] += 1
        for label in row['behavior_labels']:
            label_counts[label] += 1
            label_split_counts[label][split] += 1

    return {
        'schema': 'behavior_dataset_manifest@v1',
        'dataset_id': ds_id,
        'created_at': now.isoformat(),
        'annotations_root': str(root),
        'split_seed': int(split_seed),
        'split_ratios': {
            'train': float(train_ratio),
            'val': float(val_ratio),
            'test': float(test_ratio),
        },
        'taxonomy': taxonomy,
        'video_count': len(entries),
        'videos': entries,
        'stats': {
            'split_counts': dict(split_counts),
            'behavior_label_video_counts': dict(sorted(label_counts.items())),
            'behavior_label_split_counts': {
                label: dict(sorted(counter.items()))
                for label, counter in sorted(label_split_counts.items())
            },
        },
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--annotations-root', required=True)
    parser.add_argument('--dataset-id', default='')
    parser.add_argument('--taxonomy-json', default='')
    parser.add_argument('--split-seed', type=int, default=42)
    parser.add_argument('--train-ratio', type=float, default=0.7)
    parser.add_argument('--val-ratio', type=float, default=0.15)
    parser.add_argument('--test-ratio', type=float, default=0.15)
    parser.add_argument('--out', required=True)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    manifest = build_behavior_dataset_manifest(
        annotations_root=args.annotations_root,
        dataset_id=(args.dataset_id or '').strip() or None,
        taxonomy_json=(args.taxonomy_json or '').strip() or None,
        split_seed=int(args.split_seed),
        train_ratio=float(args.train_ratio),
        val_ratio=float(args.val_ratio),
        test_ratio=float(args.test_ratio),
    )
    out_path = Path(args.out).expanduser().resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'ok': True, 'manifest_path': str(out_path), 'video_count': manifest['video_count']}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
