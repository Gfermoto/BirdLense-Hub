#!/usr/bin/env python3
"""Resolve or download golden benchmark clips (1816 noise, 1819 birds) for SOTA-09."""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
MANIFEST = REPO / "benchmarks" / "golden_clips.json"
FIXTURES_DIR = REPO / "benchmarks" / "fixtures"


def _load_manifest() -> dict:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def _resolve_from_db(db_path: Path, video_id: int) -> Path | None:
    if not db_path.is_file():
        return None
    con = sqlite3.connect(str(db_path))
    try:
        row = con.execute(
            "SELECT video_path FROM video WHERE id = ? AND (deleted_at IS NULL OR deleted_at = '')",
            (int(video_id),),
        ).fetchone()
    finally:
        con.close()
    if not row or not row[0]:
        return None
    rel = str(row[0]).strip()
    candidates = [
        REPO / "app" / rel.lstrip("/"),
        REPO / rel.lstrip("/"),
        Path(rel).expanduser(),
    ]
    for cand in candidates:
        if cand.is_file():
            return cand.resolve()
    return None


def resolve_clip_path(clip_id: str, *, db: Path | None = None) -> Path | None:
    manifest = _load_manifest()
    entry = (manifest.get("clips") or {}).get(str(clip_id))
    if not entry:
        return None
    for key in ("env_var", "legacy_env_var"):
        env_name = str(entry.get(key) or "").strip()
        if env_name:
            raw = os.environ.get(env_name, "").strip()
            if raw and Path(raw).is_file():
                return Path(raw).resolve()
    fixture = REPO / str(entry.get("fixture_path") or "")
    if fixture.is_file():
        return fixture.resolve()
    vid = entry.get("video_id")
    if db and vid is not None:
        found = _resolve_from_db(db, int(vid))
        if found:
            return found
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", default=os.environ.get("BIRDLENSE_DB", str(REPO / "app/data/db/birdlense.db")))
    ap.add_argument("--link-fixtures", action="store_true", help="Symlink resolved clips into benchmarks/fixtures/")
    args = ap.parse_args()
    db = Path(args.db)
    manifest = _load_manifest()
    ok = True
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
    for clip_id, entry in sorted((manifest.get("clips") or {}).items()):
        path = resolve_clip_path(clip_id, db=db)
        if path is None:
            print(f"MISSING {clip_id}: set {entry.get('env_var')} or place {entry.get('fixture_path')}", file=sys.stderr)
            ok = False
            continue
        print(f"OK {clip_id}: {path}")
        if args.link_fixtures:
            dest = FIXTURES_DIR / f"clip_{clip_id}.mp4"
            if dest.exists() or dest.is_symlink():
                dest.unlink()
            dest.symlink_to(path)
            print(f"  -> linked {dest}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
