#!/usr/bin/env python3
"""Profile OpenVINO device/hint combos and build ov_async_profile_report@v1 (#412)."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_DEFAULT_GLOBS: tuple[str, ...] = ("**/*.mp4", "**/*.mov", "**/*.mkv", "**/*.avi")


@dataclass(frozen=True)
class ProfileSpec:
    name: str
    inference_device: str
    frame_step: int
    lores_px: int
    openvino_profile: str
    openvino_num_requests: int


def _default_profiles() -> list[ProfileSpec]:
    return [
        ProfileSpec(
            name="latency_cpu",
            inference_device="cpu",
            frame_step=2,
            lores_px=640,
            openvino_profile="latency",
            openvino_num_requests=0,
        ),
        ProfileSpec(
            name="throughput_cpu",
            inference_device="cpu",
            frame_step=3,
            lores_px=640,
            openvino_profile="throughput",
            openvino_num_requests=4,
        ),
        ProfileSpec(
            name="throughput_intel_gpu",
            inference_device="intel:gpu",
            frame_step=2,
            lores_px=640,
            openvino_profile="throughput",
            openvino_num_requests=4,
        ),
    ]


def _collect_videos(videos: list[str], videos_root: str | None, max_videos: int) -> list[str]:
    acc: list[str] = []
    for v in videos:
        p = Path(v).expanduser().resolve()
        if p.is_file():
            acc.append(str(p))
    if videos_root:
        root = Path(videos_root).expanduser().resolve()
        if root.is_dir():
            for pat in _DEFAULT_GLOBS:
                for p in sorted(root.glob(pat)):
                    if p.is_file():
                        acc.append(str(p.resolve()))
    out: list[str] = []
    seen: set[str] = set()
    for path in acc:
        if path in seen:
            continue
        seen.add(path)
        out.append(path)
        if len(out) >= max(1, int(max_videos)):
            break
    return out


def _load_json(path: str) -> dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        payload = json.load(f)
    if not isinstance(payload, dict):
        raise ValueError(f"JSON object expected: {path}")
    return payload


def _run_profile(
    *,
    root_dir: str,
    profile: ProfileSpec,
    videos: list[str],
    max_runtime_sec: int,
    labels_json: str | None,
) -> dict[str, Any]:
    cmd: list[str] = [
        "python3",
        os.path.join(root_dir, "scripts", "benchmark-track-regen.py"),
    ]
    for video in videos:
        cmd.extend(["--video", video])
    cmd.extend(
        [
            "--inference-backend",
            "openvino",
            "--inference-device",
            profile.inference_device,
            "--frame-step",
            str(max(1, int(profile.frame_step))),
            "--lores-px",
            str(max(320, int(profile.lores_px))),
            "--max-runtime-sec",
            str(max(30, int(max_runtime_sec))),
        ]
    )
    if labels_json:
        cmd.extend(["--labels-json", labels_json])
    with tempfile.TemporaryDirectory(prefix=f"ovprof_{profile.name}_") as td:
        out_path = os.path.join(td, "benchmark.json")
        cmd.extend(["--write-report", out_path])
        env = os.environ.copy()
        env["BIRDLENSE_INFERENCE_BACKEND"] = "openvino"
        env["BIRDLENSE_INFERENCE_DEVICE"] = profile.inference_device
        env["BIRDLENSE_OPENVINO_PROFILE"] = profile.openvino_profile
        env["BIRDLENSE_OPENVINO_NUM_REQUESTS"] = str(max(0, int(profile.openvino_num_requests)))
        t0 = time.monotonic()
        proc = subprocess.run(
            cmd,
            cwd=root_dir,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        elapsed_s = max(0.0, time.monotonic() - t0)
        if proc.returncode != 0:
            return {
                "profile": profile.name,
                "status": "failed",
                "return_code": proc.returncode,
                "elapsed_seconds": round(elapsed_s, 4),
                "stderr_tail": "\n".join((proc.stderr or "").splitlines()[-20:]),
            }
        payload = _load_json(out_path)
    videos_rows = payload.get("videos") or []
    if not isinstance(videos_rows, list):
        videos_rows = []
    total_runtime = 0.0
    total_tracks = 0
    total_raw_tracks = 0
    label_eval_samples = 0
    label_eval_matches = 0
    for row in videos_rows:
        if not isinstance(row, dict):
            continue
        total_runtime += float(row.get("runtime_seconds") or 0.0)
        total_tracks += int(row.get("fused_track_count") or 0)
        total_raw_tracks += int(row.get("raw_track_count") or 0)
        le = row.get("label_eval")
        if isinstance(le, dict) and not bool(le.get("skipped")):
            label_eval_samples += int(le.get("gold_count") or 0)
            label_eval_matches += int(le.get("matched") or 0)
    recall = (
        float(label_eval_matches) / float(label_eval_samples)
        if label_eval_samples > 0
        else None
    )
    return {
        "profile": profile.name,
        "status": "ok",
        "settings": {
            "inference_backend": "openvino",
            "inference_device": profile.inference_device,
            "openvino_profile": profile.openvino_profile,
            "openvino_num_requests": int(profile.openvino_num_requests),
            "frame_step": int(profile.frame_step),
            "lores_px": int(profile.lores_px),
        },
        "elapsed_seconds": round(elapsed_s, 4),
        "aggregates": {
            "videos": len(videos_rows),
            "runtime_seconds_sum": round(total_runtime, 4),
            "runtime_seconds_mean": round(total_runtime / max(1, len(videos_rows)), 4),
            "fused_track_count_sum": int(total_tracks),
            "raw_track_count_sum": int(total_raw_tracks),
            "label_eval_gold_count_sum": int(label_eval_samples),
            "label_eval_matched_sum": int(label_eval_matches),
            "label_eval_recall": (round(recall, 6) if recall is not None else None),
        },
    }


def _rank_score(row: dict[str, Any]) -> tuple[float, float, int]:
    aggr = row.get("aggregates") if isinstance(row.get("aggregates"), dict) else {}
    mean_s = float(aggr.get("runtime_seconds_mean") or 1e9)
    recall = aggr.get("label_eval_recall")
    recall_val = float(recall) if recall is not None else -1.0
    fused = int(aggr.get("fused_track_count_sum") or 0)
    return (mean_s, -recall_val, -fused)


def build_openvino_async_profile_report(
    *,
    profile_rows: list[dict[str, Any]],
    videos: list[str],
) -> dict[str, Any]:
    ok_rows = [row for row in profile_rows if str(row.get("status")) == "ok"]
    best = min(ok_rows, key=_rank_score) if ok_rows else None
    return {
        "schema": "ov_async_profile_report@v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "inputs": {
            "video_count": len(videos),
            "videos": videos,
        },
        "profiles": profile_rows,
        "best_profile": (
            {
                "name": str(best.get("profile")),
                "settings": dict(best.get("settings") or {}),
                "aggregates": dict(best.get("aggregates") or {}),
            }
            if best is not None
            else None
        ),
        "ok": best is not None,
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", action="append", default=[], help="Absolute/relative video path (repeatable).")
    parser.add_argument(
        "--videos-root",
        default="",
        help="Optional root with benchmark videos; collects common video extensions recursively.",
    )
    parser.add_argument("--max-videos", type=int, default=3, help="Cap videos to keep profiling bounded.")
    parser.add_argument("--max-runtime-sec", type=int, default=420, help="Per-video timeout for benchmark run.")
    parser.add_argument("--labels-json", default="", help="Optional gold labels (gold_by_basename@v1).")
    parser.add_argument(
        "--profile",
        action="append",
        default=[],
        help=(
            "Custom profile name=device,frame_step,lores_px,profile,num_requests ; "
            "e.g. gpu=intel:gpu,2,640,throughput,4"
        ),
    )
    parser.add_argument("--out", required=True, help="Output path for ov_async_profile_report@v1 JSON.")
    return parser.parse_args()


def _parse_custom_profiles(raw_profiles: list[str]) -> list[ProfileSpec]:
    out: list[ProfileSpec] = []
    for raw in raw_profiles:
        text = str(raw or "").strip()
        if "=" not in text:
            continue
        name, data = text.split("=", 1)
        parts = [p.strip() for p in data.split(",")]
        if len(parts) != 5:
            continue
        dev, frame_step, lores_px, profile, num_requests = parts
        try:
            out.append(
                ProfileSpec(
                    name=name.strip() or "custom",
                    inference_device=dev or "auto",
                    frame_step=max(1, int(frame_step)),
                    lores_px=max(320, int(lores_px)),
                    openvino_profile=(profile or "latency"),
                    openvino_num_requests=max(0, int(num_requests or 0)),
                )
            )
        except ValueError:
            continue
    return out


def main() -> int:
    args = _parse_args()
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    videos = _collect_videos(
        args.video or [],
        (args.videos_root or "").strip() or None,
        max_videos=max(1, int(args.max_videos)),
    )
    if not videos:
        raise SystemExit("No videos found: pass --video or --videos-root.")
    labels_json = (args.labels_json or "").strip() or None
    profiles = _parse_custom_profiles(args.profile or [])
    if not profiles:
        profiles = _default_profiles()
    rows: list[dict[str, Any]] = []
    for profile in profiles:
        rows.append(
            _run_profile(
                root_dir=root_dir,
                profile=profile,
                videos=videos,
                max_runtime_sec=max(30, int(args.max_runtime_sec)),
                labels_json=labels_json,
            )
        )
    report = build_openvino_async_profile_report(profile_rows=rows, videos=videos)
    out_path = Path(args.out).expanduser().resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if bool(report.get("ok")) else 3


if __name__ == "__main__":
    raise SystemExit(main())
