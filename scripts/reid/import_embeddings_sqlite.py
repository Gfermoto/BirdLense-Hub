#!/usr/bin/env python3
"""Import offline Re-ID embeddings JSONL into a local SQLite sidecar table (#374).

Input is the output of ``embed_dinov2_crop.py``. Optional manifest is the JSONL
from ``export_crops_from_sqlite.py --manifest``; when present, rows are linked
to ``video_species_id`` / ``video_id``.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path


def _ensure_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS reid_embedding (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            video_species_id INTEGER,
            video_id INTEGER,
            species_id INTEGER,
            track_id INTEGER,
            crop_path TEXT NOT NULL UNIQUE,
            model TEXT NOT NULL,
            dim INTEGER NOT NULL,
            embedding_json TEXT NOT NULL,
            species_name TEXT,
            individual_label TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """,
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS ix_reid_embedding_video_species_id "
        "ON reid_embedding(video_species_id)",
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS ix_reid_embedding_species_id "
        "ON reid_embedding(species_id)",
    )


def _load_manifest(path: Path | None) -> dict[str, dict]:
    if not path:
        return {}
    out: dict[str, dict] = {}
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            row = json.loads(line)
            crop = row.get("crop_path")
            if crop:
                out[str(Path(crop).resolve())] = row
    return out


def _validate_embedding(row: dict) -> tuple[str, str, int, list[float]] | None:
    crop_path = row.get("path")
    model = row.get("model")
    emb = row.get("embedding")
    if not crop_path or not model or not isinstance(emb, list):
        return None
    vals: list[float] = []
    for v in emb:
        try:
            vals.append(float(v))
        except (TypeError, ValueError):
            return None
    dim = int(row.get("dim") or len(vals))
    if dim != len(vals) or dim <= 0:
        return None
    return str(Path(crop_path).resolve()), str(model), dim, vals


def import_embeddings(args) -> int:
    manifest = _load_manifest(Path(args.manifest) if args.manifest else None)
    conn = sqlite3.connect(args.db)
    try:
        _ensure_table(conn)
        written = 0
        skipped = 0
        with open(args.jsonl, encoding="utf-8") as fh:
            for line in fh:
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                except ValueError:
                    skipped += 1
                    continue
                parsed = _validate_embedding(row)
                if parsed is None:
                    skipped += 1
                    continue
                crop_path, model, dim, vals = parsed
                meta = manifest.get(crop_path, {})
                conn.execute(
                    """
                    INSERT INTO reid_embedding (
                        video_species_id, video_id, species_id, track_id,
                        crop_path, model, dim, embedding_json, species_name
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(crop_path) DO UPDATE SET
                        model=excluded.model,
                        dim=excluded.dim,
                        embedding_json=excluded.embedding_json,
                        species_name=excluded.species_name
                    """,
                    (
                        meta.get("video_species_id"),
                        meta.get("video_id"),
                        meta.get("species_id"),
                        meta.get("track_id"),
                        crop_path,
                        model,
                        dim,
                        json.dumps(vals, separators=(",", ":")),
                        meta.get("species_name"),
                    ),
                )
                written += 1
        conn.commit()
    finally:
        conn.close()
    print(json.dumps({"rows_written": written, "rows_skipped": skipped}), file=sys.stderr)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", required=True, help="Path to birdlense.db or sidecar sqlite")
    ap.add_argument("--jsonl", required=True, help="embed_dinov2_crop.py JSONL")
    ap.add_argument("--manifest", default="", help="export_crops_from_sqlite.py manifest JSONL")
    args = ap.parse_args()
    return import_embeddings(args)


if __name__ == "__main__":
    raise SystemExit(main())
