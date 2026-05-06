#!/usr/bin/env python3
"""Sparse-проход записей через COCO pretrained YOLO (Ultralytics), только класс 14 — bird.

По умолчанию модель ``yolo11n.pt`` (автоскачаивается Ultralytics при первом запуске).
Сеть обучена на MS COCO, не Birdlense-binary.

Пример::

    docker exec -e PYTHONPATH=/app:/app/web:/app/processor/src \\
      birdlense python3 /app/scripts/diag_coco_bird_frames.py --video-id 1048 --video-id 1055
"""

from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from pathlib import Path


def _bootstrap_paths() -> None:
    if os.path.isdir("/app"):
        for p in ("/app/web", "/app/processor/src", "/app"):
            if p not in sys.path:
                sys.path.insert(0, p)
        return
    repo = Path(__file__).resolve().parents[1]
    app_root = repo / "app"
    if app_root.is_dir():
        if str(app_root) not in sys.path:
            sys.path.insert(0, str(app_root))
        for sub in ("web", "processor/src"):
            sp = app_root / sub
            if sp.is_dir():
                sys.path.insert(0, str(sp))


_bootstrap_paths()

import cv2  # noqa: E402
import numpy as np  # noqa: E402


def _default_db_path() -> str:
    p = "/app/data/db/birdlense.db"
    if os.path.isfile(p):
        return p
    root = Path(__file__).resolve().parents[1] / "app" / "data" / "db" / "birdlense.db"
    return str(root)


def resolve_video_row(db_path: str, video_id: int) -> tuple[int, str] | None:
    conn = sqlite3.connect(db_path)
    row = conn.execute("SELECT id, video_path FROM video WHERE id = ?", (video_id,)).fetchone()
    conn.close()
    if not row:
        return None
    return int(row[0]), str(row[1])


def _bird_stats_from_boxes(bx, coco_cls: int) -> tuple[int, float]:
    """Число боксов класса coco_cls и max conf по ним."""
    if bx is None or len(bx) == 0:
        return 0, 0.0
    cls_np = bx.cls.detach().cpu().numpy().astype(int)
    conf_np = bx.conf.detach().cpu().numpy()
    mask = cls_np == int(coco_cls)
    cnt = int(np.sum(mask))
    if cnt == 0:
        return 0, 0.0
    mx = float(np.max(conf_np[mask]))
    return cnt, mx


def sparse_sweep_bird_only(
    model,
    cap: cv2.VideoCapture,
    positions: list[int],
    imgsz: int,
    conf_th: float,
    coco_cls: int,
    label: str,
) -> dict:
    best_conf = 0.0
    best_frame = -1
    best_n = 0
    for p in positions:
        cap.set(cv2.CAP_PROP_POS_FRAMES, p)
        ok, fr = cap.read()
        if not ok:
            print(f"{label} frame {p}: read_failed")
            continue
        img = cv2.resize(fr, (imgsz, imgsz))
        pr = model.predict(img, conf=conf_th, imgsz=imgsz, verbose=False)
        bx = pr[0].boxes
        nb, mx = _bird_stats_from_boxes(bx, coco_cls)
        print(f"{label} frame {p:4d} bird_boxes {nb} bird_maxconf {mx:.5f}")
        if mx > best_conf:
            best_conf, best_frame, best_n = mx, p, nb
    summary = {"bird_maxconf": best_conf, "frame": int(best_frame), "bird_n_boxes": int(best_n)}
    print(f"{label}_BIRD_BEST", summary)
    return summary


def main() -> int:
    ap = argparse.ArgumentParser(description="COCO YOLO — только класс bird (14) на кадрах записи")
    ap.add_argument("--video-id", type=int, action="append", required=True)
    ap.add_argument("--db", type=str, default=None)
    ap.add_argument(
        "--model",
        type=str,
        default="yolo11n.pt",
        help="Ultralytics detect weights (COCO), скачается при необходимости",
    )
    ap.add_argument("--imgsz", type=int, default=640)
    ap.add_argument("--sparse-conf", type=float, default=0.001, help="нижний порог predict (фильтр по cls отдельно)")
    ap.add_argument("--coco-cls", type=int, default=14, help="индекс COCO в порядке Ultralytics / yolo11n (14=bird)")
    args = ap.parse_args()

    from ultralytics import YOLO  # noqa: PLC0415

    print("loading", args.model, flush=True)
    model = YOLO(args.model)
    names = model.names
    nm = names.get(args.coco_cls) if isinstance(names, dict) else None
    bird_ok = nm is not None and "bird" in str(nm).lower()
    if not bird_ok:
        print(f"WARN: coco_cls={args.coco_cls} mapped to name={nm!r} (expect class name containing 'bird')")

    db_path = args.db or _default_db_path()
    if not os.path.isfile(db_path):
        print("ERROR: sqlite not found:", db_path, file=sys.stderr)
        return 2

    os.environ.setdefault("DATA_DIR", os.path.dirname(os.path.dirname(db_path)))
    from data_paths import resolve_recording_video_file  # noqa: WPS433

    print(
        "COCO_diag",
        {
            "model": args.model,
            "coco_cls": args.coco_cls,
            "coco_name": nm,
            "imgsz": args.imgsz,
            "sparse_conf": args.sparse_conf,
        },
    )

    for vid in args.video_id:
        print("=== video_id", vid, "===")
        row = resolve_video_row(db_path, vid)
        if not row:
            print("ERROR: video id not found:", vid, file=sys.stderr)
            continue
        _, rel = row
        full = resolve_recording_video_file(rel)
        if not full or not os.path.isfile(full):
            print("ERROR: file missing:", rel, "→", full, file=sys.stderr)
            continue
        print("relative_path", rel)
        print("full_path", full)

        cap = cv2.VideoCapture(full)
        n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        print("frames", n, "fps", fps)
        if n <= 0:
            positions = [0]
        else:
            step = max(1, n // 24)
            positions = list(range(0, n, step))
            if n - 1 not in positions:
                positions.append(n - 1)

        prefix = f"COCO_bird_cls{args.coco_cls}_{Path(args.model).name}"
        sparse_sweep_bird_only(
            model,
            cap,
            positions,
            args.imgsz,
            args.sparse_conf,
            args.coco_cls,
            prefix,
        )
        cap.release()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
