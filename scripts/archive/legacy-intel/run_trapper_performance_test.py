#!/usr/bin/env python3
"""TrapperAI OpenVINO performance + quality test on a recording (7 FPS simulation)."""

from __future__ import annotations

import argparse
import json
import sqlite3
import statistics
import sys
import time
from pathlib import Path

import cv2
import numpy as np
import yaml
from ultralytics import YOLO

BIRD_ID = 0
SQUIRREL_ID = 5
TARGET_CLASS_IDS = {BIRD_ID, SQUIRREL_ID}
BIRD_COLOR = (0, 220, 0)  # BGR green
SQUIRREL_COLOR = (0, 140, 255)  # BGR orange


def _norm(name: str) -> str:
    return " ".join(str(name or "").strip().lower().split())


def resolve_video_path(video_id: int, db_path: Path) -> Path | None:
    if not db_path.is_file():
        return None
    con = sqlite3.connect(str(db_path))
    try:
        row = con.execute(
            "SELECT video_path FROM video WHERE id = ?",
            (int(video_id),),
        ).fetchone()
    finally:
        con.close()
    if not row or not row[0]:
        return None
    rel = str(row[0]).strip()
    p = Path(rel)
    if not p.is_absolute():
        p = Path("/app") / rel if rel.startswith("data/") else Path("/app/data") / rel
    return p if p.is_file() else None


def find_fallback_video(db_path: Path) -> tuple[int, Path] | None:
    if not db_path.is_file():
        return None
    con = sqlite3.connect(str(db_path))
    try:
        rows = con.execute(
            "SELECT id, video_path FROM video ORDER BY id DESC LIMIT 80"
        ).fetchall()
    finally:
        con.close()
    for vid, rel in rows:
        if not rel:
            continue
        p = Path(str(rel))
        if not p.is_absolute():
            p = Path("/app") / str(rel) if str(rel).startswith("data/") else Path("/app/data") / str(rel)
        if p.is_file() and p.stat().st_size > 500_000:
            return int(vid), p
    return None


def draw_detections(frame: np.ndarray, boxes, names: dict[int, str], conf_min: float) -> tuple[np.ndarray, int, int]:
    out = frame.copy()
    birds = squirrels = 0
    if boxes is None or len(boxes) == 0:
        return out, 0, 0
    for i in range(len(boxes)):
        cid = int(boxes.cls[i].item())
        if cid not in TARGET_CLASS_IDS:
            continue
        conf = float(boxes.conf[i].item())
        if conf < conf_min:
            continue
        x1, y1, x2, y2 = boxes.xyxy[i].cpu().numpy().astype(int).tolist()
        label = str(names.get(cid, cid))
        if cid == BIRD_ID:
            color = BIRD_COLOR
            birds += 1
        else:
            color = SQUIRREL_COLOR
            squirrels += 1
        cv2.rectangle(out, (x1, y1), (x2, y2), color, 2)
        txt = f"{label} {conf:.2f}"
        (tw, th), _ = cv2.getTextSize(txt, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
        cv2.rectangle(out, (x1, y1 - th - 6), (x1 + tw + 4, y1), color, -1)
        cv2.putText(out, txt, (x1 + 2, y1 - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1, cv2.LINE_AA)
    return out, birds, squirrels


def make_collage(candidates: list[tuple[float, Path]], out_path: Path, cols: int = 5) -> None:
    """candidates: (score, image_path) sorted desc; take up to 10."""
    picks = sorted(candidates, key=lambda x: -x[0])[:10]
    if not picks:
        return
    thumbs: list[np.ndarray] = []
    for _, p in picks:
        im = cv2.imread(str(p))
        if im is None:
            continue
        h, w = im.shape[:2]
        scale = 320 / max(h, w)
        im = cv2.resize(im, (int(w * scale), int(h * scale)))
        thumbs.append(im)
    if not thumbs:
        return
    row_h = max(t.shape[0] for t in thumbs)
    row_w = max(t.shape[1] for t in thumbs)
    rows: list[list[np.ndarray]] = []
    for i in range(0, len(thumbs), cols):
        chunk = thumbs[i : i + cols]
        padded = []
        for t in chunk:
            pad = np.zeros((row_h, row_w, 3), dtype=np.uint8)
            pad[: t.shape[0], : t.shape[1]] = t
            padded.append(pad)
        while len(padded) < cols:
            padded.append(np.zeros((row_h, row_w, 3), dtype=np.uint8))
        rows.append(cv2.hconcat(padded))
    grid = cv2.vconcat(rows)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out_path), grid)


