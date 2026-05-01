#!/usr/bin/env python3
"""Domain-driven 640 tuning: pseudo-gold from DB, fast subset, full validation."""

from __future__ import annotations

import json
import sqlite3
import subprocess
from dataclasses import dataclass
from pathlib import Path

import yaml

ROOT = Path("/root/BirdLense")
CFG_PATH = ROOT / "app" / "app_config" / "user_config.yaml"
DB_PATH = ROOT / "app" / "data" / "db" / "birdlense.db"
OUT_DIR = ROOT / "app" / "data" / "tuning_640_domain"
SUMMARY_PATH = OUT_DIR / "summary.json"
LABELS_PATH = OUT_DIR / "pseudo_gold_labels.json"


def run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, check=False, capture_output=True, text=True)


@dataclass
class VideoMeta:
    video_path: str
    basename: str
    hour: int
    gold_species: list[str]


def _hour_from_path(video_path: str) -> int:
    # .../YYYY/MM/DD/HHMMSS/video.mp4
    parts = video_path.strip("/").split("/")
    if len(parts) >= 2:
        hhmmss = parts[-2]
        if len(hhmmss) >= 2 and hhmmss[:2].isdigit():
            return int(hhmmss[:2])
    return 12


def load_videos_with_gold() -> list[VideoMeta]:
    con = sqlite3.connect(str(DB_PATH))
    try:
        rows = con.execute(
            """
            SELECT
                v.video_path,
                s.name,
                MAX(vs.confidence) AS max_conf
            FROM video v
            JOIN video_species vs ON vs.video_id = v.id
            JOIN species s ON s.id = vs.species_id
            WHERE v.deleted_at IS NULL
              AND COALESCE(vs.frames, '') <> ''
              AND LENGTH(vs.frames) > 20
              AND vs.detection_provider = ?
            GROUP BY v.video_path, s.name
            ORDER BY v.video_path
            """,
            ("yolo",),
        ).fetchall()
    finally:
        con.close()

    by_video: dict[str, dict[str, float]] = {}
    for video_path, species_name, max_conf in rows:
        if not video_path or not species_name:
            continue
        sp = str(species_name).strip()
        if not sp or sp.lower() in {"background", "null", "unknown"}:
            continue
        by_video.setdefault(video_path, {})[sp] = float(max_conf or 0.0)

    out: list[VideoMeta] = []
    for video_path, sp_map in sorted(by_video.items()):
        host_path = ROOT / "app" / str(video_path).lstrip("/")
        if not host_path.is_file():
            continue
        gold_species = sorted(sp_map.keys())
        if not gold_species:
            continue
        out.append(
            VideoMeta(
                video_path="/app/" + str(video_path).lstrip("/"),
                basename=host_path.name,
                hour=_hour_from_path(video_path),
                gold_species=gold_species,
            ),
        )
    return out


