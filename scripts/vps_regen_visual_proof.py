#!/usr/bin/env python3
"""Regenerate tracks for video IDs + write contact sheets / short annotated MP4 (hub container)."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import cv2
import numpy as np

# GPU/OpenVINO — до импорта processor/web
for _k, _v in (
    ("BIRDLENSE_INFERENCE_BACKEND", "openvino"),
    ("BIRDLENSE_INFERENCE_DEVICE", "intel:gpu"),
    ("BIRDLENSE_CLASSIFIER_INFERENCE_BACKEND", "openvino"),
    ("BIRDLENSE_CLASSIFIER_INFERENCE_DEVICE", "intel:gpu"),
):
    os.environ.setdefault(_k, _v)

APP_ROOT = Path(os.environ.get("APP_ROOT", "/app"))
WEB_ROOT = Path(os.environ.get("WEB_ROOT", str(APP_ROOT / "web")))
PROC_SRC = Path(os.environ.get("PROCESSOR_SRC", str(APP_ROOT / "processor" / "src")))
DATA_ROOT = Path(os.environ.get("DATA_ROOT", str(APP_ROOT / "data")))
OUT_DIR = DATA_ROOT / "tmp" / "regen_proof"


def _ensure_paths() -> None:
    for p in (APP_ROOT, WEB_ROOT, PROC_SRC):
        s = str(p)
        if s not in sys.path:
            sys.path.insert(0, s)
    os.chdir(WEB_ROOT)


def _resolve_video_path(rel: str) -> Path:
    p = Path(rel)
    if p.is_file():
        return p
    cand = DATA_ROOT / rel.replace("data/", "", 1) if rel.startswith("data/") else DATA_ROOT / rel
    if cand.is_file():
        return cand
    return DATA_ROOT / "recordings" / rel  # fallback


def _norm_bbox_to_px(bbox: list, w: int, h: int) -> tuple[int, int, int, int]:
    x1, y1, x2, y2 = bbox
    if max(abs(x1), abs(y1), abs(x2), abs(y2)) <= 1.5:
        return int(x1 * w), int(y1 * h), int(x2 * w), int(y2 * h)
    return int(x1), int(y1), int(x2), int(y2)


def _draw_tracks_on_frame(
    frame: np.ndarray,
    tracks: list[dict],
    t_sec: float,
    *,
    tol: float = 0.35,
) -> np.ndarray:
    out = frame.copy()
    h, w = out.shape[:2]
    for tr in tracks:
        name = str(tr.get("species_name") or "?")
        conf = float(tr.get("confidence") or 0.0)
        tid = tr.get("track_id")
        for fr in tr.get("frames") or []:
            if abs(float(fr.get("t", -999)) - t_sec) > tol:
                continue
            bb = fr.get("bbox")
            if not bb or len(bb) < 4:
                continue
            x1, y1, x2, y2 = _norm_bbox_to_px(list(bb)[:4], w, h)
            color = (0, 220, 80) if "magpie" in name.lower() else (80, 180, 255)
            cv2.rectangle(out, (x1, y1), (x2, y2), color, 2)
            label = f"{name} {conf:.2f} id={tid}"
            cv2.putText(
                out,
                label[:48],
                (x1, max(18, y1 - 6)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                color,
                2,
                cv2.LINE_AA,
            )
    return out


def _load_tracks_from_db(video_id: int) -> list[dict]:
    from models import Species, Video, VideoSpecies, db

    video = db.session.get(Video, video_id)
    if not video:
        return []
    out: list[dict] = []
    for vs in video.video_species:
        sp = vs.species.name if vs.species else "?"
        frames_raw = vs.frames
        frames: list = []
        if frames_raw:
            try:
                frames = json.loads(frames_raw) if isinstance(frames_raw, str) else list(frames_raw)
            except (TypeError, json.JSONDecodeError):
                frames = []
        out.append(
            {
                "species_name": sp,
                "confidence": float(vs.confidence or 0),
                "track_id": vs.track_id,
                "frames": frames,
            },
        )
    return out


def _write_visuals(video_id: int, rel_path: str, tracks: list[dict], *, frame_step: int) -> dict:
    vp = _resolve_video_path(rel_path)
    if not vp.is_file():
        return {"video_id": video_id, "error": "file_missing", "path": str(vp)}

    cap = cv2.VideoCapture(str(vp))
    if not cap.isOpened():
        return {"video_id": video_id, "error": "open_failed"}

    fps = float(cap.get(cv2.CAP_PROP_FPS) or 25.0)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    duration = total / fps if fps > 0 and total > 0 else 0.0

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    contact_path = OUT_DIR / f"video_{video_id}_contact.jpg"
    mp4_path = OUT_DIR / f"video_{video_id}_annotated.mp4"

    sample_ts = [duration * x for x in (0.08, 0.25, 0.42, 0.58, 0.75, 0.92)] if duration > 1 else [0.0]
    panels: list[np.ndarray] = []
    for t in sample_ts:
        cap.set(cv2.CAP_PROP_POS_MSEC, max(0.0, t * 1000.0))
        ok, frame = cap.read()
        if not ok or frame is None:
            continue
        panels.append(_draw_tracks_on_frame(frame, tracks, t))

    if panels:
        ph = max(p.shape[0] for p in panels)
        pw = max(p.shape[1] for p in panels)
        row = []
        for p in panels[:3]:
            if p.shape[0] != ph or p.shape[1] != pw:
                p = cv2.resize(p, (pw, ph))
            row.append(p)
        top = np.hstack(row) if row else None
        row2 = []
        for p in panels[3:6]:
            if p.shape[0] != ph or p.shape[1] != pw:
                p = cv2.resize(p, (pw, ph))
            row2.append(p)
        bottom = np.hstack(row2) if row2 else None
        if top is not None and bottom is not None:
            sheet = np.vstack([top, bottom])
        else:
            sheet = top or bottom
        if sheet is not None:
            cv2.imwrite(str(contact_path), sheet)

    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
    out_fps = fps / max(1, frame_step)
    writer = cv2.VideoWriter(
        str(mp4_path),
        cv2.VideoWriter_fourcc(*"mp4v"),
        out_fps,
        (w, h),
    )
    written = 0
    idx = 0
    max_out = min(total, int(fps * 45)) if total else 900  # cap ~45s output
    while idx < max_out:
        ok, frame = cap.read()
        if not ok or frame is None:
            break
        if idx % frame_step == 0:
            t = idx / fps if fps > 0 else 0.0
            writer.write(_draw_tracks_on_frame(frame, tracks, t, tol=0.2))
            written += 1
        idx += 1
    cap.release()
    writer.release()

    species = sorted({str(t.get("species_name") or "") for t in tracks if t.get("species_name")})
    return {
        "video_id": video_id,
        "path": str(vp),
        "duration_sec": round(duration, 2),
        "species": species,
        "contact_jpg": str(contact_path) if contact_path.is_file() else None,
        "annotated_mp4": str(mp4_path) if mp4_path.is_file() else None,
        "mp4_frames_written": written,
    }


def _apply_regen_tuning(frame_step: int) -> None:
    from app_config.app_config import app_config

    app_config.set("processor.track_regen_match_live_pipeline", False)
    app_config.set("processor.track_regen_frame_step", max(1, frame_step))
    app_config.set("processor.track_regen_video_timeout_sec", 1200)
    app_config.set("processor.track_regen_precise_timeout_sec", 1200)


def run_regen(video_ids: list[int], *, skip_regen: bool, frame_step: int) -> dict:
    _ensure_paths()
    from app import create_app

    app = create_app()
    regen_result: dict = {"skipped": skip_regen, "per_video": []}
    with app.app_context():
        if not skip_regen:
            from services.system_track_regen.worker_core import run_regenerate_tracks_worker
            import routes.ui_system_jobs_state as job_state

            _apply_regen_tuning(frame_step)
            for vid in video_ids:
                run_regenerate_tracks_worker(
                    app,
                    False,
                    None,
                    None,
                    None,
                    [vid],
                    [],
                )
                regen_result["per_video"].append(
                    {"video_id": vid, **dict(job_state._regenerate_tracks_status)},
                )
            regen_result["status"] = "done"

        from models import Video, db

        visuals = []
        for vid in video_ids:
            video = db.session.get(Video, vid)
            if not video or not video.video_path:
                visuals.append({"video_id": vid, "error": "no_video"})
                continue
            tracks = _load_tracks_from_db(vid)
            visuals.append(
                _write_visuals(vid, video.video_path, tracks, frame_step=frame_step),
            )
        regen_result["visuals"] = visuals
    return regen_result


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--video-ids", required=True, help="Comma-separated ids, e.g. 2140,2152")
    ap.add_argument("--skip-regen", action="store_true", help="Only redraw from DB")
    ap.add_argument("--frame-step", type=int, default=3, help="Annotated MP4 subsample (simulate low FPS)")
    args = ap.parse_args()
    ids = [int(x.strip()) for x in args.video_ids.split(",") if x.strip()]
    result = run_regen(ids, skip_regen=args.skip_regen, frame_step=max(1, args.frame_step))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("status") != "failed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
