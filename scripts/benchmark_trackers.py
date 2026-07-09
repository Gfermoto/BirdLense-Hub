#!/usr/bin/env python3
"""SOTA-12: compare tracker presets on golden clips (stability metrics, no full MOTA)."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]


def _resolve_app_paths() -> tuple[str, str]:
    hub = "/app"
    if Path(hub, "processor", "src").is_dir():
        return hub, str(Path(hub, "processor", "src"))
    app_root = str(REPO / "app")
    return app_root, str(REPO / "app" / "processor" / "src")


def _run_clip(
    video_path: Path,
    *,
    tracker_preset: str,
    frame_step: int,
    max_runtime_sec: int,
) -> dict[str, Any]:
    app_root, proc_src = _resolve_app_paths()
    if app_root not in sys.path:
        sys.path.insert(0, app_root)
    if proc_src not in sys.path:
        sys.path.insert(0, proc_src)

    from app_config.app_config import app_config
    from track_regenerator import build_detection_pipeline, process_video_for_tracks
    from tracker_registry import resolve_tracker_preset

    old_tracker = app_config.get("processor.tracker")
    try:
        app_config.set("processor.tracker", tracker_preset)
        resolved = resolve_tracker_preset(tracker_preset)
        fp, dm = build_detection_pipeline(app_config, for_track_regen=True)
        metrics: dict[str, Any] = {"tracker_preset": tracker_preset, "tracker_resolved": resolved}
        t0 = time.monotonic()
        process_video_for_tracks(
            str(video_path),
            frame_processor=fp,
            decision_maker=dm,
            frame_step=frame_step,
            max_runtime_sec=max_runtime_sec,
            metrics_out=metrics,
        )
        metrics["wall_seconds"] = round(time.monotonic() - t0, 4)
        return metrics
    finally:
        if old_tracker is not None:
            app_config.set("processor.tracker", old_tracker)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clip", type=Path, required=True)
    parser.add_argument(
        "--presets",
        default="bytetrack_birdlense,botsort_birdlense",
        help="Comma-separated tracker_registry preset ids",
    )
    parser.add_argument("--frame-step", type=int, default=6)
    parser.add_argument("--max-runtime-sec", type=int, default=600)
    parser.add_argument("--write-report", type=Path, default="")
    args = parser.parse_args()

    if not args.clip.is_file():
        print(f"FAIL: clip not found: {args.clip}", file=sys.stderr)
        return 1

    presets = [p.strip() for p in args.presets.split(",") if p.strip()]
    report: dict[str, Any] = {
        "report_format": "benchmark_trackers@v1",
        "clip": str(args.clip),
        "frame_step": args.frame_step,
        "presets": {},
    }
    baseline_key = "bytetrack_birdlense"
    baseline_fused = 0

    for preset in presets:
        print(f"tracker {preset}: {args.clip}", flush=True)
        metrics = _run_clip(
            args.clip,
            tracker_preset=preset,
            frame_step=args.frame_step,
            max_runtime_sec=args.max_runtime_sec,
        )
        report["presets"][preset] = metrics
        if preset == baseline_key:
            baseline_fused = int(metrics.get("fused_track_count") or 0)

    for preset, metrics in report["presets"].items():
        fused = int(metrics.get("fused_track_count") or 0)
        if baseline_fused > 0 and preset != baseline_key:
            metrics["recall_ratio_vs_bytetrack"] = round(fused / float(baseline_fused), 4)
        metrics["tracking_unified_with_live"] = bool(metrics.get("tracking_unified_with_live"))

    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.write_report:
        args.write_report.parent.mkdir(parents=True, exist_ok=True)
        args.write_report.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