def write_report(
    path: Path,
    *,
    video_id: int,
    video_path: Path,
    metrics: dict,
    perf_status: str,
    quality_note: str,
    verdict: str,
    visual_dir: Path,
    collage_path: Path,
) -> None:
    lines = [
        "# TrapperAI v02.2024 — Performance & Quality Report",
        "",
        f"- **Video ID:** {video_id}",
        f"- **File:** `{video_path}`",
        f"- **Model:** OpenVINO `trapper_ai_v02_2024_openvino_model` @704",
        f"- **Device:** `{metrics.get('device', '')}`",
        f"- **Target stream rate:** 7 FPS (simulated)",
        "",
        "## Performance",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Processed frames | {metrics['processed_frames']} |",
        f"| Avg inference (ms) | {metrics['infer_ms_avg']:.2f} |",
        f"| Min inference (ms) | {metrics['infer_ms_min']:.2f} |",
        f"| Max inference (ms) | {metrics['infer_ms_max']:.2f} |",
        f"| Avg frame total (ms) | {metrics['frame_ms_avg']:.2f} |",
        f"| Avg processing FPS (wall) | {metrics['avg_fps']:.2f} |",
        f"| **Avg infer FPS (steady)** | **{metrics.get('avg_fps_steady', metrics['avg_fps']):.2f}** |",
        f"| Avg inference steady (ms) | {metrics.get('infer_ms_avg_steady', metrics['infer_ms_avg']):.2f} |",
        f"| **Status** | **{perf_status}** |",
        "",
        "## Detections (conf > {conf})".format(conf=metrics["conf_threshold"]),
        "",
        "| Class | Count |",
        "|-------|-------|",
        f"| Bird | {metrics['bird_detections']} |",
        f"| Squirrel | {metrics['squirrel_detections']} |",
        f"| Frames with any target | {metrics['frames_with_detections']} |",
        "",
        "## Artifacts",
        "",
        f"- Visual frames: `{visual_dir}/`",
        f"- Collage (top 10): `{collage_path}`",
        f"- JSON metrics: `{path.with_suffix('.json')}`",
        "",
        "## Quality (automated heuristics)",
        "",
        quality_note,
        "",
        f"## Verdict",
        "",
        f"**{verdict}**",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--video-id", type=int, default=1952)
    ap.add_argument("--video", default="", help="Override video file path")
    ap.add_argument("--db", default="/app/data/db/birdlense.db")
    ap.add_argument("--ov-dir", default="/app/processor/models/detection/weights/trapper_ai_v02_2024_openvino_model")
    ap.add_argument("--out-dir", default="/tmp/trapper_test_1952")
    ap.add_argument("--device", default="cuda:0")
    ap.add_argument("--imgsz", type=int, default=704)
    ap.add_argument("--conf", type=float, default=0.25)
    ap.add_argument("--target-fps", type=float, default=7.0)
    ap.add_argument("--min-frames", type=int, default=100)
    ap.add_argument("--save-every-n", type=int, default=5)
    ap.add_argument("--classes", default="0,5")
    args = ap.parse_args()

    out_dir = Path(args.out_dir)
    visual_dir = out_dir / "results_visual"
    visual_dir.mkdir(parents=True, exist_ok=True)

    video_id = int(args.video_id)
    video_path: Path | None
    if args.video.strip():
        video_path = Path(args.video.strip())
    else:
        video_path = resolve_video_path(video_id, Path(args.db))
    if video_path is None or not video_path.is_file():
        fb = find_fallback_video(Path(args.db))
        if fb is None:
            print(json.dumps({"ok": False, "error": "video_not_found", "video_id": video_id}))
            return 1
        video_id, video_path = fb
        print(f"fallback video_id={video_id} path={video_path}", file=sys.stderr)

    ov = Path(args.ov_dir)
    meta = ov / "metadata.yaml"
    if meta.is_file():
        data = yaml.safe_load(meta.read_text(encoding="utf-8")) or {}
        imgsz_meta = data.get("imgsz")
        if isinstance(imgsz_meta, (list, tuple)) and imgsz_meta:
            if int(imgsz_meta[0]) != int(args.imgsz):
                print(
                    json.dumps({"ok": False, "error": "imgsz_mismatch", "meta": imgsz_meta}),
                    file=sys.stderr,
                )
                return 1

    class_ids = [int(x) for x in str(args.classes).split(",") if x.strip()]
    model = YOLO(str(ov))
    names = {int(k): str(v) for k, v in (model.names or {}).items()}

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        print(json.dumps({"ok": False, "error": "cannot_open_video", "path": str(video_path)}))
        return 1

    src_fps = float(cap.get(cv2.CAP_PROP_FPS) or 25.0)
    frame_step = max(1, int(round(src_fps / float(args.target_fps))))
    total_src_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)

    infer_times: list[float] = []
    frame_times: list[float] = []
    bird_total = squirrel_total = 0
    frames_with_det = 0
    processed = 0
    collage_candidates: list[tuple[float, Path]] = []

    kw_base: dict = {
        "imgsz": int(args.imgsz),
        "conf": float(args.conf),
        "device": str(args.device),
        "verbose": False,
        "classes": class_ids,
    }

    # Warmup: first predict may compile on CPU/GPU switch — exclude from metrics.
    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
    for _ in range(3):
        ok, bgr = cap.read()
        if not ok:
            break
        model.predict(np.asarray(bgr, dtype=np.uint8), **kw_base)
    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)

    fi = 0
    t_run0 = time.perf_counter()
    while processed < int(args.min_frames):
        ok, bgr = cap.read()
        if not ok:
            break
        if fi % frame_step != 0:
            fi += 1
            continue
        fi += 1
        frame = np.asarray(bgr, dtype=np.uint8)
        t0 = time.perf_counter()
        pred = model.predict(frame, **kw_base)
        infer_ms = (time.perf_counter() - t0) * 1000.0
        infer_times.append(infer_ms)

        boxes = pred[0].boxes if pred else None
        vis, nb, ns = draw_detections(frame, boxes, names, float(args.conf))
        bird_total += nb
        squirrel_total += ns
        has_det = (nb + ns) > 0
        if has_det:
            frames_with_det += 1

        frame_ms = (time.perf_counter() - t0) * 1000.0
        frame_times.append(frame_ms)
        processed += 1

        save = has_det or (processed % int(args.save_every_n) == 0)
        if save:
            name = f"f{processed:04d}_b{nb}_s{ns}.jpg"
            out_p = visual_dir / name
            cv2.imwrite(str(out_p), vis)
            score = float(nb + ns) * 10.0
            if boxes is not None and len(boxes):
                score += float(boxes.conf.max().item()) if hasattr(boxes.conf, "max") else 0.0
            collage_candidates.append((score, out_p))

        if total_src_frames > 0 and fi >= total_src_frames:
            break

    cap.release()
    wall_s = max(time.perf_counter() - t_run0, 1e-6)
    avg_fps = processed / wall_s if processed else 0.0

    if not infer_times:
        print(json.dumps({"ok": False, "error": "no_frames_processed"}))
        return 1

    # Drop outliers >3× median (compile spikes).
    med = statistics.median(infer_times)
    infer_clean = [t for t in infer_times if t <= max(med * 3.0, 500.0)]
    if len(infer_clean) < max(10, len(infer_times) // 2):
        infer_clean = infer_times
    infer_ms_avg_clean = statistics.mean(infer_clean)
    avg_fps_steady = 1000.0 / infer_ms_avg_clean if infer_ms_avg_clean > 0 else 0.0

    hit_rate = frames_with_det / processed if processed else 0.0
    false_bg_heuristic = "низкая" if hit_rate < 0.85 else "возможны ложные на фоне (много кадров с детекциями)"
    miss_heuristic = (
        "явных пропусков по выборке не видно"
        if frames_with_det >= processed * 0.15
        else "мало кадров с целями — возможны пропуски или пустой клип"
    )
    quality_note = (
        f"- Доля кадров с Bird/Squirrel: **{hit_rate * 100:.1f}%** ({frames_with_det}/{processed})\n"
        f"- Ложные на фоне (эвристика): {false_bg_heuristic}\n"
        f"- Пропуски (эвристика): {miss_heuristic}\n"
        f"- Коллаж: 10 кадров с наибольшим числом детекций → `results_visual/collage_top10.jpg`"
    )

    collage_path = visual_dir / "collage_top10.jpg"
    make_collage(collage_candidates, collage_path)

    # Go/No-Go on steady-state infer FPS (7 FPS target, PASS if >=10).
    if avg_fps_steady >= 10.0:
        perf_status = "PASS"
    elif avg_fps_steady < 7.0:
        perf_status = "FAIL"
    else:
        perf_status = "MARGINAL"

    if perf_status == "PASS" and frames_with_det >= max(5, processed // 10):
        verdict = "Готово к прод-эксплуатации на 7 FPS"
    elif perf_status == "FAIL":
        verdict = "Требуется оптимизация (производительность ниже 7 FPS)"
    else:
        verdict = "Требуется оптимизация (производительность или качество детекции)"

    metrics = {
        "ok": True,
        "video_id": video_id,
        "video_path": str(video_path),
        "device": args.device,
        "imgsz": args.imgsz,
        "conf_threshold": args.conf,
        "target_fps_sim": args.target_fps,
        "source_fps": src_fps,
        "frame_step": frame_step,
        "processed_frames": processed,
        "infer_ms_avg": statistics.mean(infer_times),
        "infer_ms_avg_steady": infer_ms_avg_clean,
        "infer_ms_min": min(infer_clean),
        "infer_ms_max": max(infer_clean),
        "frame_ms_avg": statistics.mean(frame_times),
        "avg_fps": avg_fps,
        "avg_fps_steady": avg_fps_steady,
        "perf_status": perf_status,
        "bird_detections": bird_total,
        "squirrel_detections": squirrel_total,
        "frames_with_detections": frames_with_det,
        "visual_dir": str(visual_dir),
        "collage": str(collage_path),
        "verdict": verdict,
    }

    json_path = out_dir / "metrics.json"
    json_path.write_text(json.dumps(metrics, indent=2, ensure_ascii=False), encoding="utf-8")
    report_path = out_dir / "report.md"
    write_report(
        report_path,
        video_id=video_id,
        video_path=video_path,
        metrics=metrics,
        perf_status=perf_status,
        quality_note=quality_note,
        verdict=verdict,
        visual_dir=visual_dir,
        collage_path=collage_path,
    )

    print(json.dumps(metrics, ensure_ascii=False))
    print(f"\nReport: {report_path}", file=sys.stderr)
    return 0 if perf_status != "FAIL" else 2


if __name__ == "__main__":
    raise SystemExit(main())
