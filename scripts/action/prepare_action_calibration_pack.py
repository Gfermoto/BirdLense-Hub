#!/usr/bin/env python3
# flake8: noqa
"""Prepare calibration subset and annotator templates from action seed JSONL."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for ln in path.read_text(encoding='utf-8').splitlines():
        if not ln.strip():
            continue
        obj = json.loads(ln)
        if isinstance(obj, dict):
            rows.append(obj)
    return rows


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        '\n'.join(json.dumps(r, ensure_ascii=False) for r in rows) + '\n',
        encoding='utf-8',
    )


def prepare_pack(
    *,
    seed_jsonl: Path,
    output_dir: Path,
    max_videos: int,
    max_segments_per_video: int,
    annotator_a: str,
    annotator_b: str,
) -> dict[str, Any]:
    rows = _read_jsonl(seed_jsonl)
    by_video: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        try:
            vid = int(row.get('video_id'))
        except Exception:
            continue
        by_video[vid].append(row)

    selected: list[dict[str, Any]] = []
    selected_videos: list[int] = []
    for vid in sorted(by_video.keys()):
        per_video = sorted(
            by_video[vid],
            key=lambda r: (int(r.get('t_start_ms', 0)), int(r.get('t_end_ms', 0))),
        )[: max(1, int(max_segments_per_video))]
        if not per_video:
            continue
        selected.extend(per_video)
        selected_videos.append(vid)
        if len(selected_videos) >= int(max_videos):
            break

    subset_path = output_dir / 'action_calibration_subset.jsonl'
    _write_jsonl(subset_path, selected)

    def _template_row(base: dict[str, Any], annotator_id: str) -> dict[str, Any]:
        return {
            'segment_uid': base.get('segment_uid'),
            'video_id': base.get('video_id'),
            'track_id': base.get('track_id'),
            'camera_id': base.get('camera_id'),
            't_start_ms': base.get('t_start_ms'),
            't_end_ms': base.get('t_end_ms'),
            'action_label': base.get('action_label'),
            'annotator_id': annotator_id,
            'created_at_utc': base.get('created_at_utc'),
            'source': 'calibration_template_from_seed',
        }

    ann_a_rows = [_template_row(r, annotator_a) for r in selected]
    ann_b_rows = [_template_row(r, annotator_b) for r in selected]
    ann_a_path = output_dir / 'action_calibration_annotator_a.jsonl'
    ann_b_path = output_dir / 'action_calibration_annotator_b.jsonl'
    _write_jsonl(ann_a_path, ann_a_rows)
    _write_jsonl(ann_b_path, ann_b_rows)

    label_counts = Counter(str(r.get('action_label') or '') for r in selected)
    video_labels = defaultdict(set)
    for r in selected:
        try:
            vid = int(r.get('video_id'))
        except Exception:
            continue
        video_labels[vid].add(str(r.get('action_label') or ''))

    summary = {
        'schema': 'action_calibration_pack@v1',
        'seed_jsonl': str(seed_jsonl),
        'output_dir': str(output_dir),
        'subset_rows': len(selected),
        'subset_videos': len(selected_videos),
        'label_counts': dict(label_counts),
        'videos_without_possible_feeding': sum(
            1 for labels in video_labels.values() if 'possible_feeding' not in labels
        ),
        'files': {
            'subset_jsonl': str(subset_path),
            'annotator_a_jsonl': str(ann_a_path),
            'annotator_b_jsonl': str(ann_b_path),
        },
    }
    summary_path = output_dir / 'action_calibration_summary.json'
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    summary['files']['summary_json'] = str(summary_path)
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seed-jsonl', required=True)
    parser.add_argument('--output-dir', required=True)
    parser.add_argument('--max-videos', type=int, default=60)
    parser.add_argument('--max-segments-per-video', type=int, default=2)
    parser.add_argument('--annotator-a', default='annotator_a')
    parser.add_argument('--annotator-b', default='annotator_b')
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    summary = prepare_pack(
        seed_jsonl=Path(args.seed_jsonl).resolve(),
        output_dir=Path(args.output_dir).resolve(),
        max_videos=int(args.max_videos),
        max_segments_per_video=int(args.max_segments_per_video),
        annotator_a=str(args.annotator_a),
        annotator_b=str(args.annotator_b),
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
