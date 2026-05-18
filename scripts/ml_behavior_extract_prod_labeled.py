#!/usr/bin/env python3
"""Extract labeled Hub tracklets + crops from prod DB (approved AL + high-confidence)."""

from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ml_behavior_crop_core import extract_tracklet_crops
from ml_behavior_eval_harness import assign_splits_stratified


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_frames(raw: str | None) -> list[dict[str, Any]]:
    if not raw:
        return []
    try:
        p = json.loads(raw)
    except Exception:
        return []
    if not isinstance(p, list):
        return []
    out = []
    for f in p:
        if not isinstance(f, dict):
            continue
        b = f.get("bbox")
        if isinstance(b, list) and len(b) == 4:
            out.append({"t": float(f.get("t") or 0.0), "bbox": b})
    return out


def build_prod_manifest(
    *,
    db_path: Path,
    out_path: Path,
    crops_dir: Path,
    repo_root: Path | None,
    min_frames: int = 3,
    min_blur_score: float = 8.0,
    min_confidence: float = 0.85,
    require_approved_or_conf: bool = True,
    val_ratio: float = 0.1,
    holdout_ratio: float = 0.1,
    min_label_count: int = 5,
) -> dict[str, Any]:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    approved_videos = {
        int(r[0])
        for r in conn.execute(
            "SELECT DISTINCT video_id FROM active_learning_case WHERE status='approved' AND video_id IS NOT NULL"
        )
        if r[0] is not None
    }

    sql = """
        SELECT
          vs.id AS video_species_id,
          vs.video_id,
          vs.track_id,
          vs.frames,
          s.name AS species_name,
          v.video_path,
          v.behavior_label,
          v.behavior_confidence
        FROM video_species vs
        JOIN video v ON v.id = vs.video_id
        LEFT JOIN species s ON s.id = vs.species_id
        WHERE vs.source='video'
          AND v.deleted_at IS NULL
          AND vs.frames IS NOT NULL
          AND v.behavior_label IS NOT NULL
          AND TRIM(v.behavior_label) != ''
    """
    rows = conn.execute(sql).fetchall()
    conn.close()

    tracklets: list[dict[str, Any]] = []
    label_counts: dict[str, int] = {}

    for row in rows:
        conf = float(row["behavior_confidence"] or 0.0)
        vid = int(row["video_id"])
        approved = vid in approved_videos
        if require_approved_or_conf and not approved and conf < float(min_confidence):
            continue

        frames = _parse_frames(row["frames"])
        if len(frames) < int(min_frames):
            continue

        label = str(row["behavior_label"]).strip().lower()
        if not label or label in {"unknown", "unlabeled"}:
            continue

        tr = {
            "tracklet_id": f"v{vid}_t{int(row['track_id']) if row['track_id'] is not None else 'na'}_{int(row['video_species_id'])}",
            "video_id": vid,
            "video_species_id": int(row["video_species_id"]),
            "track_id": int(row["track_id"]) if row["track_id"] is not None else None,
            "video_path": str(row["video_path"]),
            "frame_count": len(frames),
            "boxes": frames,
            "species_name": str(row["species_name"] or "").strip() or None,
            "label": label,
            "label_source": "approved_case" if approved else "high_confidence",
            "label_confidence": conf,
            "domain_tag": "hub_prod",
        }

        crop_meta = extract_tracklet_crops(
            tr,
            crops_root=crops_dir,
            repo_root=repo_root,
            min_blur_score=float(min_blur_score),
        )
        if crop_meta is None:
            continue
        tr.update(crop_meta)
        tracklets.append(tr)
        label_counts[label] = label_counts.get(label, 0) + 1

    # Drop rare labels
    keep_labels = {lab for lab, n in label_counts.items() if n >= int(min_label_count)}
    tracklets = [t for t in tracklets if str(t.get("label")) in keep_labels]
    label_counts = {k: v for k, v in label_counts.items() if k in keep_labels}

    manifest = {
        "schema": "behavior_tracklet_manifest@v1",
        "created_at": _utc_now(),
        "source": "hub_prod_labeled",
        "db_path": str(db_path),
        "tracklet_count": len(tracklets),
        "label_counts": label_counts,
        "tracklets": tracklets,
        "crops_dir": str(crops_dir.resolve()),
        "filters": {
            "min_frames": min_frames,
            "min_blur_score": min_blur_score,
            "min_confidence": min_confidence,
            "require_approved_or_conf": require_approved_or_conf,
            "min_label_count": min_label_count,
        },
    }
    manifest = assign_splits_stratified(manifest, val_ratio=val_ratio, holdout_ratio=holdout_ratio)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--crops-dir", required=True)
    ap.add_argument("--repo-root", default="/app")
    ap.add_argument("--min-frames", type=int, default=3)
    ap.add_argument("--min-blur-score", type=float, default=5.0)
    ap.add_argument("--min-confidence", type=float, default=0.85)
    ap.add_argument("--val-ratio", type=float, default=0.1)
    ap.add_argument("--holdout-ratio", type=float, default=0.1)
    ap.add_argument("--min-label-count", type=int, default=5)
    args = ap.parse_args()

    man = build_prod_manifest(
        db_path=Path(args.db).expanduser().resolve(),
        out_path=Path(args.out).expanduser().resolve(),
        crops_dir=Path(args.crops_dir).expanduser().resolve(),
        repo_root=Path(args.repo_root).expanduser().resolve() if args.repo_root else None,
        min_frames=int(args.min_frames),
        min_blur_score=float(args.min_blur_score),
        min_confidence=float(args.min_confidence),
        val_ratio=float(args.val_ratio),
        holdout_ratio=float(args.holdout_ratio),
        min_label_count=int(args.min_label_count),
    )
    print(
        json.dumps(
            {
                "ok": True,
                "out": str(Path(args.out).resolve()),
                "tracklet_count": man["tracklet_count"],
                "label_counts": man["label_counts"],
                "split_counts": man.get("split_counts"),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
