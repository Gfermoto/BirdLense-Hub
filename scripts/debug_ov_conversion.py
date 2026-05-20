#!/usr/bin/env python3
"""
Сравнение PyTorch vs OpenVINO для бинарного YOLO на одном кадре.

Цель: локализовать деградацию OV (логиты до NMS vs после NMS vs пост-процесс Ultralytics).

Пример (контейнер birdlense, утренний клип с птицей):

  docker exec birdlense python3 /app/scripts/debug_ov_conversion.py \\
    --image /app/data/recordings/2026/05/20/014828/video.mp4 \\
    --frame-index 11 \\
    --pt /app/processor/models/detection/weights/best.pt \\
    --ov /app/processor/models/detection/weights/best_openvino_model \\
    --imgsz 640 --conf 0.001

  # NABirds (рабочий PT) vs BRG OpenVINO:
  docker exec birdlense python3 /app/scripts/debug_ov_conversion.py \\
    --image /app/data/recordings/2026/05/20/014828/video.mp4 \\
    --frame-index 11 \\
    --pt /app/processor/models/detection/weights/best_NABirds.pt \\
    --ov /app/processor/models/detection/weights/best_openvino_model \\
    --bird-class-id 0
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def _read_frame(source: str, frame_index: int):
    import cv2
    import numpy as np

    path = Path(source)
    if path.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp", ".bmp"}:
        img = cv2.imread(str(path))
        if img is None:
            raise SystemExit(f"cannot read image: {path}")
        return img
    cap = cv2.VideoCapture(str(path))
    if frame_index > 0:
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(frame_index))
    ok, frame = cap.read()
    cap.release()
    if not ok or frame is None:
        raise SystemExit(f"cannot read frame {frame_index} from {path}")
    return np.asarray(frame, dtype=np.uint8)


def _frame_stats(bgr) -> dict[str, Any]:
    import numpy as np

    arr = np.asarray(bgr)
    return {
        "shape": list(arr.shape),
        "dtype": str(arr.dtype),
        "mean": float(arr.mean()),
        "std": float(arr.std()),
        "min": int(arr.min()),
        "max": int(arr.max()),
    }


def _predict_boxes(model_path: str, bgr, *, imgsz: int, conf: float, device: str | None) -> dict[str, Any]:
    from ultralytics import YOLO

    m = YOLO(str(model_path))
    kw: dict[str, Any] = {"verbose": False, "imgsz": int(imgsz), "conf": float(conf)}
    if device:
        kw["device"] = device
    pred = m.predict(bgr, **kw)
    boxes = pred[0].boxes if pred else None
    n = int(len(boxes)) if boxes is not None else 0
    rows = []
    if n:
        data = boxes.data.cpu().numpy()
        cls = boxes.cls.int().cpu().tolist()
        for i in range(n):
            x1, y1, x2, y2, c, _ = data[i].tolist()
            rows.append(
                {
                    "xyxy": [float(x1), float(y1), float(x2), float(y2)],
                    "conf": float(c),
                    "cls": int(cls[i]),
                }
            )
    return {"box_count": n, "boxes": rows, "names": dict(getattr(m, "names", {}) or {})}


def _raw_head_tensor(model_path: str, bgr, *, imgsz: int, device: str | None):
    """Pre-NMS head output via Ultralytics predictor (один forward)."""
    import numpy as np
    from ultralytics import YOLO

    m = YOLO(str(model_path))
    overrides: dict[str, Any] = {"imgsz": int(imgsz), "conf": 0.001, "verbose": False}
    if device:
        overrides["device"] = device
    m.predict(bgr, **overrides)
    predictor = m.predictor
    if predictor is None:
        raise RuntimeError("predictor not initialized")
    batch = predictor.preprocess([bgr])
    out = predictor.model(batch, augment=False)
    if isinstance(out, (list, tuple)):
        out = out[0]
    if hasattr(out, "detach"):
        arr = out.detach().cpu().float().numpy()
    else:
        arr = np.asarray(out, dtype=np.float32)
    return np.asarray(arr, dtype=np.float32)


def _tensor_summary(arr, *, bird_class_id: int | None = None) -> dict[str, Any]:
    import numpy as np

    flat = arr.astype(np.float64).reshape(-1)
    summary: dict[str, Any] = {
        "shape": list(arr.shape),
        "dtype": str(arr.dtype),
        "min": float(flat.min()) if flat.size else None,
        "max": float(flat.max()) if flat.size else None,
        "mean": float(flat.mean()) if flat.size else None,
        "std": float(flat.std()) if flat.size else None,
    }
    # YOLO detect head: [batch, 4+nc, anchors] — оценка max class score по каналам
    if arr.ndim == 3 and arr.shape[0] == 1 and arr.shape[1] >= 5:
        nc = arr.shape[1] - 4
        cls_scores = arr[0, 4 : 4 + nc, :]
        best_per_anchor = cls_scores.max(axis=0)
        summary["cls_channel_count"] = int(nc)
        summary["max_cls_score_global"] = float(best_per_anchor.max())
        summary["anchors_above_0.01"] = int((best_per_anchor > 0.01).sum())
        summary["anchors_above_0.05"] = int((best_per_anchor > 0.05).sum())
        if bird_class_id is not None and 0 <= bird_class_id < nc:
            bird_scores = cls_scores[bird_class_id, :]
            summary["bird_class_id"] = int(bird_class_id)
            summary["bird_max_score"] = float(bird_scores.max())
            summary["bird_anchors_above_0.01"] = int((bird_scores > 0.01).sum())
    return summary


def _compare_tensors(a, b) -> dict[str, Any]:
    import numpy as np

    if a.shape != b.shape:
        return {
            "shape_match": False,
            "shape_pt": list(a.shape),
            "shape_ov": list(b.shape),
        }
    diff = np.abs(a.astype(np.float64) - b.astype(np.float64))
    denom = float(np.linalg.norm(a.astype(np.float64)) + 1e-12)
    return {
        "shape_match": True,
        "max_abs_diff": float(diff.max()),
        "mean_abs_diff": float(diff.mean()),
        "rel_l2": float(np.linalg.norm(diff) / denom),
        "pt_summary": _tensor_summary(a),
        "ov_summary": _tensor_summary(b),
    }


def _read_ov_metadata(ov_path: str) -> dict[str, Any]:
    import yaml

    p = Path(ov_path)
    meta = p / "metadata.yaml" if p.is_dir() else p.parent / "metadata.yaml"
    if not meta.is_file():
        return {}
    try:
        data = yaml.safe_load(meta.read_text(encoding="utf-8"))
    except Exception as e:
        return {"error": str(e)}
    return data if isinstance(data, dict) else {}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", required=True, help="Путь к .mp4 или статичному кадру")
    parser.add_argument("--frame-index", type=int, default=11, help="Индекс кадра для видео")
    parser.add_argument("--pt", required=True, help="Путь к .pt (PyTorch)")
    parser.add_argument("--ov", required=True, help="Каталог OpenVINO IR или .xml")
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--conf", type=float, default=0.001)
    parser.add_argument("--pt-device", default="cpu")
    parser.add_argument("--ov-device", default="intel:cpu")
    parser.add_argument("--bird-class-id", type=int, default=None, help="Индекс класса Bird для сводки logits")
    args = parser.parse_args()

    try:
        import cv2  # noqa: F401
        import numpy as np  # noqa: F401
        from ultralytics import YOLO  # noqa: F401
    except ImportError as e:
        print(json.dumps({"error": "deps_missing", "detail": str(e)}), file=sys.stderr)
        return 2

    bgr = _read_frame(args.image, args.frame_index)
    report: dict[str, Any] = {
        "frame": _frame_stats(bgr),
        "pt_path": str(args.pt),
        "ov_path": str(args.ov),
        "imgsz": int(args.imgsz),
        "conf": float(args.conf),
        "openvino_metadata": _read_ov_metadata(args.ov),
    }

    report["post_nms"] = {
        "pytorch": _predict_boxes(
            args.pt,
            bgr,
            imgsz=args.imgsz,
            conf=args.conf,
            device=(args.pt_device or "").strip() or None,
        ),
        "openvino": _predict_boxes(
            args.ov,
            bgr,
            imgsz=args.imgsz,
            conf=args.conf,
            device=(args.ov_device or "").strip() or None,
        ),
    }

    try:
        raw_pt = _raw_head_tensor(
            args.pt,
            bgr,
            imgsz=args.imgsz,
            device=(args.pt_device or "").strip() or None,
        )
        raw_ov = _raw_head_tensor(
            args.ov,
            bgr,
            imgsz=args.imgsz,
            device=(args.ov_device or "").strip() or None,
        )
        report["pre_nms"] = {
            "pytorch": _tensor_summary(raw_pt, bird_class_id=args.bird_class_id),
            "openvino": _tensor_summary(raw_ov, bird_class_id=args.bird_class_id),
            "diff": _compare_tensors(raw_pt, raw_ov),
        }
        logits_close = bool(report["pre_nms"]["diff"].get("shape_match")) and (
            report["pre_nms"]["diff"].get("max_abs_diff", 1e9) < 0.05
        )
        report["diagnosis_hint"] = (
            "logits_match_post_nms_differs"
            if logits_close
            and report["post_nms"]["pytorch"]["box_count"] != report["post_nms"]["openvino"]["box_count"]
            else (
                "logits_diverge_export_or_quantization"
                if not logits_close
                else (
                    "both_blind_check_pt_weights"
                    if report["post_nms"]["pytorch"]["box_count"] == 0
                    and report["post_nms"]["openvino"]["box_count"] == 0
                    else "parity_ok_or_minor_diff"
                )
            )
        )
    except Exception as e:
        report["pre_nms_error"] = str(e)

    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
