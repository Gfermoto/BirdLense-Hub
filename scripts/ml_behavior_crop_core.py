"""Shared tracklet crop extraction and quality filters for Behavior v2 (#456)."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Sequence

import numpy as np

try:
    import cv2
except ImportError as exc:  # pragma: no cover
    raise RuntimeError("opencv-python is required for behavior crop extraction") from exc


DEFAULT_CROP_SIZE = 224
DEFAULT_NUM_FRAMES = 16


def resolve_video_path(video_path: str | None, *, repo_root: Path | None = None) -> Path | None:
    if not video_path:
        return None
    p = Path(str(video_path).strip())
    candidates: list[Path] = []
    if p.is_absolute():
        candidates.append(p)
    else:
        if repo_root is not None:
            candidates.append((repo_root / p).resolve())
            candidates.append((repo_root / "app" / p).resolve())
        candidates.append((Path.cwd() / p).resolve())
    for cand in candidates:
        if cand.is_file():
            return cand
    return None


def bbox_to_pixels(bbox: Sequence[float], width: int, height: int) -> tuple[int, int, int, int]:
    x1, y1, x2, y2 = [float(v) for v in bbox[:4]]
    if max(abs(x1), abs(y1), abs(x2), abs(y2)) <= 1.5:
        x1, x2 = x1 * width, x2 * width
        y1, y2 = y1 * height, y2 * height
    left = int(max(0, min(x1, x2)))
    right = int(min(width, max(x1, x2)))
    top = int(max(0, min(y1, y2)))
    bottom = int(min(height, max(y1, y2)))
    if right <= left + 2 or bottom <= top + 2:
        return 0, 0, width, height
    return left, top, right, bottom


def blur_score_laplacian(bgr: np.ndarray) -> float:
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def crop_frame(
    frame_bgr: np.ndarray,
    bbox: Sequence[float],
    *,
    out_size: int = DEFAULT_CROP_SIZE,
) -> np.ndarray:
    h, w = frame_bgr.shape[:2]
    left, top, right, bottom = bbox_to_pixels(bbox, w, h)
    crop = frame_bgr[top:bottom, left:right]
    if crop.size == 0:
        crop = frame_bgr
    return cv2.resize(crop, (out_size, out_size), interpolation=cv2.INTER_AREA)


def sample_tracklet_frames(
    boxes: list[dict[str, Any]],
    *,
    num_frames: int = DEFAULT_NUM_FRAMES,
) -> list[dict[str, Any]]:
    usable = [b for b in boxes if isinstance(b, dict) and isinstance(b.get("bbox"), list) and len(b["bbox"]) == 4]
    if not usable:
        return []
    if len(usable) <= num_frames:
        return usable
    idxs = np.linspace(0, len(usable) - 1, num=num_frames, dtype=int)
    return [usable[int(i)] for i in idxs]


def temporal_mean_rgb(frames_rgb: list[np.ndarray]) -> np.ndarray:
    if not frames_rgb:
        raise ValueError("no frames for temporal mean")
    stack = np.stack([f.astype(np.float32) for f in frames_rgb], axis=0)
    mean = np.mean(stack, axis=0)
    return np.clip(mean, 0, 255).astype(np.uint8)


def extract_tracklet_crops(
    tracklet: dict[str, Any],
    *,
    crops_root: Path,
    repo_root: Path | None = None,
    num_frames: int = DEFAULT_NUM_FRAMES,
    out_size: int = DEFAULT_CROP_SIZE,
    min_blur_score: float = 8.0,
    min_span: float = 0.01,
) -> dict[str, Any] | None:
    """Save per-frame jpgs + preview.mp4; return quality metadata or None if rejected."""
    video_path = resolve_video_path(tracklet.get("video_path"), repo_root=repo_root)
    boxes = tracklet.get("boxes") or []
    if not isinstance(boxes, list) or not boxes:
        return None
    sampled = sample_tracklet_frames(boxes, num_frames=num_frames)
    if len(sampled) < max(3, min(5, num_frames // 3)):
        return None

    tracklet_id = str(tracklet.get("tracklet_id") or "unknown")
    out_dir = crops_root / tracklet_id
    out_dir.mkdir(parents=True, exist_ok=True)

    spans: list[float] = []
    blur_scores: list[float] = []
    frame_paths: list[str] = []
    rgb_frames: list[np.ndarray] = []

    cap = None
    if video_path is not None:
        cap = cv2.VideoCapture(str(video_path))
    if cap is not None and cap.isOpened():
        for i, box in enumerate(sampled):
            t_sec = float(box.get("t") or 0.0)
            cap.set(cv2.CAP_PROP_POS_MSEC, max(0.0, t_sec * 1000.0))
            ok, frame = cap.read()
            if not ok or frame is None:
                continue
            crop = crop_frame(frame, box["bbox"], out_size=out_size)
            blur_scores.append(blur_score_laplacian(crop))
            frame_paths.append(str((out_dir / f"frame_{i:03d}.jpg").resolve()))
            cv2.imwrite(frame_paths[-1], crop)
            rgb_frames.append(cv2.cvtColor(crop, cv2.COLOR_BGR2RGB))
            b = box["bbox"]
            c0x = (float(b[0]) + float(b[2])) * 0.5
            c0y = (float(b[1]) + float(b[3])) * 0.5
            spans.append(math.hypot(c0x, c0y))
        cap.release()
    else:
        # WetlandBirds / bbox-only: synthetic solid crops from normalized bbox geometry.
        for i, box in enumerate(sampled):
            b = box["bbox"]
            canvas = np.zeros((out_size, out_size, 3), dtype=np.uint8)
            x1, y1, x2, y2 = [float(v) for v in b[:4]]
            if max(abs(x1), abs(y1)) <= 1.5:
                px = [int(x1 * out_size), int(y1 * out_size), int(x2 * out_size), int(y2 * out_size)]
            else:
                px = [int(x1), int(y1), int(x2), int(y2)]
            cv2.rectangle(canvas, (px[0], px[1]), (px[2], px[3]), (40, 180, 90), thickness=-1)
            blur_scores.append(blur_score_laplacian(canvas))
            rel = str((out_dir / f"frame_{i:03d}.jpg").resolve())
            frame_paths.append(rel)
            cv2.imwrite(rel, canvas)
            rgb_frames.append(cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB))
            spans.append(0.05)

    if len(frame_paths) < 3:
        return None
    mean_blur = float(np.mean(blur_scores))
    span = float(max(spans) - min(spans)) if spans else 0.0
    if mean_blur < float(min_blur_score):
        return None
    if span < float(min_span) and video_path is not None:
        return None

    preview_path = out_dir / "preview.mp4"
    if len(frame_paths) >= 2:
        writer = cv2.VideoWriter(
            str(preview_path),
            cv2.VideoWriter_fourcc(*"mp4v"),
            4.0,
            (out_size, out_size),
        )
        for fp in frame_paths:
            img = cv2.imread(fp)
            if img is not None:
                writer.write(img)
        writer.release()

    mean_rgb = temporal_mean_rgb(rgb_frames)
    mean_path = out_dir / "mean_rgb.npy"
    np.save(mean_path, mean_rgb)

    meta = {
        "crop_dir": str(out_dir.resolve()),
        "frame_paths": frame_paths,
        "preview_mp4": str(preview_path.resolve()) if preview_path.is_file() else None,
        "mean_rgb_npy": str(mean_path.resolve()),
        "quality": {
            "mean_blur": round(mean_blur, 4),
            "span": round(span, 4),
            "frame_count": len(frame_paths),
        },
    }
    (out_dir / "crop_meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return meta


def load_tracklet_mean_rgb(tracklet: dict[str, Any]) -> np.ndarray | None:
    path = tracklet.get("mean_rgb_npy") or tracklet.get("crop_mean_rgb")
    if not path:
        crop_dir = tracklet.get("crop_dir")
        if crop_dir:
            cand = Path(str(crop_dir)) / "mean_rgb.npy"
            if cand.is_file():
                path = str(cand)
    if not path:
        return None
    p = Path(str(path))
    if not p.is_file():
        return None
    arr = np.load(p)
    if arr.ndim != 3 or arr.shape[2] != 3:
        return None
    return arr.astype(np.uint8)
