#!/usr/bin/env python3
"""
Сравнение боксов «птица» между двумя чекпоинтами YOLO на одних и тех же роликах.

Метрики: доля кадров с хотя бы одной птицей у A/B, средний best IoU на кадрах где оба
увидели птицу (greedy matching по IoU). Нужен для оценки BRG vs старый бинарник по
геометрии рамок (не по видам классификатора).

Пример (в контейнере birdlense или venv с ultralytics):

  # Разные чекпоинты на одном ролике (COCO yolo11n class 14 = bird; BRG 3-class class 0 = Bird):
  docker compose run --rm -v "$(pwd)/..:/workspace" birdlense \\
    python3 /workspace/scripts/compare_detector_bboxes.py \\
    --video /workspace/tmp/exp_video.mp4 \\
    --model-a /workspace/app/processor/models/detection/weights/yolo11n.pt \\
    --model-b /workspace/app/processor/models/detection/weights/best.pt \\
    --bird-class-ids-a 14 --bird-class-ids-b 0 \\
    --imgsz 640 --conf 0.25 --frame-step 2 --device cpu

  # Чистая проверка parity PyTorch ↔ OpenVINO одного BRG-веса (оба «птица» = класс 0):
  # сначала: scripts/train_detector_brg.py --export-openvino-only app/processor/.../best.pt --imgsz 640
  docker compose run --rm -v "$(pwd)/..:/workspace" birdlense \\
    python3 /workspace/scripts/compare_detector_bboxes.py \\
    --video /workspace/tmp/exp_video.mp4 \\
    --model-a /workspace/app/processor/models/detection/weights/best.pt \\
    --model-b /workspace/app/processor/models/detection/weights/best_openvino_model \\
    --bird-class-ids-a 0 --bird-class-ids-b 0 \\
    --imgsz 640 --conf 0.25 --frame-step 2 --device cpu

  python3 scripts/compare_detector_bboxes.py \\
    --video /app/data/recordings/2026/04/07/185837/video.mp4 \\
    --model-a /app/processor/models/detection/weights_backup_before_brg_20260430T144708Z/best.pt \\
    --model-b /app/processor/models/detection/weights/best.pt \\
    --bird-class-ids-a 0 --bird-class-ids-b 0 \\
    --imgsz 640 --conf 0.2 --frame-step 3
"""

from __future__ import annotations

import argparse
import json
import sys
from statistics import mean, median


