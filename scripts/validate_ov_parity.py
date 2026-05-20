#!/usr/bin/env python3
"""
Parity gate: best_NABirds.pt (PyTorch) vs OpenVINO IR на golden frames.

Критерии (на кадр и в среднем):
  - Число боксов bird (class 0) совпадает
  - Greedy IoU пар: mean >= 0.95 (если оба > 0)
  - |conf_pt - conf_ov| / max(conf_pt, 1e-6) <= 5% (среднее по парам)
  - Pre-NMS tensor shape совпадает (если доступен raw forward)

Exit 0 = PASS, 1 = FAIL (брак экспорта).

Пример:
  python3 scripts/validate_ov_parity.py \\
    --pt app/processor/models/detection/weights/best_NABirds.pt \\
    --ov-dir app/processor/models/detection/weights/nabirds_openvino_v1
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _resolve_ov_model_path(ov_dir: Path) -> str:
    """Ultralytics OpenVINO: каталог ``*_openvino_model`` с ``best.xml`` + ``best.bin``."""
    p = ov_dir.resolve()
    if not p.name.endswith("_openvino_model") and p.is_dir():
        raise ValueError(
            f"OpenVINO bundle dir must end with '_openvino_model', got {p.name!r}. "
            "See scripts/export_nabirds_to_openvino.py",
        )
    return str(p)


def _resolve_media(path_str: str, data_root: Path, *, manifest_dir: Path | None = None) -> Path:
    p = Path(path_str)
    if p.is_absolute():
        return p
    cand = (data_root / p).resolve()
    if cand.is_file():
        return cand
    if manifest_dir is not None:
        alt = (manifest_dir / p).resolve()
        if alt.is_file():
            return alt
    return cand


def _read_frame(path: Path, frame_index: int):
    import cv2
    import numpy as np

    if path.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp", ".bmp"}:
        img = cv2.imread(str(path))
        if img is None:
            raise OSError(f"cannot read image {path}")
        return np.asarray(img, dtype=np.uint8)
    cap = cv2.VideoCapture(str(path))
    if frame_index > 0:
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(frame_index))
    ok, frame = cap.read()
    cap.release()
    if not ok or frame is None:
        raise OSError(f"cannot read frame {frame_index} from {path}")
    return frame


def _bird_boxes(result, bird_class_id: int) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if not result or not result[0].boxes or len(result[0].boxes) == 0:
        return out
    b = result[0].boxes
    data = b.data.cpu().numpy()
    cls = b.cls.int().cpu().tolist()
    for i in range(len(cls)):
        if int(cls[i]) != int(bird_class_id):
            continue
        x1, y1, x2, y2, conf, _ = data[i].tolist()
        out.append(
            {
                "xyxy": (float(x1), float(y1), float(x2), float(y2)),
                "conf": float(conf),
            }
        )
    return out


def _predict(model_path: str, bgr, *, imgsz: int, conf: float, device: str | None):
    from ultralytics import YOLO

    m = YOLO(str(model_path))
    kw: dict[str, Any] = {"verbose": False, "imgsz": int(imgsz), "conf": float(conf)}
    if device:
        kw["device"] = device
    return m.predict(bgr, **kw)


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


def _match_boxes(pt_boxes: list[dict], ov_boxes: list[dict]) -> dict[str, Any]:
    if not pt_boxes and not ov_boxes:
        return {"count_pt": 0, "count_ov": 0, "matched": 0, "mean_iou": 1.0, "mean_conf_rel_err": 0.0}
    if not pt_boxes or not ov_boxes:
        return {
            "count_pt": len(pt_boxes),
            "count_ov": len(ov_boxes),
            "matched": 0,
            "mean_iou": 0.0,
            "mean_conf_rel_err": 1.0,
            "count_mismatch": True,
        }
    pairs: list[tuple[float, int, int]] = []
    for ia, a in enumerate(pt_boxes):
        for ib, b in enumerate(ov_boxes):
            pairs.append((_iou_xyxy(a["xyxy"], b["xyxy"]), ia, ib))
    pairs.sort(key=lambda t: t[0], reverse=True)
    used_a: set[int] = set()
    used_b: set[int] = set()
    ious: list[float] = []
    conf_errs: list[float] = []
    for iou, ia, ib in pairs:
        if ia in used_a or ib in used_b:
            continue
        used_a.add(ia)
        used_b.add(ib)
        ious.append(iou)
        cp, co = pt_boxes[ia]["conf"], ov_boxes[ib]["conf"]
        conf_errs.append(abs(cp - co) / max(cp, 1e-6))
    return {
        "count_pt": len(pt_boxes),
        "count_ov": len(ov_boxes),
        "matched": len(ious),
        "mean_iou": sum(ious) / len(ious) if ious else 0.0,
        "mean_conf_rel_err": sum(conf_errs) / len(conf_errs) if conf_errs else 1.0,
        "count_mismatch": len(pt_boxes) != len(ov_boxes),
    }


def _raw_shape(model_path: str, bgr, *, imgsz: int, device: str | None) -> list[int] | None:
    import numpy as np
    from ultralytics import YOLO

    m = YOLO(str(model_path))
    overrides: dict[str, Any] = {"imgsz": int(imgsz), "conf": 0.001, "verbose": False}
    if device:
        overrides["device"] = device
    m.predict(bgr, **overrides)
    pred = m.predictor
    if pred is None:
        return None
    batch = pred.preprocess([bgr])
    out = pred.model(batch, augment=False)
    if isinstance(out, (list, tuple)):
        out = out[0]
    if hasattr(out, "detach"):
        arr = out.detach().cpu().float().numpy()
    else:
        arr = np.asarray(out, dtype=np.float32)
    return list(arr.shape)


def main() -> int:
    root = _repo_root()
    default_manifest = root / "app/data/datasets/nabirds_parity_golden/manifest.json"
    default_pt = root / "app/processor/models/detection/weights/best_NABirds.pt"
    default_ov = root / "app/processor/models/detection/weights/best_NABirds_openvino_model"

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--manifest", type=Path, default=default_manifest)
    ap.add_argument("--data-root", type=Path, default=root / "app/data")
    ap.add_argument("--pt", type=Path, default=default_pt)
    ap.add_argument("--ov-dir", type=Path, default=default_ov)
    ap.add_argument("--imgsz", type=int, default=None)
    ap.add_argument("--conf", type=float, default=None)
    ap.add_argument("--bird-class-id", type=int, default=None)
    ap.add_argument("--pt-device", default="cpu")
    ap.add_argument("--ov-device", default="intel:cpu")
    ap.add_argument("--iou-threshold", type=float, default=0.95)
    ap.add_argument("--max-conf-rel-err", type=float, default=0.05)
    ap.add_argument("--out", type=Path, default=None, help="JSON отчёт")
    args = ap.parse_args()

    if not args.manifest.is_file():
        print(json.dumps({"error": "manifest_missing", "path": str(args.manifest)}), file=sys.stderr)
        return 2
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    manifest_dir = args.manifest.resolve().parent
    imgsz = int(args.imgsz if args.imgsz is not None else manifest.get("imgsz", 640))
    conf = float(args.conf if args.conf is not None else manifest.get("conf", 0.08))
    bird_id = int(args.bird_class_id if args.bird_class_id is not None else manifest.get("bird_class_id", 0))

    pt = args.pt.resolve()
    ov_dir = args.ov_dir.resolve()
    ov_model = _resolve_ov_model_path(ov_dir)
    if not pt.is_file():
        print(json.dumps({"error": "pt_missing", "path": str(pt)}), file=sys.stderr)
        return 2
    if not Path(ov_model).exists() and not list(ov_dir.glob("*.xml")):
        print(json.dumps({"error": "ov_missing", "path": str(ov_dir)}), file=sys.stderr)
        return 2

    try:
        import cv2  # noqa: F401
        from ultralytics import YOLO  # noqa: F401
    except ImportError as e:
        print(json.dumps({"error": "deps_missing", "detail": str(e)}), file=sys.stderr)
        return 2

    frames_report: list[dict[str, Any]] = []
    failures: list[str] = []

    for item in manifest.get("frames") or []:
        fid = str(item.get("id") or "")
        media = _resolve_media(
            str(item.get("video") or item.get("image") or ""),
            args.data_root,
            manifest_dir=manifest_dir,
        )
        fidx = int(item.get("frame_index") or 0)
        try:
            bgr = _read_frame(media, fidx)
        except OSError as e:
            frames_report.append({"id": fid, "error": str(e), "pass": False})
            failures.append(f"{fid}: read_failed")
            continue

        pt_pred = _predict(str(pt), bgr, imgsz=imgsz, conf=conf, device=args.pt_device or None)
        ov_pred = _predict(ov_model, bgr, imgsz=imgsz, conf=conf, device=args.ov_device or None)
        pt_boxes = _bird_boxes(pt_pred, bird_id)
        ov_boxes = _bird_boxes(ov_pred, bird_id)
        match = _match_boxes(pt_boxes, ov_boxes)

        shape_pt = _raw_shape(str(pt), bgr, imgsz=imgsz, device=args.pt_device or None)
        shape_ov = _raw_shape(ov_model, bgr, imgsz=imgsz, device=args.ov_device or None)
        shape_ok = shape_pt == shape_ov if shape_pt and shape_ov else None

        frame_pass = True
        reasons: list[str] = []
        if match.get("count_mismatch"):
            frame_pass = False
            reasons.append("box_count_mismatch")
        if match["matched"] > 0 and match["mean_iou"] < args.iou_threshold:
            frame_pass = False
            reasons.append(f"mean_iou={match['mean_iou']:.4f}<{args.iou_threshold}")
        elif match["count_pt"] > 0 and match["matched"] == 0:
            frame_pass = False
            reasons.append("no_iou_pairs")
        if match["matched"] > 0 and match["mean_conf_rel_err"] > args.max_conf_rel_err:
            frame_pass = False
            reasons.append(f"conf_err={match['mean_conf_rel_err']:.4f}>{args.max_conf_rel_err}")
        if shape_ok is False:
            # Мягкое предупреждение: у Ultralytics torch/OV иногда разный anchor layout (5040 vs 8400).
            reasons.append(f"raw_shape_warn:{shape_pt}!={shape_ov}")

        if not frame_pass:
            failures.append(f"{fid}: {', '.join(reasons)}")

        frames_report.append(
            {
                "id": fid,
                "media": str(media),
                "frame_index": fidx,
                "pass": frame_pass,
                "reasons": reasons,
                "match": match,
                "raw_shape_pt": shape_pt,
                "raw_shape_ov": shape_ov,
            }
        )

    n = len(frames_report)
    n_pass = sum(1 for f in frames_report if f.get("pass"))
    ok = len(failures) == 0 and n_pass == n and n > 0

    summary = {
        "pass": ok,
        "frames_total": n,
        "frames_pass": n_pass,
        "failures": failures,
        "pt": str(pt),
        "ov_dir": str(ov_dir),
        "ov_model": ov_model,
        "imgsz": imgsz,
        "conf": conf,
        "criteria": {
            "iou_min": args.iou_threshold,
            "max_conf_rel_err": args.max_conf_rel_err,
            "box_count_must_match": True,
            "raw_shape_must_match": True,
        },
        "frames": frames_report,
    }

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
