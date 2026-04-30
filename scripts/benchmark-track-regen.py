#!/usr/bin/env python3
"""Benchmark regenerate-tracks on local videos (reproducible JSON output)."""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone

import cv2

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(_SCRIPT_DIR)


def _resolve_app_paths() -> tuple[str, str]:
    """Checkout: <repo>/app; hub container: flat /app (processor, web, app_config)."""
    hub = '/app'
    if (
        os.path.isdir(os.path.join(hub, 'processor', 'src'))
        and os.path.isdir(os.path.join(hub, 'app_config'))
        and os.path.isfile(os.path.join(hub, 'web', 'app.py'))
    ):
        return hub, os.path.join(hub, 'processor', 'src')
    app_root = os.path.join(_REPO_ROOT, 'app')
    return app_root, os.path.join(app_root, 'processor', 'src')


APP_ROOT, PROCESSOR_SRC = _resolve_app_paths()
SCRIPTS_DIR = _SCRIPT_DIR
if APP_ROOT not in sys.path:
    sys.path.insert(0, APP_ROOT)
if PROCESSOR_SRC not in sys.path:
    sys.path.insert(0, PROCESSOR_SRC)
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from benchmark_regen_labels import (  # noqa: E402
    eval_video_against_gold,
    load_gold_by_basename,
)


def _video_window(path: str) -> tuple[datetime, datetime]:
    """Approximate video wall-clock span from container metadata."""
    cap = cv2.VideoCapture(path)
    try:
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        frames = cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0.0
    finally:
        cap.release()
    duration = max(0.0, float(frames) / float(fps or 30.0))
    start = datetime.now(timezone.utc)
    return start, start + timedelta(seconds=duration)


def main() -> int:
    """Parse CLI, set inference env if requested, run benchmark, print JSON."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '--video',
        action='append',
        required=True,
        help='Video path to benchmark',
    )
    parser.add_argument('--frame-step', type=int, default=2)
    parser.add_argument('--lores-px', type=int, default=640)
    parser.add_argument('--max-runtime-sec', type=int, default=420)
    parser.add_argument('--strategy', default='two_stage')
    parser.add_argument(
        '--inference-backend',
        default='',
        help=(
            'Sets BIRDLENSE_INFERENCE_BACKEND for this run '
            '(e.g. torch, openvino). Empty = env/config.'
        ),
    )
    parser.add_argument(
        '--inference-device',
        default='',
        help=(
            'Sets BIRDLENSE_INFERENCE_DEVICE for this run '
            '(e.g. intel:gpu for OpenVINO on Intel iGPU). Empty = env/config.'
        ),
    )
    parser.add_argument(
        '--labels-json',
        default='',
        help=(
            'Optional gold labels sidecar (schema gold_by_basename@v1). '
            'See benchmark_regen_labels.py docstring.'
        ),
    )
    parser.add_argument(
        '--write-report',
        default='',
        help='Also write the same JSON as stdout to this file (UTF-8).',
    )
    args = parser.parse_args()

    if args.inference_backend:
        be = args.inference_backend.strip().lower()
        os.environ['BIRDLENSE_INFERENCE_BACKEND'] = be

    if args.inference_device:
        os.environ['BIRDLENSE_INFERENCE_DEVICE'] = args.inference_device.strip()

    labels_sidecar_path = (args.labels_json or '').strip()
    gold_map: dict[str, list[str]] | None = None
    if labels_sidecar_path:
        if not os.path.isfile(labels_sidecar_path):
            print(
                json.dumps(
                    {'error': 'labels_json_not_found', 'path': labels_sidecar_path},
                    ensure_ascii=False,
                ),
                file=sys.stderr,
            )
            return 2
        gold_map = load_gold_by_basename(labels_sidecar_path)

    from app_config.app_config import app_config  # noqa: E402
    from detection_fusion import build_fused_video_detections  # noqa: E402
    from inference.selector import resolve_inference_backend  # noqa: E402
    from track_regenerator import (  # noqa: E402
        build_detection_pipeline,
        process_video_for_tracks,
    )

    resolved_backend = resolve_inference_backend(app_config)

    frame_processor, decision_maker = build_detection_pipeline(
        app_config,
        strategy_override=args.strategy,
        for_track_regen=True,
    )
    results: list[dict] = []
    for video_path in args.video:
        start, end = _video_window(video_path)
        raw = process_video_for_tracks(
            video_path,
            lores_size=(args.lores_px, args.lores_px),
            frame_processor=frame_processor,
            decision_maker=decision_maker,
            frame_step=args.frame_step,
            max_runtime_sec=args.max_runtime_sec,
        )
        fused = build_fused_video_detections(
            raw,
            [],
            start_time=start,
            end_time=end,
            app_config=app_config,
        )
        kind_iter = (str(track.get('decision_kind') or 'unknown') for track in fused)
        clf_review_raw = sum(1 for track in raw if bool(track.get('classifier_needs_review')))
        clf_review_fused = sum(1 for track in fused if bool(track.get('classifier_needs_review')))
        row = {
            'video': video_path,
            'raw_track_count': len(raw),
            'fused_track_count': len(fused),
            'species': [track.get('species_name') for track in fused],
            'decision_kind_counts': dict(
                sorted(Counter(kind_iter).items()),
            ),
            'fallback_count': sum(
                (1 for track in fused if bool(track.get('fallback_used'))),
            ),
            'classifier_needs_review_count_raw': clf_review_raw,
            'classifier_needs_review_count_fused': clf_review_fused,
        }
        if gold_map is not None:
            ev = eval_video_against_gold(gold_map, video_path, fused)
            if ev is not None:
                row['label_eval'] = ev
            else:
                row['label_eval'] = {
                    'skipped': True,
                    'reason': 'no_gold_for_basename',
                    'video_basename': os.path.basename(video_path),
                }
        results.append(row)
    out_obj: dict = {
        'report_format': 'benchmark_track_regen@v1',
        'inference_backend': resolved_backend,
        'videos': results,
    }
    if gold_map is not None:
        out_obj['labels_sidecar'] = {
            'path': labels_sidecar_path,
            'schema': 'gold_by_basename@v1',
        }
    text = json.dumps(out_obj, ensure_ascii=False, indent=2)
    print(text)
    write_report = (args.write_report or '').strip()
    if write_report:
        parent = os.path.dirname(os.path.abspath(write_report))
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(write_report, 'w', encoding='utf-8') as fh:
            fh.write(text)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
