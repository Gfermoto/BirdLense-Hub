#!/usr/bin/env python3
"""Run a reproducible regenerate-tracks benchmark on one or more local videos."""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone

import cv2

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP_ROOT = os.path.join(ROOT, 'app')
PROCESSOR_SRC = os.path.join(ROOT, 'app', 'processor', 'src')
if APP_ROOT not in sys.path:
    sys.path.insert(0, APP_ROOT)
if PROCESSOR_SRC not in sys.path:
    sys.path.insert(0, PROCESSOR_SRC)

from app_config.app_config import app_config  # noqa: E402
from detection_fusion import build_fused_video_detections  # noqa: E402
from track_regenerator import build_detection_pipeline, process_video_for_tracks  # noqa: E402


def _video_window(path: str) -> tuple[datetime, datetime]:
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
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--video', action='append', required=True, help='Video path to benchmark')
    parser.add_argument('--frame-step', type=int, default=2)
    parser.add_argument('--lores-px', type=int, default=640)
    parser.add_argument('--max-runtime-sec', type=int, default=420)
    parser.add_argument('--strategy', default='two_stage')
    args = parser.parse_args()

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
        results.append(
            {
                'video': video_path,
                'raw_track_count': len(raw),
                'fused_track_count': len(fused),
                'species': [track.get('species_name') for track in fused],
                'decision_kind_counts': dict(
                    sorted(Counter(str(track.get('decision_kind') or 'unknown') for track in fused).items()),
                ),
                'fallback_count': sum(1 for track in fused if bool(track.get('fallback_used'))),
            },
        )
    print(json.dumps({'videos': results}, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