def _iou_xyxy(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
    inter = iw * ih
    if inter <= 0:
        return 0.0
    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    union = area_a + area_b - inter
    return float(inter / union) if union > 0 else 0.0


def _greedy_match_ious(boxes_a: list, boxes_b: list) -> list[float]:
    """Жадное сопоставление пар по убыванию IoU; каждый бокс не более одного матча."""
    if not boxes_a or not boxes_b:
        return []
    pairs: list[tuple[float, int, int]] = []
    for ia, a in enumerate(boxes_a):
        for ib, b in enumerate(boxes_b):
            pairs.append((_iou_xyxy(tuple(a), tuple(b)), ia, ib))
    pairs.sort(key=lambda t: t[0], reverse=True)
    used_a: set[int] = set()
    used_b: set[int] = set()
    ious: list[float] = []
    for iou, ia, ib in pairs:
        if ia in used_a or ib in used_b:
            continue
        used_a.add(ia)
        used_b.add(ib)
        ious.append(iou)
    return ious


def _bird_boxes(result, bird_ids: set[int]):
    out = []
    if not result or not result[0].boxes:
        return out
    b = result[0].boxes
    xyxy = b.xyxy.cpu().numpy()
    cls = b.cls.int().cpu().tolist()
    for i, c in enumerate(cls):
        if int(c) in bird_ids:
            out.append(tuple(float(x) for x in xyxy[i]))
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", action="append", required=True)
    parser.add_argument("--model-a", required=True)
    parser.add_argument("--model-b", required=True)
    parser.add_argument(
        "--bird-class-ids-a",
        default="0",
        help="Классы птицы у модели A (через запятую), обычно 0",
    )
    parser.add_argument("--bird-class-ids-b", default="0")
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--conf", type=float, default=0.2)
    parser.add_argument("--frame-step", type=int, default=3)
    parser.add_argument("--device", default="", help="Ultralytics device (e.g. intel:gpu, 0, cpu)")
    parser.add_argument(
        "--min-median-iou",
        type=float,
        default=None,
        help="Exit 1 when median_iou_when_both is below this gate (Frigate-parity #640)",
    )
    parser.add_argument(
        "--clip-id",
        default="",
        help="Clip label for gate failure messages (e.g. golden 1819)",
    )
    args = parser.parse_args()

    try:
        from ultralytics import YOLO
    except ImportError:
        print(json.dumps({"error": "ultralytics_missing"}), file=sys.stderr)
        return 2

    ids_a = {int(x.strip()) for x in args.bird_class_ids_a.split(",") if x.strip()}
    ids_b = {int(x.strip()) for x in args.bird_class_ids_b.split(",") if x.strip()}
    dev = (args.device or "").strip() or None

    ma = YOLO(args.model_a, task="detect")
    mb = YOLO(args.model_b, task="detect")

    import cv2

    pred_kw = {"imgsz": args.imgsz, "conf": args.conf, "verbose": False}
    if dev:
        pred_kw["device"] = dev

    per_video: list[dict] = []
    global_frames = 0
    global_a = global_b = global_both = 0
    global_ious: list[float] = []

    for video_path in args.video:
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            per_video.append({"video": video_path, "error": "cannot_open"})
            continue
        fi = 0
        sampled = 0
        fa = fb = fboth = 0
        viou: list[float] = []
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            if fi % args.frame_step != 0:
                fi += 1
                continue
            ra = ma.predict(frame, **pred_kw)
            rb = mb.predict(frame, **pred_kw)
            ba = _bird_boxes(ra, ids_a)
            bb = _bird_boxes(rb, ids_b)
            global_frames += 1
            sampled += 1
            fi += 1
            if ba:
                fa += 1
                global_a += 1
            if bb:
                fb += 1
                global_b += 1
            if ba and bb:
                fboth += 1
                global_both += 1
                viou.extend(_greedy_match_ious(ba, bb))
        cap.release()
        global_ious.extend(viou)
        per_video.append(
            {
                "video": video_path,
                "sampled_frames": sampled,
                "frames_with_bird_a": fa,
                "frames_with_bird_b": fb,
                "frames_with_bird_both": fboth,
                "mean_iou_when_both": round(mean(viou), 4) if viou else None,
                "median_iou_when_both": round(median(viou), 4) if viou else None,
            },
        )

    out = {
        "report_format": "compare_detector_bboxes@v1",
        "model_a": args.model_a,
        "model_b": args.model_b,
        "bird_class_ids_a": sorted(ids_a),
        "bird_class_ids_b": sorted(ids_b),
        "imgsz": args.imgsz,
        "conf": args.conf,
        "frame_step": args.frame_step,
        "device": dev,
        "sampled_frames_total": global_frames,
        "frames_with_bird_a": global_a,
        "frames_with_bird_b": global_b,
        "frames_with_bird_both": global_both,
        "mean_iou_when_both": round(mean(global_ious), 4) if global_ious else None,
        "median_iou_when_both": round(median(global_ious), 4) if global_ious else None,
        "videos": per_video,
    }
    gate = args.min_median_iou
    if gate is not None:
        median = out.get("median_iou_when_both")
        out["gate"] = {
            "min_median_iou": gate,
            "clip_id": (args.clip_id or "").strip() or None,
            "passed": median is not None and float(median) >= float(gate),
            "delta": None if median is None else round(float(median) - float(gate), 4),
        }
        if not out["gate"]["passed"]:
            clip = out["gate"]["clip_id"] or "unknown"
            delta = out["gate"]["delta"]
            print(
                json.dumps(
                    {
                        "error": "detector_bbox_parity_gate_failed",
                        "clip_id": clip,
                        "median_iou": median,
                        "min_median_iou": gate,
                        "delta": delta,
                    },
                    ensure_ascii=False,
                ),
                file=sys.stderr,
            )
            print(json.dumps(out, ensure_ascii=False, indent=2))
            return 1

    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
