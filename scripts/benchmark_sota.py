#!/usr/bin/env python3
"""SOTA-09: automated benchmark harness on golden clips 1816 (noise/FP) and 1819 (birds/recall)."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
DEFAULT_BASELINE = REPO / "benchmarks" / "golden_baseline.json"
DEFAULT_MANIFEST = REPO / "benchmarks" / "golden_clips.json"


def _resolve_app_paths() -> tuple[str, str]:
    hub = "/app"
    if (
        Path(hub, "processor", "src").is_dir()
        and Path(hub, "app_config").is_dir()
        and Path(hub, "web", "app.py").is_file()
    ):
        return hub, str(Path(hub, "processor", "src"))
    app_root = str(REPO / "app")
    return app_root, str(REPO / "app" / "processor" / "src")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _metric_int(metrics: dict[str, Any], key: str) -> int:
    try:
        return int(metrics.get(key) or 0)
    except (TypeError, ValueError):
        return 0


def evaluate_clip(
    clip_id: str,
    metrics: dict[str, Any],
    *,
    thresholds: dict[str, Any],
    baseline_metrics: dict[str, Any],
) -> list[str]:
    """Return list of failure messages (empty = pass)."""
    failures: list[str] = []
    th = thresholds.get(clip_id) or {}
    base = baseline_metrics.get(clip_id) or {}

    fused = _metric_int(metrics, "fused_track_count")
    accepted = _metric_int(metrics, "yolo_accepted_boxes_total")
    species_n = _metric_int(metrics, "species_detected_count")
    frames_tracks = _metric_int(metrics, "frames_with_tracks")
    base_fused = max(0, _metric_int(base, "fused_track_count"))

    if clip_id == "1816":
        max_tracks = int(th.get("max_fused_track_count", 0))
        if fused > max_tracks:
            failures.append(f"1816 FP: fused_track_count={fused} > max {max_tracks}")
        max_acc = int(th.get("max_yolo_accepted_boxes_total", 0))
        if accepted > max_acc:
            failures.append(f"1816 FP: yolo_accepted_boxes_total={accepted} > max {max_acc}")
        max_sp = int(th.get("max_species_detected_count", 0))
        if species_n > max_sp:
            failures.append(f"1816 FP: species_detected_count={species_n} > max {max_sp}")
    elif clip_id == "1819":
        min_tracks = int(th.get("min_fused_track_count", 1))
        if fused < min_tracks:
            failures.append(f"1819 recall: fused_track_count={fused} < min {min_tracks}")
        min_frames = int(th.get("min_frames_with_tracks", 1))
        if frames_tracks < min_frames:
            failures.append(f"1819 recall: frames_with_tracks={frames_tracks} < min {min_frames}")
        min_sp = int(th.get("min_species_detected_count", 1))
        if species_n < min_sp:
            failures.append(f"1819 recall: species_detected_count={species_n} < min {min_sp}")
        ratio = float(th.get("min_recall_ratio", 0.9))
        if base_fused > 0:
            recall = float(fused) / float(base_fused)
            if recall < ratio:
                failures.append(
                    f"1819 recall: ratio={recall:.3f} < min_recall_ratio={ratio} "
                    f"(baseline fused={base_fused}, current={fused})"
                )
        elif fused < min_tracks:
            failures.append("1819 recall: no baseline fused_track_count and current below min")
        max_switches = int(th.get("max_track_id_switches", 999999))
        switches = _metric_int(metrics, "track_id_switches_count")
        if switches > max_switches:
            failures.append(
                f"1819 stability: track_id_switches_count={switches} > max {max_switches}"
            )
        min_dur = float(th.get("min_avg_track_duration_sec", 0.0))
        dur = float(metrics.get("avg_track_duration_sec") or 0.0)
        if min_dur > 0 and dur < min_dur:
            failures.append(
                f"1819 stability: avg_track_duration_sec={dur:.3f} < min {min_dur}"
            )
    return failures


def run_benchmark_on_clip(
    video_path: Path,
    *,
    frame_step: int,
    max_runtime_sec: int,
) -> dict[str, Any]:
    app_root, proc_src = _resolve_app_paths()
    if app_root not in sys.path:
        sys.path.insert(0, app_root)
    if proc_src not in sys.path:
        sys.path.insert(0, proc_src)

    from track_regenerator import build_detection_pipeline, process_video_for_tracks  # type: ignore

    fp, dm = build_detection_pipeline(
        __import__("app_config.app_config", fromlist=["app_config"]).app_config,
        for_track_regen=True,
    )
    metrics: dict[str, Any] = {}
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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE)
    parser.add_argument("--db", default=os.environ.get("BIRDLENSE_DB", str(REPO / "app/data/db/birdlense.db")))
    parser.add_argument("--clip-1816", default=os.environ.get("SOTA_GOLDEN_CLIP_1816", "").strip())
    parser.add_argument("--clip-1819", default=os.environ.get("SOTA_GOLDEN_CLIP_1819", "").strip())
    parser.add_argument("--frame-step", type=int, default=int(os.environ.get("SOTA_BENCHMARK_FRAME_STEP", "6")))
    parser.add_argument("--max-runtime-sec", type=int, default=int(os.environ.get("SOTA_BENCHMARK_MAX_RUNTIME_SEC", "600")))
    parser.add_argument("--skip-if-missing", action="store_true")
    parser.add_argument("--smoke", action="store_true", help="Use smoke baseline + same clip for both if only one path set")
    parser.add_argument("--update-baseline", action="store_true")
    parser.add_argument("--write-report", default="", help="Write JSON report path")
    parser.add_argument("--validate-config-only", action="store_true")
    args = parser.parse_args()

    if not args.manifest.is_file():
        print(f"FAIL: manifest not found: {args.manifest}", file=sys.stderr)
        return 1
    if not args.baseline.is_file():
        print(f"FAIL: baseline not found: {args.baseline}", file=sys.stderr)
        return 1

    baseline_doc = load_json(args.baseline)
    if args.smoke:
        smoke_path = REPO / "benchmarks" / "golden_baseline_smoke.json"
        if smoke_path.is_file():
            baseline_doc = load_json(smoke_path)

    if args.validate_config_only:
        print(json.dumps({"ok": True, "manifest": str(args.manifest), "baseline": str(args.baseline)}, indent=2))
        return 0

    sys.path.insert(0, str(REPO / "scripts"))
    from fetch_golden_clips import resolve_clip_path  # type: ignore

    if args.clip_1816:
        os.environ.setdefault("SOTA_GOLDEN_CLIP_1816", args.clip_1816)
    if args.clip_1819:
        os.environ.setdefault("SOTA_GOLDEN_CLIP_1819", args.clip_1819)

    db = Path(args.db)
    paths: dict[str, Path] = {}
    for clip_id in ("1816", "1819"):
        p = resolve_clip_path(clip_id, db=db)
        if p is not None:
            paths[clip_id] = p

    if args.smoke and len(paths) < 2:
        smoke = os.environ.get("SOTA_SMOKE_CLIP", "").strip()
        if not smoke:
            smoke_path = REPO / ".artifacts" / "smoke_clip.mp4"
            if smoke_path.is_file():
                smoke = str(smoke_path)
        if smoke and Path(smoke).is_file():
            sp = Path(smoke).resolve()
            paths.setdefault("1816", sp)
            paths.setdefault("1819", sp)

    missing = [cid for cid in ("1816", "1819") if cid not in paths]
    if missing:
        msg = (
            f"Golden clips missing: {missing}. "
            "Set SOTA_GOLDEN_CLIP_1816/1819, run scripts/fetch-golden-clips.py, "
            "or place files under benchmarks/fixtures/."
        )
        if args.skip_if_missing:
            print(f"SKIP: {msg}", file=sys.stderr)
            return 0
        print(f"FAIL: {msg}", file=sys.stderr)
        return 2

    thresholds = baseline_doc.get("thresholds") or {}
    baseline_metrics = baseline_doc.get("metrics") or {}
    report_clips: dict[str, Any] = {}
    all_failures: list[str] = []

    for clip_id, video_path in paths.items():
        print(f"benchmark {clip_id}: {video_path}", flush=True)
        metrics = run_benchmark_on_clip(
            video_path,
            frame_step=args.frame_step,
            max_runtime_sec=args.max_runtime_sec,
        )
        failures = evaluate_clip(
            clip_id,
            metrics,
            thresholds=thresholds,
            baseline_metrics=baseline_metrics,
        )
        status = "PASS" if not failures else "FAIL"
        report_clips[clip_id] = {
            "video": str(video_path),
            "status": status,
            "metrics": metrics,
            "failures": failures,
        }
        for line in failures:
            print(f"  {line}", file=sys.stderr)
        if not failures:
            print(
                f"  PASS fused={metrics.get('fused_track_count')} "
                f"species={metrics.get('species_detected_count')} "
                f"fps={metrics.get('processing_fps')}",
            )
        all_failures.extend(failures)

    report = {
        "report_format": "benchmark_sota@v1",
        "baseline": str(args.baseline),
        "clips": report_clips,
        "overall": "PASS" if not all_failures else "FAIL",
    }

    if args.update_baseline and not all_failures:
        updated = dict(baseline_doc)
        updated["metrics"] = {cid: report_clips[cid]["metrics"] for cid in report_clips}
        updated["updated_at"] = time.strftime("%Y-%m-%d", time.gmtime())
        args.baseline.write_text(json.dumps(updated, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"Updated baseline: {args.baseline}")

    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.write_report:
        out = Path(args.write_report)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text + "\n", encoding="utf-8")
    print(text)

    return 1 if all_failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
