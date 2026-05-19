#!/usr/bin/env python3
"""Harvest priority behavior crops during nightly marathon (flying + discrepancies)."""

from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ml_behavior_crop_core import extract_tracklet_crops


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
        if isinstance(f, dict) and isinstance(f.get("bbox"), list) and len(f["bbox"]) == 4:
            out.append({"t": float(f.get("t") or 0.0), "bbox": f["bbox"]})
    return out


def _priority(
    *,
    meta: str | None,
    shadow: str | None,
    meta_conf: float,
    shadow_conf: float,
) -> tuple[int, str]:
    ml = (meta or "").strip().lower()
    sl = (shadow or "").strip().lower()
    if ml and sl and ml != sl:
        return 100, "discrepancy"
    if sl == "flying" or ml == "flying":
        return 90, "flying"
    if ml == "flying" and sl == "feeding":
        return 95, "flying_vs_feeding"
    if shadow_conf > 0 and shadow_conf < 0.45:
        return 70, "low_video_conf"
    if meta_conf > 0 and meta_conf < 0.45:
        return 65, "low_meta_conf"
    return 10, "other"


def harvest_since(
    *,
    db_path: Path,
    crops_root: Path,
    repo_root: Path | None,
    since_iso: str,
    min_frames: int = 3,
    min_blur_score: float = 4.0,
    min_priority: int = 65,
    limit: int = 200,
    manifest_append: Path | None = None,
) -> dict[str, Any]:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT
          vs.id AS video_species_id,
          vs.video_id,
          vs.track_id,
          vs.frames,
          v.video_path,
          v.behavior_label,
          v.behavior_confidence,
          v.behavior_shadow_label,
          v.behavior_shadow_confidence,
          v.created_at
        FROM video_species vs
        JOIN video v ON v.id = vs.video_id
        WHERE v.deleted_at IS NULL
          AND vs.frames IS NOT NULL
          AND v.created_at >= ?
        ORDER BY v.id DESC
        """,
        (since_iso,),
    ).fetchall()
    conn.close()

    saved = 0
    skipped = 0
    by_reason: dict[str, int] = {}
    by_label: dict[str, int] = {}

    for row in rows:
        frames = _parse_frames(row["frames"])
        if len(frames) < min_frames:
            skipped += 1
            continue
        meta = str(row["behavior_label"] or "").strip().lower() or None
        shadow = str(row["behavior_shadow_label"] or "").strip().lower() or None
        pri, reason = _priority(
            meta=meta,
            shadow=shadow,
            meta_conf=float(row["behavior_confidence"] or 0.0),
            shadow_conf=float(row["behavior_shadow_confidence"] or 0.0),
        )
        if pri < min_priority:
            skipped += 1
            continue

        label = shadow or meta or "unlabeled"
        tr = {
            "tracklet_id": f"v{int(row['video_id'])}_t{int(row['track_id']) if row['track_id'] is not None else 'na'}_{int(row['video_species_id'])}",
            "video_id": int(row["video_id"]),
            "video_species_id": int(row["video_species_id"]),
            "track_id": int(row["track_id"]) if row["track_id"] is not None else None,
            "video_path": str(row["video_path"]),
            "frame_count": len(frames),
            "boxes": frames,
            "label": label,
            "label_source": f"nightly_{reason}",
            "meta_label": meta,
            "shadow_label": shadow,
            "priority": pri,
            "harvest_reason": reason,
            "domain_tag": "hub_nightly",
        }
        crop_meta = extract_tracklet_crops(
            tr,
            crops_root=crops_root,
            repo_root=repo_root,
            min_blur_score=min_blur_score,
            min_span=0.0,
        )
        if crop_meta is None:
            skipped += 1
            continue
        tr.update(crop_meta)
        saved += 1
        by_reason[reason] = by_reason.get(reason, 0) + 1
        by_label[label] = by_label.get(label, 0) + 1

        if manifest_append is not None:
            manifest_append.parent.mkdir(parents=True, exist_ok=True)
            with manifest_append.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(tr, ensure_ascii=False) + "\n")

        if saved >= limit:
            break

    return {
        "saved": saved,
        "skipped": skipped,
        "by_reason": by_reason,
        "by_label": by_label,
        "crops_dir": str(crops_root.resolve()),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", required=True)
    ap.add_argument("--crops-dir", required=True)
    ap.add_argument("--since", required=True, help="ISO timestamp UTC")
    ap.add_argument("--repo-root", default="/app")
    ap.add_argument("--manifest-append", default="")
    ap.add_argument("--min-priority", type=int, default=65)
    ap.add_argument("--limit", type=int, default=200)
    args = ap.parse_args()
    rep = harvest_since(
        db_path=Path(args.db).expanduser().resolve(),
        crops_root=Path(args.crops_dir).expanduser().resolve(),
        repo_root=Path(args.repo_root).expanduser().resolve() if args.repo_root else None,
        since_iso=str(args.since),
        min_priority=int(args.min_priority),
        limit=int(args.limit),
        manifest_append=Path(args.manifest_append) if args.manifest_append else None,
    )
    rep["at"] = _utc_now()
    print(json.dumps({"ok": True, **rep}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
