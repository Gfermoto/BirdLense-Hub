"""Tracklet crop + RGB feature extraction (shared by ML scripts and processor runtime)."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Sequence

import numpy as np

try:
    import cv2
except ImportError as exc:  # pragma: no cover
    raise RuntimeError("opencv-python required for behavior tracklet crops") from exc

RGB_SIZE = 8
FEATURE_DIM = RGB_SIZE * RGB_SIZE * 3


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


def crop_frame(frame_bgr: np.ndarray, bbox: Sequence[float], *, out_size: int = 224) -> np.ndarray:
    h, w = frame_bgr.shape[:2]
    left, top, right, bottom = bbox_to_pixels(bbox, w, h)
    crop = frame_bgr[top:bottom, left:right]
    if crop.size == 0:
        crop = frame_bgr
    return cv2.resize(crop, (out_size, out_size), interpolation=cv2.INTER_AREA)


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


def rgb_feature_vector_from_mean_rgb(rgb: np.ndarray) -> list[float]:
    small = cv2.resize(rgb, (RGB_SIZE, RGB_SIZE), interpolation=cv2.INTER_AREA)
    return (small.astype(np.float32).reshape(-1) / 255.0).tolist()


def dominant_tracklet_boxes(video_detections: list[dict[str, Any]]) -> list[dict[str, Any]]:
    best: dict[str, Any] | None = None
    best_n = -1
    for det in video_detections:
        if not isinstance(det, dict):
            continue
        frames = det.get("frames") or []
        if not isinstance(frames, list) or len(frames) < 3:
            continue
        boxes = []
        for fr in frames:
            if not isinstance(fr, dict):
                continue
            b = fr.get("bbox")
            if isinstance(b, list) and len(b) == 4:
                boxes.append({"t": float(fr.get("t") or 0.0), "bbox": b})
        if len(boxes) > best_n:
            best_n = len(boxes)
            best = {"boxes": boxes}
    return (best or {}).get("boxes") or []


def runtime_tracklet_rgb_features(
    video_detections: list[dict[str, Any]],
    *,
    video_path: str | None = None,
    processor_cwd: str | None = None,
    num_frames: int = 16,
) -> list[float] | None:
    boxes = dominant_tracklet_boxes(video_detections)
    if len(boxes) < 3:
        return None
    root = Path(processor_cwd) if processor_cwd else None
    vpath = resolve_video_path(video_path, repo_root=root)
    rgb_frames: list[np.ndarray] = []
    if vpath is not None and vpath.is_file():
        cap = cv2.VideoCapture(str(vpath))
        if cap.isOpened():
            if len(boxes) > num_frames:
                idxs = np.linspace(0, len(boxes) - 1, num=num_frames, dtype=int)
                sampled = [boxes[int(i)] for i in idxs]
            else:
                sampled = boxes
            for box in sampled:
                t_sec = float(box.get("t") or 0.0)
                cap.set(cv2.CAP_PROP_POS_MSEC, max(0.0, t_sec * 1000.0))
                ok, frame = cap.read()
                if not ok or frame is None:
                    continue
                crop = crop_frame(frame, box["bbox"])
                rgb_frames.append(cv2.cvtColor(crop, cv2.COLOR_BGR2RGB))
            cap.release()
    if len(rgb_frames) < 3:
        out_size = 224
        for box in boxes[:num_frames]:
            b = box["bbox"]
            canvas = np.zeros((out_size, out_size, 3), dtype=np.uint8)
            x1, y1, x2, y2 = [float(v) for v in b[:4]]
            if max(abs(x1), abs(y1)) <= 1.5:
                px = [int(x1 * out_size), int(y1 * out_size), int(x2 * out_size), int(y2 * out_size)]
            else:
                px = [int(x1), int(y1), int(x2), int(y2)]
            cv2.rectangle(canvas, (px[0], px[1]), (px[2], px[3]), (40, 180, 90), thickness=-1)
            rgb_frames.append(canvas)
    if len(rgb_frames) < 3:
        return None
    stack = np.stack([f.astype(np.float32) for f in rgb_frames], axis=0)
    mean_rgb = np.clip(np.mean(stack, axis=0), 0, 255).astype(np.uint8)
    vec = rgb_feature_vector_from_mean_rgb(mean_rgb)
    return vec if len(vec) == FEATURE_DIM else None
