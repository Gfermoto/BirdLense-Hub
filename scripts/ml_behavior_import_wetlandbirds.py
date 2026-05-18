#!/usr/bin/env python3
"""Import WetlandBirds annotations into behavior_tracklet_manifest@v1 (#457)."""

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ml_behavior_crop_core import extract_tracklet_crops
from ml_behavior_dataset_manifest import DEFAULT_TAXONOMY
from ml_behavior_eval_harness import assign_splits


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _taxonomy_map() -> dict[int, str]:
    return {int(row["id"]): str(row["label"]) for row in DEFAULT_TAXONOMY}


def import_wetlandbirds(
    *,
    annotations_root: Path,
    out_path: Path,
    split: str = "pretrain",
    domain_tag: str = "wetlandbirds",
    crops_dir: Path | None = None,
    extract_crops: bool = False,
    holdout_ratio: float | None = 0.2,
    min_blur_score: float = 0.0,
) -> dict[str, Any]:
    tax = _taxonomy_map()
    tracklets = []
    for csv_path in sorted(annotations_root.rglob("*.csv")):
        video_key = csv_path.stem
        by_subject: dict[str, list[dict[str, Any]]] = {}
        with csv_path.open("r", encoding="utf-8") as fh:
            reader = csv.reader(fh)
            frame_idx = 0
            for row in reader:
                frame_idx += 1
                if len(row) < 6:
                    continue
                try:
                    x1, y1, x2, y2 = [float(row[i]) for i in range(4)]
                    behavior_id = int(float(row[4]))
                except (TypeError, ValueError):
                    continue
                subject = str(row[5] or "").strip() or f"subject_{frame_idx}"
                species_name = str(row[6] or "").strip() if len(row) >= 7 else ""
                entry = {
                    "t": max(0.0, (frame_idx - 1) / 25.0),
                    "bbox": [x1, y1, x2, y2],
                    "behavior_id": behavior_id,
                    "species_name": species_name or None,
                }
                by_subject.setdefault(subject, []).append(entry)
        for subject_id, frames in by_subject.items():
            if len(frames) < 5:
                continue
            labels = [tax.get(int(f.get("behavior_id") or -1), "unknown") for f in frames]
            # Majority label per subject tracklet.
            label = max(set(labels), key=labels.count) if labels else "unknown"
            t_vals = [float(f.get("t") or 0.0) for f in frames]
            species_name = next((str(f["species_name"]) for f in frames if f.get("species_name")), None)
            tr = {
                    "tracklet_id": f"{video_key}_{subject_id}",
                    "video_id": None,
                    "video_species_id": None,
                    "track_id": None,
                    "camera_id": None,
                    "video_path": None,
                    "source_video_key": video_key,
                    "subject_id": subject_id,
                    "t_start_ms": int(min(t_vals) * 1000.0),
                    "t_end_ms": int(max(t_vals) * 1000.0),
                    "frame_count": len(frames),
                    "boxes": [{"t": f["t"], "bbox": f["bbox"]} for f in frames],
                    "species_name": species_name,
                    "label": label,
                    "label_source": "wetlandbirds",
                    "split": split,
                    "domain_tag": domain_tag,
                }
            if extract_crops and crops_dir is not None:
                meta = extract_tracklet_crops(
                    tr,
                    crops_root=crops_dir,
                    min_blur_score=min_blur_score,
                    min_span=0.0,
                )
                if meta is None:
                    continue
                tr.update(meta)
            tracklets.append(tr)

    label_counts: dict[str, int] = {}
    for tr in tracklets:
        lab = str(tr.get("label") or "unknown")
        label_counts[lab] = label_counts.get(lab, 0) + 1

    out = {
        "schema": "behavior_tracklet_manifest@v1",
        "created_at": _utc_now(),
        "source": "wetlandbirds_import",
        "tracklet_count": len(tracklets),
        "label_counts": label_counts,
        "tracklets": tracklets,
        "crops_dir": str(crops_dir.resolve()) if crops_dir else None,
    }
    if holdout_ratio is not None:
        out = assign_splits(out, holdout_ratio=float(holdout_ratio))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--annotations-root", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--split", default="pretrain")
    ap.add_argument("--domain-tag", default="wetlandbirds")
    ap.add_argument("--crops-dir", default="")
    ap.add_argument("--extract-crops", action="store_true")
    ap.add_argument("--holdout-ratio", type=float, default=0.2)
    ap.add_argument("--min-blur-score", type=float, default=0.0)
    args = ap.parse_args()
    root = Path(args.annotations_root).expanduser().resolve()
    if not root.is_dir():
        raise SystemExit(f"annotations root not found: {root}")
    outp = Path(args.out).expanduser().resolve()
    crops_dir = Path(args.crops_dir).expanduser().resolve() if str(args.crops_dir).strip() else None
    rep = import_wetlandbirds(
        annotations_root=root,
        out_path=outp,
        split=str(args.split).strip() or "pretrain",
        domain_tag=str(args.domain_tag).strip() or "wetlandbirds",
        crops_dir=crops_dir,
        extract_crops=bool(args.extract_crops or crops_dir),
        holdout_ratio=float(args.holdout_ratio),
        min_blur_score=float(args.min_blur_score),
    )
    print(json.dumps({"ok": True, "tracklet_count": rep["tracklet_count"], "out": str(outp)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
