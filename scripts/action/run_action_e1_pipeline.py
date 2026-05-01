#!/usr/bin/env python3
# flake8: noqa
"""Run end-to-end E1 pipeline for action-labeling artifacts."""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from collections import Counter
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


def _seed_stats(rows: list[dict[str, Any]]) -> dict[str, Any]:
    labels = Counter(str(r.get('action_label') or '') for r in rows)
    videos = Counter(int(r.get('video_id')) for r in rows if r.get('video_id') is not None)
    videos_without_feeding = 0
    by_video: dict[int, set[str]] = {}
    for r in rows:
        if r.get('video_id') is None:
            continue
        vid = int(r['video_id'])
        by_video.setdefault(vid, set()).add(str(r.get('action_label') or ''))
    for lset in by_video.values():
        if 'possible_feeding' not in lset:
            videos_without_feeding += 1
    return {
        'rows': len(rows),
        'videos': len(videos),
        'label_counts': dict(labels),
        'label_ratio': (
            {k: round(v / len(rows), 6) for k, v in labels.items()} if rows else {}
        ),
        'videos_without_possible_feeding': videos_without_feeding,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db-path', required=True)
    parser.add_argument('--output-dir', required=True)
    parser.add_argument('--limit-videos', type=int, default=400)
    parser.add_argument('--boundary-ms', type=int, default=300)
    parser.add_argument('--min-track-duration-ms', type=int, default=300)
    parser.add_argument('--min-tracks', type=int, default=1)
    parser.add_argument('--min-weight-delta-kg', type=float, default=0.001)
    parser.add_argument('--require-weight-delta', action='store_true')
    parser.add_argument('--annotator-id', default='bootstrap_weak_label')
    parser.add_argument('--calib-max-videos', type=int, default=60)
    parser.add_argument('--calib-segments-per-video', type=int, default=2)
    parser.add_argument('--calib-annotator-a', default='annotator_a')
    parser.add_argument('--calib-annotator-b', default='annotator_b')
    parser.add_argument('--agreement-ann-a', default='')
    parser.add_argument('--agreement-ann-b', default='')
    parser.add_argument('--min-kappa', type=float, default=0.75)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = Path(__file__).resolve().parents[2]
    out_dir = Path(args.output_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    seed_jsonl = out_dir / 'action_seed.jsonl'
    seed_manifest = out_dir / 'action_seed_manifest.json'
    calibration_dir = out_dir / 'calibration'
    final_report = out_dir / 'action_e1_report.json'

    export_mod = _load_module(
        root / 'scripts' / 'action' / 'export_action_seed_dataset.py',
        'export_action_seed_dataset',
    )
    calibration_mod = _load_module(
        root / 'scripts' / 'action' / 'prepare_action_calibration_pack.py',
        'prepare_action_calibration_pack',
    )
    agreement_mod = _load_module(
        root / 'scripts' / 'action' / 'compute_action_agreement.py',
        'compute_action_agreement',
    )

    seed_summary = export_mod.export_seed_rows(
        db_path=Path(args.db_path).resolve(),
        output_jsonl=seed_jsonl,
        manifest_json=seed_manifest,
        limit_videos=int(args.limit_videos),
        boundary_ms=int(args.boundary_ms),
        min_track_duration_ms=int(args.min_track_duration_ms),
        min_tracks=int(args.min_tracks),
        min_weight_delta_kg=float(args.min_weight_delta_kg),
        require_weight_delta=bool(args.require_weight_delta),
        annotator_id=str(args.annotator_id),
        video_ids=[],
    )
    seed_rows = _read_jsonl(seed_jsonl)
    seed_stats = _seed_stats(seed_rows)

    calib_summary = calibration_mod.prepare_pack(
        seed_jsonl=seed_jsonl,
        output_dir=calibration_dir,
        max_videos=int(args.calib_max_videos),
        max_segments_per_video=int(args.calib_segments_per_video),
        annotator_a=str(args.calib_annotator_a),
        annotator_b=str(args.calib_annotator_b),
    )

    agreement_a = (
        Path(args.agreement_ann_a).resolve()
        if str(args.agreement_ann_a).strip()
        else calibration_dir / 'action_calibration_annotator_a.jsonl'
    )
    agreement_b = (
        Path(args.agreement_ann_b).resolve()
        if str(args.agreement_ann_b).strip()
        else calibration_dir / 'action_calibration_annotator_b.jsonl'
    )
    agreement_ok = False
    agreement_report: dict[str, Any] | None = None
    if agreement_a.is_file() and agreement_b.is_file():
        agreement_ok, agreement_report = agreement_mod.compute_report(
            annotator_a_jsonl=agreement_a,
            annotator_b_jsonl=agreement_b,
            min_kappa=float(args.min_kappa),
            max_disagreements=100,
        )

    hard_cases: list[str] = []
    if int(seed_stats['label_counts'].get('possible_feeding', 0)) == 0:
        hard_cases.append('missing_possible_feeding_segments')
    if int(seed_stats['videos_without_possible_feeding']) == int(seed_stats['videos']):
        hard_cases.append('no_weight_evidence_in_seed_window')

    dod = {
        'seed_manifest_present': seed_manifest.is_file(),
        'seed_rows_gt_zero': int(seed_stats['rows']) > 0,
        'calibration_pack_present': bool(calib_summary.get('subset_rows', 0)) > 0,
        'kappa_measured': agreement_report is not None,
        'kappa_passed': bool(agreement_ok) if agreement_report is not None else False,
        'has_possible_feeding_seed': int(seed_stats['label_counts'].get('possible_feeding', 0)) > 0,
    }

    final = {
        'schema': 'action_e1_pipeline_report@v1',
        'ok': all(
            [
                bool(dod['seed_manifest_present']),
                bool(dod['seed_rows_gt_zero']),
                bool(dod['calibration_pack_present']),
                bool(dod['kappa_measured']),
                bool(dod['kappa_passed']),
            ]
        ),
        'dod': dod,
        'seed_summary': seed_summary,
        'seed_stats': seed_stats,
        'calibration_summary': calib_summary,
        'agreement': agreement_report,
        'hard_cases': hard_cases,
        'artifacts': {
            'seed_jsonl': str(seed_jsonl),
            'seed_manifest': str(seed_manifest),
            'calibration_dir': str(calibration_dir),
            'agreement_input_a': str(agreement_a),
            'agreement_input_b': str(agreement_b),
            'final_report': str(final_report),
        },
    }
    final_report.write_text(json.dumps(final, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(final, ensure_ascii=False, indent=2))
    return 0 if final['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
