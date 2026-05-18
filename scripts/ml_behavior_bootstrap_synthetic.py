#!/usr/bin/env python3
"""Bootstrap synthetic WetlandBirds + tracklets for CI/training when external data absent."""

from __future__ import annotations

import argparse
import csv
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ml_behavior_crop_core import extract_tracklet_crops
from ml_behavior_eval_harness import assign_splits
from ml_behavior_import_wetlandbirds import import_wetlandbirds


def _write_csv(path: Path, *, label_id: int, pattern: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows: list[list[Any]] = []
    for frame in range(30):
        t = frame / 25.0
        if pattern == "flying":
            x1, y1 = 0.1 + frame * 0.02, 0.2
            x2, y2 = x1 + 0.15, y1 + 0.12
        elif pattern == "feeding":
            x1, y1 = 0.35, 0.45 + 0.01 * math.sin(frame / 3.0)
            x2, y2 = x1 + 0.2, y1 + 0.18
        else:
            x1, y1 = 0.5, 0.5
            x2, y2 = x1 + 0.12, y1 + 0.1
        rows.append([x1, y1, x2, y2, label_id, f"sub_{pattern}", "synthetic"])
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        for r in rows:
            w.writerow(r)


def bootstrap_synthetic(
    *,
    out_root: Path,
    per_label: int = 24,
) -> dict[str, Any]:
    ann = out_root / "wetlandbirds_synthetic"
    ann.mkdir(parents=True, exist_ok=True)
    for lab, bid, pat in [("feeding", 2, "feeding"), ("flying", 3, "flying"), ("alert", 1, "alert")]:
        for i in range(max(1, per_label // 8)):
            _write_csv(ann / f"{pat}_{i}.csv", label_id=bid, pattern=pat)

    wb_manifest = out_root / "wetland_tracklets.json"
    import_wetlandbirds(annotations_root=ann, out_path=wb_manifest, domain_tag="wetlandbirds_synthetic")

    payload = json.loads(wb_manifest.read_text(encoding="utf-8"))
    tracklets = payload.get("tracklets") or []
    crops_dir = out_root / "behavior_crops"
    crops_dir.mkdir(parents=True, exist_ok=True)
    kept: list[dict[str, Any]] = []
    for tr in tracklets:
        if not isinstance(tr, dict):
            continue
        meta = extract_tracklet_crops(tr, crops_root=crops_dir, min_blur_score=0.0, min_span=0.0)
        if meta is None:
            continue
        tr.update(meta)
        kept.append(tr)
    payload["tracklets"] = kept
    payload["tracklet_count"] = len(kept)
    payload = assign_splits(payload, holdout_ratio=0.2)
    payload["crops_dir"] = str(crops_dir.resolve())
    merged_path = out_root / "behavior_tracklet_merged.json"
    merged_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"manifest": str(merged_path), "crops_dir": str(crops_dir), "tracklet_count": len(kept)}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out-root", default="app/data/datasets/behavior_v2_synthetic")
    ap.add_argument("--per-label", type=int, default=24)
    args = ap.parse_args()
    rep = bootstrap_synthetic(out_root=Path(args.out_root).expanduser().resolve(), per_label=int(args.per_label))
    print(json.dumps({"ok": True, **rep}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
