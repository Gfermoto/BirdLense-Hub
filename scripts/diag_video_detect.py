#!/usr/bin/env python3
"""Диагностика YOLO по записи SQLite: sparse predict + опционально полный track regen.

Запуск в контейнере hub::

    docker exec birdlense PYTHONPATH=/app:/app/web:/app/processor/src \\
      python3 /app/scripts/diag_video_detect.py --video-id 1055 --video-id 1048

По умолчанию torch: ``best.pt`` и ``last.pt`` в ``detection/weights`` (если есть).

Подгонка кадра под YOLO — **letterbox** (как live/track_regen), не ``cv2.resize`` во весь квадрат.

``PYTHONPATH``: ``/app:/app/web:/app/processor/src``.
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
        wp = app_root / "web"
        pp = app_root / "processor" / "src"
        if wp.is_dir() and str(wp) not in sys.path:
            sys.path.insert(0, str(wp))
        if pp.is_dir() and str(pp) not in sys.path:
            sys.path.insert(0, str(pp))


_bootstrap_paths()

import cv2  # noqa: E402

from yolo_geometry import letterbox_bgr_to_wh  # noqa: E402


def _default_db_path() -> str:
    p = "/app/data/db/birdlense.db"
    if os.path.isfile(p):
        return p
    root = Path(__file__).resolve().parents[1] / "app" / "data" / "db" / "birdlense.db"
    return str(root)


def detection_weights_dir() -> Path:
    if os.path.isdir("/app"):
        return Path("/app/processor/models/detection/weights")
    return Path(__file__).resolve().parents[1] / "app" / "processor" / "models" / "detection" / "weights"


def resolve_torch_binary_paths(extra: list[str] | None) -> list[Path]:
    wd = detection_weights_dir()
    out: list[Path] = []
    if extra:
        for s in extra:
            p = Path(s)
            if not p.is_absolute():
                p = wd / p
            if p.is_file():
                out.append(p)
        return out
    for name in ("best.pt", "last.pt"):
        p = wd / name
        if p.is_file():
            out.append(p)
    return out


def sparse_sweep_maxconf(
    model,
    cap: cv2.VideoCapture,
    positions: list[int],
    imgsz: int,
    conf_th: float,
    prefix: str,
) -> dict[str, float | int]:
    best_conf = 0.0
    best_frame = -1
    best_n = 0
    for p in positions:
        cap.set(cv2.CAP_PROP_POS_FRAMES, p)
        ok, fr = cap.read()
        if not ok:
            print(f"{prefix} frame {p}: read_failed")
            continue
        img = letterbox_bgr_to_wh(fr, (imgsz, imgsz))
        pr = model.predict(img, conf=conf_th, imgsz=imgsz, verbose=False)
        bx = pr[0].boxes
        nb = len(bx) if bx is not None else 0
        mx = float(bx.conf.max()) if nb else 0.0
        print(f"{prefix} frame {p:4d} boxes {nb} maxconf {mx:.5f}")
        if mx > best_conf:
            best_conf, best_frame, best_n = mx, p, nb
    summary = {"maxconf": best_conf, "frame": int(best_frame), "n_boxes": int(best_n)}
    print(f"{prefix}_BEST", summary)
    return summary


def torch_detail_on_frames(
    tm,
    cap: cv2.VideoCapture,
    frames: list[int],
    imgsz: int,
    pt_name: str,
) -> None:
    """Низкий conf на выбранных кадрах — как в старой версии скрипта."""
    for p_try in frames:
        if p_try < 0:
            continue
        cap.set(cv2.CAP_PROP_POS_FRAMES, p_try)
        ok, fr = cap.read()
        if not ok:
            continue
        img = letterbox_bgr_to_wh(fr, (imgsz, imgsz))
        for cth in (0.01, 0.001):
            pr = tm.predict(img, conf=cth, imgsz=imgsz, verbose=False)
            bx = pr[0].boxes
            nb = len(bx) if bx is not None else 0
            mx = float(bx.conf.max()) if nb else 0.0
            print(f"torch_detail {pt_name} frame {p_try} conf {cth} boxes {nb} maxconf {mx:.5f}")


def resolve_video_row(db_path: str, video_id: int) -> tuple[int, str] | None:
    conn = sqlite3.connect(db_path)
    row = conn.execute("SELECT id, video_path FROM video WHERE id = ?", (video_id,)).fetchone()
    conn.close()
    if not row:
        return None
    return int(row[0]), str(row[1])


def main() -> int:
    ap = argparse.ArgumentParser(description="BirdLense YOLO diagnostic by video id")
    ap.add_argument("--video-id", type=int, action="append", required=True)
    ap.add_argument("--db", type=str, default=None)
    ap.add_argument("--no-full-regen", action="store_true")
    ap.add_argument("--sparse-conf", type=float, default=0.005)
    ap.add_argument(
        "--torch-pt",
        action="append",
        default=None,
        metavar="PATH",
        help="torch weights (repeatable); relative to detection/weights. Default: best.pt, last.pt.",
    )
    args = ap.parse_args()

    db_path = args.db or _default_db_path()
    if not os.path.isfile(db_path):
        print("ERROR: sqlite not found:", db_path, file=sys.stderr)
        return 2

    os.environ.setdefault("DATA_DIR", os.path.dirname(os.path.dirname(db_path)))

    from app_config.app_config import app_config
    from data_paths import resolve_recording_video_file
    from inference.torch_backend import load_yolo_detector
    from track_regenerator import build_detection_pipeline, process_video_for_tracks

    fp, dm = build_detection_pipeline(app_config, for_track_regen=True)
    rt_m = fp.strategy.binary_model
    imgsz = int(app_config.get("processor.binary_imgsz") or 640)
    backend = str(getattr(fp.strategy, "inference_backend", "torch")).lower()
    ov_prefix = "OPENVINO_runtime" if backend == "openvino" else f"PREDICT_{backend}_binary_model"

    torch_paths = resolve_torch_binary_paths(args.torch_pt)

    for vid in args.video_id:
        fp.reset()
        dm.reset()
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
        print("binary_imgsz", imgsz)
        print("torch_checkpoints:", [p.name for p in torch_paths] if torch_paths else "(none)")

        if n <= 0:
            positions = [0]
        else:
            step = max(1, n // 24)
            positions = list(range(0, n, step))
            if n - 1 not in positions:
                positions.append(n - 1)

        ov_sum = sparse_sweep_maxconf(rt_m, cap, positions, imgsz, args.sparse_conf, ov_prefix)

        mid = positions[len(positions) // 2] if positions else 0
        probe_frames: list[int] = []
        bf = int(ov_sum.get("frame") or -1)
        for x in (bf, mid):
            if x >= 0 and x not in probe_frames:
                probe_frames.append(x)

        for pt in torch_paths:
            prefix = f"torch_sparse_{pt.name}"
            tm = load_yolo_detector(str(pt), backend="torch")
            sparse_sweep_maxconf(tm, cap, positions, imgsz, args.sparse_conf, prefix)
            torch_detail_on_frames(tm, cap, probe_frames, imgsz, pt.name)

        cap.release()

        if not args.no_full_regen:
            fp.reset()
            dm.reset()
            fstep = int(app_config.get("processor.track_regen_frame_step") or 3)
            tmo = int(app_config.get("processor.track_regen_video_timeout_sec") or 300)
            dets = process_video_for_tracks(
                full,
                lores_size=(imgsz, imgsz),
                frame_processor=fp,
                decision_maker=dm,
                frame_step=fstep,
                max_runtime_sec=tmo,
            )
            print(
                "FULL_REGEN",
                {"detections": len(dets), "tracks_dict_len": len(fp.tracks), "frame_step": fstep},
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
