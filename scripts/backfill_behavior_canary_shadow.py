#!/usr/bin/env python3
"""Backfill behavior_shadow_* on existing videos (canary video_v2 OpenVINO)."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", default="/app/data/db/birdlense.db")
    ap.add_argument("--video-ids", default="", help="Comma-separated ids")
    ap.add_argument("--since", default="", help="ISO created_at lower bound")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    for p in ("/app/processor/src", "/app/scripts", "/app"):
        if p not in sys.path:
            sys.path.insert(0, p)

    from app_config.app_config import app_config as cfg
    from behavior_baseline_runtime import maybe_predict_video_behavior_bundle

    con = sqlite3.connect(args.db)
    con.row_factory = sqlite3.Row
    if args.video_ids.strip():
        ids = [int(x.strip()) for x in args.video_ids.split(",") if x.strip()]
        placeholders = ",".join("?" * len(ids))
        videos = con.execute(
            f"SELECT id, video_path, behavior_label, behavior_shadow_label FROM video WHERE id IN ({placeholders})",
            ids,
        ).fetchall()
    elif args.since.strip():
        videos = con.execute(
            "SELECT id, video_path, behavior_label, behavior_shadow_label FROM video "
            "WHERE deleted_at IS NULL AND created_at >= ? ORDER BY id",
            (args.since.strip(),),
        ).fetchall()
    else:
        print(json.dumps({"error": "provide --video-ids or --since"}))
        return 1

    updated = 0
    rows_out = []
    for v in videos:
        species = con.execute(
            "SELECT track_id, frames FROM video_species WHERE video_id=?",
            (int(v["id"]),),
        ).fetchall()
        dets = []
        for sp in species:
            fr = json.loads(sp["frames"] or "[]")
            dets.append({"frames": fr, "track_id": sp["track_id"]})
        bundle = maybe_predict_video_behavior_bundle(
            cfg,
            dets,
            duration_s=30.0,
            processor_cwd="/app/processor",
            video_path=v["video_path"],
        )
        sl = bundle.get("shadow_label")
        sc = bundle.get("shadow_confidence")
        sk = bundle.get("shadow_model_kind")
        sv = bundle.get("shadow_model_version")
        saved = bool(sl and str(sl).strip())
        rows_out.append(
            {
                "video_id": int(v["id"]),
                "old_shadow": v["behavior_shadow_label"],
                "new_shadow": sl,
                "conf": sc,
                "saved": saved,
            }
        )
        if saved and not args.dry_run:
            con.execute(
                """
                UPDATE video SET
                  behavior_shadow_label=?,
                  behavior_shadow_confidence=?,
                  behavior_shadow_model_kind=?,
                  behavior_shadow_model_version=?
                WHERE id=?
                """,
                (
                    str(sl).strip()[:32],
                    float(sc or 0.0),
                    str(sk or "")[:32] if sk else None,
                    str(sv or "")[:96] if sv else None,
                    int(v["id"]),
                ),
            )
            updated += 1
    if not args.dry_run:
        con.commit()
    con.close()
    print(json.dumps({"ok": True, "updated": updated, "dry_run": args.dry_run, "rows": rows_out}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
