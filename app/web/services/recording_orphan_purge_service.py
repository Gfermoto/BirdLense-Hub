"""Purge recording session dirs on disk without a Video row (#598)."""

from __future__ import annotations

import logging
import os
import shutil
from typing import Any

from app_config.app_config import app_config
from models import Video, db
from services.recording_orphan_inventory import _db_video_path_for_mp4
from services.recording_protection import protected_favorite_session_dirs, session_dir_for_video_path
from util import recordings_dir

_log = logging.getLogger(__name__)

ORPHAN_FILES_PURGE_CONFIRMATION = "purge_orphan_recording_files"


def _iter_orphan_sessions(*, rec_dir: str, db_paths: set[str]) -> list[dict[str, Any]]:
    orphans: list[dict[str, Any]] = []
    for root, _dirs, files in os.walk(rec_dir):
        if "video.mp4" not in files:
            continue
        mp4 = os.path.join(root, "video.mp4")
        rel_norm = _db_video_path_for_mp4(mp4, rec_dir)
        if rel_norm in db_paths:
            continue
        try:
            size = os.path.getsize(mp4)
        except OSError:
            size = 0
        orphans.append(
            {
                "video_path": rel_norm,
                "session_dir": root,
                "bytes": size,
            }
        )
    orphans.sort(key=lambda x: x["video_path"])
    return orphans


def _db_video_paths() -> set[str]:
    out: set[str] = set()
    for (vp,) in db.session.query(Video.video_path).filter(Video.video_path.isnot(None)).all():
        if vp:
            out.add(os.path.normpath(str(vp)).replace("\\", "/"))
    return out


def _skip_orphan_session(rec_dir: str, entry: dict[str, Any], protected_dirs: set[str]) -> bool:
    if not bool(app_config.get("retention.protect_favorites", True)):
        return False
    if "favorite" in os.path.basename(entry["video_path"]).lower():
        return True
    sd = session_dir_for_video_path(rec_dir, entry["video_path"])
    return bool(sd and sd in protected_dirs)


def purge_orphan_recording_files(payload: dict | None) -> tuple[dict, int]:
    data = payload if isinstance(payload, dict) else {}
    dry_run = bool(data.get("dry_run", True))
    try:
        limit = int(data.get("limit") or 500)
    except (TypeError, ValueError):
        return {"error": "limit must be an integer"}, 400
    limit = max(1, min(5000, limit))

    rec_dir = recordings_dir()
    if not rec_dir or not os.path.isdir(rec_dir):
        return {"orphan_session_count": 0, "orphan_bytes": 0, "dry_run": dry_run, "deleted_count": 0}, 200

    db_paths = _db_video_paths()
    orphans = _iter_orphan_sessions(rec_dir=rec_dir, db_paths=db_paths)
    protected_dirs = protected_favorite_session_dirs(rec_dir)
    eligible = [o for o in orphans if not _skip_orphan_session(rec_dir, o, protected_dirs)]
    skipped_protected = len(orphans) - len(eligible)

    if dry_run:
        preview = eligible[:limit]
        freed = sum(int(o["bytes"]) for o in preview)
        return {
            "dry_run": True,
            "orphan_session_count": len(orphans),
            "eligible_count": len(eligible),
            "skipped_protected": skipped_protected,
            "would_delete_count": len(preview),
            "would_free_bytes": freed,
            "sample_paths": [o["video_path"] for o in preview[:10]],
            "confirmation_phrase": ORPHAN_FILES_PURGE_CONFIRMATION,
        }, 200

    confirm = str(data.get("confirmation") or "").strip()
    if confirm != ORPHAN_FILES_PURGE_CONFIRMATION:
        return {
            "error": f"confirmation must be {ORPHAN_FILES_PURGE_CONFIRMATION!r}",
            "confirmation_phrase": ORPHAN_FILES_PURGE_CONFIRMATION,
        }, 400

    deleted = 0
    freed = 0
    errors: list[str] = []
    for entry in eligible[:limit]:
        session_dir = entry["session_dir"]
        try:
            if os.path.isdir(session_dir):
                for fname in os.listdir(session_dir):
                    fp = os.path.join(session_dir, fname)
                    if os.path.isfile(fp):
                        freed += os.path.getsize(fp)
                shutil.rmtree(session_dir)
                deleted += 1
        except OSError as exc:
            errors.append(f"{entry['video_path']}: {exc}")
            _log.warning("orphan purge failed for %s", entry["video_path"], exc_info=True)

    return {
        "dry_run": False,
        "deleted_count": deleted,
        "freed_bytes": freed,
        "skipped_protected": skipped_protected,
        "errors": errors,
    }, 200
