#!/usr/bin/env python3
"""
Локальный синтетический смоук детектора: без хаба, без БД, без ожидания птиц.

Генерирует кадр/ролик (шум или градиент) или ``--image`` / ``--video``;
YOLO ``.pt`` или OpenVINO-каталог; пишет ``annotated*.jpg`` / ``*.mp4`` с
``Results.plot()``; печатает сводку детекций.

Примеры: ``python3 scripts/detector_synthetic_smoke.py``;
``--conf 0.15 --device cpu``; ``--image frame.jpg``;

Синтетика часто даёт 0 боксов — для визуала птицы используйте ``--image``.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from ultralytics import YOLO

_REPO = Path(__file__).resolve().parents[1]
_W = _REPO / 'app/processor/models/detection/weights'


def _default_model() -> Path:
    for cand in (_W / "yolo11n.pt", _W / "yolo11n_openvino_model", _W / "best.pt", _W / "best_openvino_model"):
        if cand.exists():
            return cand
    return _W / "yolo11n.pt"


def _synthetic_frame(mode: str, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    h, w = 720, 1280
    if mode == 'noise':
        return rng.integers(0, 256, (h, w, 3), dtype=np.uint8)
    if mode == 'gradient':
        g = np.linspace(0, 255, w, dtype=np.float32)
        grid = np.stack([g] * h, axis=0)
        b = np.stack(
            [grid, np.roll(grid, 40), np.roll(grid, -40)],
            axis=-1,
        ).astype(np.uint8)
        return b
    raise ValueError(mode)


def _synthetic_video_frames(
    mode: str, seed: int, n_frames: int, step: int
) -> list[np.ndarray]:
    out: list[np.ndarray] = []
    for i in range(n_frames):
        fr = _synthetic_frame(mode, seed + i * step)
        shift = i % 60
        out.append(np.roll(fr, shift, axis=1))
    return out


def _predict(
    model: YOLO,
    frame: np.ndarray,
    *,
    device: str | None,
    conf: float,
    imgsz: int,
) -> Any:
    kwargs: dict = {'conf': conf, 'imgsz': imgsz, 'verbose': False}
    if device:
        kwargs['device'] = device
    return model.predict(frame, **kwargs)[0]


def main() -> int:
    ap = argparse.ArgumentParser(
        description='Синтетический смоук детектора (локально)',
    )
    dm = _default_model()
    ap.add_argument(
        '--model',
        type=Path,
        default=None,
        help=f'по умолчанию: {dm}',
    )
    ap.add_argument(
        '--out-dir',
        type=Path,
        default=_REPO / 'tmp/detector_synthetic_smoke',
    )
    ap.add_argument('--conf', type=float, default=0.2)
    ap.add_argument('--imgsz', type=int, default=640)
    ap.add_argument(
        '--device',
        type=str,
        default='',
        help='cpu / 0 / intel:gpu; пусто — авто',
    )
    ap.add_argument(
        '--mode',
        choices=('noise', 'gradient'),
        default='noise',
        help='синтетика, если нет --image/--video',
    )
    ap.add_argument('--seed', type=int, default=42)
    ap.add_argument(
        '--image',
        type=Path,
        help='кадр (лучше всего, чтобы увидеть боксы)',
    )
    ap.add_argument(
        '--video',
        type=Path,
        help='ролик: до --max-frames кадров',
    )
    ap.add_argument(
        '--synthetic-video',
        action='store_true',
        help='доп. короткий mp4 из синтетических кадров',
    )
    ap.add_argument(
        '--video-frames',
        type=int,
        default=24,
        help='кадров в синтетическом mp4',
    )
    ap.add_argument(
        '--max-frames',
        type=int,
        default=120,
        help='для --video: лимит инференса',
    )
    args = ap.parse_args()

    model_path = args.model if args.model is not None else _default_model()
    if not model_path.is_file() and not model_path.is_dir():
        print(f'ERR: model not found: {model_path}', file=sys.stderr)
        return 1

    out_dir = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    device = args.device.strip() or None

    model = YOLO(str(model_path))

    if args.image and args.image.is_file():
        frame = cv2.imread(str(args.image))
        if frame is None:
            print(f'ERR: cannot read image {args.image}', file=sys.stderr)
            return 1
        r = _predict(model, frame, device=device, conf=args.conf, imgsz=args.imgsz)
        plotted = r.plot()
        out_jpg = out_dir / 'annotated.jpg'
        cv2.imwrite(str(out_jpg), plotted)
        print(f'Wrote {out_jpg}')
        print(_summary(r))
        return 0

    if args.video and args.video.is_file():
        cap = cv2.VideoCapture(str(args.video))
        if not cap.isOpened():
            print(f'ERR: cannot open video {args.video}', file=sys.stderr)
            return 1
        fps = float(cap.get(cv2.CAP_PROP_FPS) or 25.0)
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        out_mp4 = out_dir / 'annotated.mp4'
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        writer = cv2.VideoWriter(str(out_mp4), fourcc, fps, (w, h))
        n = 0
        total_dets = 0
        while n < args.max_frames:
            ret, fr = cap.read()
            if not ret or fr is None:
                break
            r = _predict(
                model, fr, device=device, conf=args.conf, imgsz=args.imgsz
            )
            total_dets += len(r.boxes) if r.boxes is not None else 0
            pl = r.plot()
            if pl.shape[1] != w or pl.shape[0] != h:
                pl = cv2.resize(pl, (w, h))
            writer.write(pl)
            n += 1
        cap.release()
        writer.release()
        print(f'Wrote {out_mp4} frames={n} boxes_total={total_dets}')
        return 0

    frame = _synthetic_frame(args.mode, args.seed)
    r = _predict(model, frame, device=device, conf=args.conf, imgsz=args.imgsz)
    plotted = r.plot()
    out_jpg = out_dir / 'annotated_synthetic.jpg'
    cv2.imwrite(str(out_jpg), plotted)
    print(f'Wrote {out_jpg}')
    print(_summary(r))

    if args.synthetic_video:
        frames = _synthetic_video_frames(
            args.mode, args.seed, args.video_frames, step=7
        )
        h, w = frames[0].shape[:2]
        out_mp4 = out_dir / 'annotated_synthetic.mp4'
        fps = 6.0
        writer = cv2.VideoWriter(
            str(out_mp4), cv2.VideoWriter_fourcc(*'mp4v'), fps, (w, h)
        )
        for fr in frames:
            r = _predict(
                model, fr, device=device, conf=args.conf, imgsz=args.imgsz
            )
            pl = r.plot()
            writer.write(pl)
        writer.release()
        print(f'Wrote {out_mp4} ({len(frames)} frames)')

    note = (
        'На синтетике часто 0 детекций; для боксов птицы — --image с кадром.'
    )
    print(note, file=sys.stderr)
    return 0


def _summary(r: Any) -> str:
    boxes = r.boxes
    if boxes is None or len(boxes) == 0:
        return 'detections: 0'
    cls_ids = (
        boxes.cls.cpu().numpy().astype(int) if boxes.cls is not None else []
    )
    confs = boxes.conf.cpu().numpy() if boxes.conf is not None else []
    names = r.names or {}
    parts = []
    for i, cid in enumerate(cls_ids):
        label = names.get(int(cid), str(int(cid)))
        c = float(confs[i]) if len(confs) > i else 0.0
        parts.append(f'{label}:{c:.2f}')
    det = f'detections: {len(parts)} | ' + ', '.join(parts)
    return det


if __name__ == '__main__':
    raise SystemExit(main())
