#!/usr/bin/env python3
"""Server-side profile tuning on DB clips with binary_imgsz=640."""

from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import time
from pathlib import Path

import yaml

ROOT = Path("/root/BirdLense")
CFG_PATH = ROOT / "app" / "app_config" / "user_config.yaml"
DB_PATH = ROOT / "app" / "data" / "db" / "birdlense.db"
OUT_BASE = ROOT / "app" / "data" / "tuning_640_profiles"
SUMMARY_PATH = ROOT / "app" / "data" / "tuning_640_summary.json"

PROFILES = [
    {
        "id": "p640_strict",
        "settings": {
            "light_gate_enabled": True,
            "min_center_dist": 0.035,
            "binary_imgsz": 640,
            "min_confidence_binary_bird": 0.40,
        },
    },
    {
        "id": "p640_relaxed",
        "settings": {
            "light_gate_enabled": False,
            "min_center_dist": 0.02,
            "binary_imgsz": 640,
            "min_confidence_binary_bird": 0.34,
        },
    },
]


def run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, check=False, capture_output=True, text=True)


def restart_container() -> None:
    run(["docker", "restart", "birdlense"])
    for _ in range(45):
        r = run(["docker", "exec", "birdlense", "curl", "-sf", "http://127.0.0.1:8000/api/ui/health"])
        if r.returncode == 0:
            return
        time.sleep(2)
    raise RuntimeError("container health timeout")


def copy_bench_scripts() -> None:
    run(["docker", "cp", str(ROOT / "scripts" / "benchmark-track-regen.py"), "birdlense:/tmp/benchmark-track-regen.py"])
    run(["docker", "cp", str(ROOT / "scripts" / "benchmark_regen_labels.py"), "birdlense:/tmp/benchmark_regen_labels.py"])


def list_videos() -> list[str]:
    con = sqlite3.connect(str(DB_PATH))
    try:
        rows = con.execute(
            """
            SELECT DISTINCT v.video_path
            FROM video v
            JOIN video_species vs ON vs.video_id=v.id
            WHERE v.deleted_at IS NULL
              AND vs.detection_provider=?
              AND vs.frames IS NOT NULL
              AND LENGTH(vs.frames) > 20
            ORDER BY v.video_path
            """,
            ("yolo",),
        ).fetchall()
    finally:
        con.close()

    videos: list[str] = []
    for (vp,) in rows:
        p = "/app/" + str(vp).lstrip("/")
        if Path(ROOT / "app" / str(vp)).is_file():
            videos.append(p)
    return videos


def apply_profile(profile: dict, base_cfg: dict) -> None:
    cfg = json.loads(json.dumps(base_cfg))
    pr = cfg.setdefault("processor", {})
    settings = profile["settings"]
    for k, v in settings.items():
        pr[k] = v
    pr["inference_backend"] = "openvino"
    pr["classifier_inference_backend"] = "openvino"
    pr["inference_device"] = "intel:gpu"
    pr["classifier_inference_device"] = "intel:gpu"
    pr.setdefault("models", {})["binary_openvino"] = "/app/data/weights-cache/best_20260430T193953Z_openvino_model"
    with open(CFG_PATH, "w", encoding="utf-8") as fh:
        yaml.safe_dump(cfg, fh, allow_unicode=True, sort_keys=False)


def run_profile(profile: dict, videos: list[str]) -> dict:
    out_dir = OUT_BASE / profile["id"]
    out_dir.mkdir(parents=True, exist_ok=True)
    chunk_size = 8
    all_rows: list[dict] = []
    chunk_reports: list[str] = []
    for i in range(0, len(videos), chunk_size):
        chunk = videos[i : i + chunk_size]
        report = out_dir / f"chunk_{i//chunk_size:02d}.json"
        cmd = [
            "docker",
            "exec",
            "birdlense",
            "python3",
            "/tmp/benchmark-track-regen.py",
            "--frame-step",
            "1",
            "--lores-px",
            "640",
            "--max-runtime-sec",
            "240",
            "--write-report",
            str(report).replace(str(ROOT / "app"), "/app"),
        ]
        for v in chunk:
            cmd.extend(["--video", v])
        res = run(cmd)
        if res.returncode != 0:
            return {
                "id": profile["id"],
                "settings": profile["settings"],
                "error": "chunk_failed",
                "stderr_tail": (res.stderr or "")[-500:],
                "chunk_index": i // chunk_size,
            }
        data = json.loads(report.read_text(encoding="utf-8"))
        rows = data.get("videos", [])
        all_rows.extend(rows)
        chunk_reports.append(str(report))

    nonzero = sum(1 for r in all_rows if int(r.get("fused_track_count", 0)) > 0)
    fused_sum = sum(int(r.get("fused_track_count", 0)) for r in all_rows)
    raw_sum = sum(int(r.get("raw_track_count", 0)) for r in all_rows)
    return {
        "id": profile["id"],
        "settings": profile["settings"],
        "clips_total": len(all_rows),
        "clips_nonzero": nonzero,
        "clips_zero": len(all_rows) - nonzero,
        "raw_sum": raw_sum,
        "fused_sum": fused_sum,
        "chunk_reports": chunk_reports,
    }


def pick_best(results: list[dict]) -> dict:
    ok = [r for r in results if "error" not in r]
    if not ok:
        return {"error": "no_successful_profiles"}
    ok.sort(key=lambda r: (int(r.get("clips_nonzero", 0)), -int(r.get("fused_sum", 0))), reverse=True)
    return ok[0]


def main() -> int:
    OUT_BASE.mkdir(parents=True, exist_ok=True)
    base_cfg = yaml.safe_load(CFG_PATH.read_text(encoding="utf-8")) or {}
    videos = list_videos()
    if not videos:
        raise RuntimeError("no videos for tuning")

    results: list[dict] = []
    for profile in PROFILES:
        apply_profile(profile, base_cfg)
        restart_container()
        copy_bench_scripts()
        results.append(run_profile(profile, videos))

    best = pick_best(results)
    if "id" in best:
        chosen = next(p for p in PROFILES if p["id"] == best["id"])
        apply_profile(chosen, base_cfg)
        restart_container()

    out = {
        "report": "tuning_640_profiles@v1",
        "profiles": results,
        "best": best,
    }
    SUMMARY_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