def write_labels_sidecar(videos: list[VideoMeta]) -> None:
    payload = {
        "schema_version": 1,
        "gold_by_basename": {v.basename: v.gold_species for v in videos},
    }
    LABELS_PATH.parent.mkdir(parents=True, exist_ok=True)
    LABELS_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def choose_subset(videos: list[VideoMeta], target: int = 14) -> list[VideoMeta]:
    night = [v for v in videos if v.hour >= 20 or v.hour <= 5]
    day = [v for v in videos if not (v.hour >= 20 or v.hour <= 5)]
    multi = [v for v in videos if len(v.gold_species) >= 2]
    single = [v for v in videos if len(v.gold_species) == 1]

    chosen: list[VideoMeta] = []
    # Start with domain-hard clips: multi-species
    chosen.extend(multi[: max(2, target // 4)])
    # Balance day/night
    chosen.extend(night[: max(4, target // 3)])
    chosen.extend(day[: max(4, target // 3)])
    # Fill with single-species clips as FP guard
    for v in single:
        if len(chosen) >= target:
            break
        if v not in chosen:
            chosen.append(v)
    # Final dedup + cap
    dedup: list[VideoMeta] = []
    seen: set[str] = set()
    for v in chosen:
        if v.video_path in seen:
            continue
        seen.add(v.video_path)
        dedup.append(v)
        if len(dedup) >= target:
            break
    return dedup


def apply_profile(profile: dict, base_cfg: dict) -> None:
    cfg = json.loads(json.dumps(base_cfg))
    pr = cfg.setdefault("processor", {})
    models = pr.setdefault("models", {})
    models["binary_openvino"] = "/app/data/weights-cache/best_20260430T193953Z_openvino_model"
    pr["inference_backend"] = "openvino"
    pr["classifier_inference_backend"] = "openvino"
    pr["inference_device"] = "intel:gpu"
    pr["classifier_inference_device"] = "intel:gpu"
    pr["binary_imgsz"] = 640
    pr["adaptive_profiles"] = pr.get("adaptive_profiles") or {}
    if "adaptive_profiles_enabled" in profile:
        pr["adaptive_profiles"]["enabled"] = bool(profile["adaptive_profiles_enabled"])
    for k in (
        "light_gate_enabled",
        "min_center_dist",
        "min_box_size_px",
        "min_confidence_binary_bird",
        "min_confidence_binary_rodent",
        "min_confidence_to_process",
    ):
        if k in profile:
            pr[k] = profile[k]
    with open(CFG_PATH, "w", encoding="utf-8") as fh:
        yaml.safe_dump(cfg, fh, allow_unicode=True, sort_keys=False)


def run_benchmark(report_path: Path, videos: list[VideoMeta]) -> dict:
    report_path.parent.mkdir(parents=True, exist_ok=True)
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
        "--labels-json",
        "/app/data/tuning_640_domain/pseudo_gold_labels.json",
        "--write-report",
        str(report_path).replace(str(ROOT / "app"), "/app"),
    ]
    for v in videos:
        cmd.extend(["--video", v.video_path])
    res = run(cmd)
    if res.returncode != 0:
        return {
            "error": "benchmark_failed",
            "stderr_tail": (res.stderr or "")[-1200:],
            "stdout_tail": (res.stdout or "")[-1200:],
        }
    return json.loads(report_path.read_text(encoding="utf-8"))


def score_report(report_obj: dict) -> dict:
    rows = report_obj.get("videos", [])
    if not rows:
        return {
            "videos": 0,
            "hit_rate": 0.0,
            "recall_mean": 0.0,
            "extra_rate": 0.0,
            "fallback_rate": 0.0,
            "score": -1e9,
        }
    n = len(rows)
    hits = sum(1 for r in rows if int(r.get("fused_track_count", 0)) > 0)
    recalls: list[float] = []
    extra_total = 0
    fallback_total = 0
    fused_total = 0
    for r in rows:
        fused = int(r.get("fused_track_count", 0))
        fused_total += fused
        fallback_total += int(r.get("fallback_count", 0))
        ev = r.get("label_eval") or {}
        rec = ev.get("gold_species_recall")
        if rec is not None:
            recalls.append(float(rec))
        extra_total += len(ev.get("extra_vs_gold") or [])
    hit_rate = hits / n
    recall_mean = (sum(recalls) / len(recalls)) if recalls else 0.0
    extra_rate = extra_total / n
    fallback_rate = (fallback_total / fused_total) if fused_total else 0.0
    score = (
        100.0 * recall_mean
        + 35.0 * hit_rate
        - 22.0 * extra_rate
        - 8.0 * fallback_rate
    )
    return {
        "videos": n,
        "hit_rate": round(hit_rate, 4),
        "recall_mean": round(recall_mean, 4),
        "extra_rate": round(extra_rate, 4),
        "fallback_rate": round(fallback_rate, 4),
        "score": round(score, 4),
    }


def candidate_profiles() -> list[dict]:
    # Domain-aware set: recall-oriented, then balanced anti-FP variants.
    return [
        {
            "id": "r1_recall_max",
            "light_gate_enabled": False,
            "adaptive_profiles_enabled": False,
            "min_center_dist": 0.01,
            "min_box_size_px": 36,
            "min_confidence_binary_bird": 0.28,
            "min_confidence_binary_rodent": 0.18,
            "min_confidence_to_process": 0.24,
        },
        {
            "id": "r2_recall_plus",
            "light_gate_enabled": False,
            "adaptive_profiles_enabled": False,
            "min_center_dist": 0.015,
            "min_box_size_px": 40,
            "min_confidence_binary_bird": 0.30,
            "min_confidence_binary_rodent": 0.20,
            "min_confidence_to_process": 0.26,
        },
        {
            "id": "b1_balanced_low",
            "light_gate_enabled": False,
            "adaptive_profiles_enabled": False,
            "min_center_dist": 0.02,
            "min_box_size_px": 44,
            "min_confidence_binary_bird": 0.32,
            "min_confidence_binary_rodent": 0.22,
            "min_confidence_to_process": 0.28,
        },
        {
            "id": "b2_balanced_mid",
            "light_gate_enabled": False,
            "adaptive_profiles_enabled": True,
            "min_center_dist": 0.025,
            "min_box_size_px": 48,
            "min_confidence_binary_bird": 0.34,
            "min_confidence_binary_rodent": 0.24,
            "min_confidence_to_process": 0.30,
        },
        {
            "id": "g1_guard_fp",
            "light_gate_enabled": True,
            "adaptive_profiles_enabled": True,
            "min_center_dist": 0.03,
            "min_box_size_px": 52,
            "min_confidence_binary_bird": 0.36,
            "min_confidence_binary_rodent": 0.24,
            "min_confidence_to_process": 0.32,
        },
        {
            "id": "g2_guard_fp_plus",
            "light_gate_enabled": True,
            "adaptive_profiles_enabled": True,
            "min_center_dist": 0.035,
            "min_box_size_px": 56,
            "min_confidence_binary_bird": 0.40,
            "min_confidence_binary_rodent": 0.26,
            "min_confidence_to_process": 0.34,
        },
    ]


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    base_cfg = yaml.safe_load(CFG_PATH.read_text(encoding="utf-8")) or {}
    videos = load_videos_with_gold()
    if not videos:
        raise RuntimeError("No videos with pseudo-gold labels found")
    write_labels_sidecar(videos)
    subset = choose_subset(videos, target=14)

    # Ensure benchmark scripts in container are current.
    run(["docker", "cp", str(ROOT / "scripts" / "benchmark-track-regen.py"), "birdlense:/tmp/benchmark-track-regen.py"])
    run(["docker", "cp", str(ROOT / "scripts" / "benchmark_regen_labels.py"), "birdlense:/tmp/benchmark_regen_labels.py"])

    fast_results: list[dict] = []
    for profile in candidate_profiles():
        apply_profile(profile, base_cfg)
        rep = run_benchmark(OUT_DIR / f"fast_{profile['id']}.json", subset)
        row = {
            "profile_id": profile["id"],
            "profile": profile,
        }
        if "error" in rep:
            row["error"] = rep
        else:
            row["metrics"] = score_report(rep)
        fast_results.append(row)

    valid_fast = [r for r in fast_results if "metrics" in r]
    if not valid_fast:
        out = {"error": "all_fast_profiles_failed", "fast_results": fast_results}
        SUMMARY_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 2

    valid_fast.sort(key=lambda r: float(r["metrics"]["score"]), reverse=True)
    top = valid_fast[:2]

    full_results: list[dict] = []
    for cand in top:
        profile = cand["profile"]
        apply_profile(profile, base_cfg)
        rep = run_benchmark(OUT_DIR / f"full_{profile['id']}.json", videos)
        row = {"profile_id": profile["id"], "profile": profile}
        if "error" in rep:
            row["error"] = rep
        else:
            row["metrics"] = score_report(rep)
        full_results.append(row)

    valid_full = [r for r in full_results if "metrics" in r]
    best = None
    if valid_full:
        valid_full.sort(key=lambda r: float(r["metrics"]["score"]), reverse=True)
        best = valid_full[0]
        apply_profile(best["profile"], base_cfg)

    summary = {
        "report": "tuning_640_domain@v1",
        "videos_total": len(videos),
        "videos_subset": len(subset),
        "subset_videos": [v.video_path for v in subset],
        "fast_stage": fast_results,
        "full_stage": full_results,
        "best": best,
    }
    SUMMARY_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
