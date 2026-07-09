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
from services.session_manifest_io import orphan_purge_grace_skip
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


def _orphan_purge_grace_minutes() -> float:
    try:
        minutes = float(app_config.get("reconcile.orphan_purge_grace_minutes") or 15)
    except (TypeError, ValueError):
        minutes = 15.0
    return max(0.0, min(1440.0, minutes))


def _orphan_purge_min_bytes() -> int:
    try:
        val = int(app_config.get("reconcile.orphan_purge_min_bytes") or 512)
    except (TypeError, ValueError):
        val = 512
    return max(0, min(10_000_000, val))


def _skip_orphan_session(
    rec_dir: str,
    entry: dict[str, Any],
    protected_dirs: set[str],
    *,
    grace_minutes: float,
    min_bytes: int,
) -> str | None:
    if not bool(app_config.get("retention.protect_favorites", True)):
        pass
    elif "favorite" in os.path.basename(entry["video_path"]).lower():
        return "protected"
    else:
        sd = session_dir_for_video_path(rec_dir, entry["video_path"])
        if sd and sd in protected_dirs:
            return "protected"

    if orphan_purge_grace_skip(
        entry["session_dir"],
        video_bytes=int(entry.get("bytes") or 0),
        grace_minutes=grace_minutes,
        min_bytes=min_bytes,
    ):
        return "grace"
    return None


def _coerce_orphan_purge_limit(raw: object, *, default: int = 500) -> int | None:
    try:
        limit = int(raw if raw is not None else default)
    except (TypeError, ValueError):
        return None
    return max(1, min(5000, limit))


def _plan_orphan_recording_purge(*, limit: int = 500) -> dict[str, Any]:
    """Eligible orphan disk sessions for purge or dry-run preview."""
    rec_dir = recordings_dir()
    if not rec_dir or not os.path.isdir(rec_dir):
        return {
            "eligible": [],
            "orphan_session_count": 0,
            "skipped_protected": 0,
            "skipped_grace": 0,
            "limit": limit,
        }

    grace_minutes = _orphan_purge_grace_minutes()
    min_bytes = _orphan_purge_min_bytes()
    db_paths = _db_video_paths()
    orphans = _iter_orphan_sessions(rec_dir=rec_dir, db_paths=db_paths)
    protected_dirs = protected_favorite_session_dirs(rec_dir)
    eligible: list[dict[str, Any]] = []
    skipped_protected = 0
    skipped_grace = 0
    for orphan in orphans:
        reason = _skip_orphan_session(
            rec_dir,
            orphan,
            protected_dirs,
            grace_minutes=grace_minutes,
            min_bytes=min_bytes,
        )
        if reason == "protected":
            skipped_protected += 1
        elif reason == "grace":
            skipped_grace += 1
        else:
            eligible.append(orphan)

    return {
        "eligible": eligible,
        "orphan_session_count": len(orphans),
        "skipped_protected": skipped_protected,
        "skipped_grace": skipped_grace,
        "limit": limit,
    }


def preview_orphan_recording_purge(*, limit: int = 500) -> dict[str, Any]:
    """Dry-run: report orphan disk sessions reconcile would delete."""
    plan = _plan_orphan_recording_purge(limit=limit)
    preview = plan["eligible"][:limit]
    would_free = sum(int(o["bytes"]) for o in preview)
    sample_paths = [o["video_path"] for o in preview[:10]]
    if preview:
        _log.info(
            "orphan purge dry-run: would_delete=%s would_free_bytes=%s sample=%s",
            len(preview),
            would_free,
            sample_paths[:3],
        )
    return {
        "dry_run": True,
        "would_delete_count": len(preview),
        "would_free_bytes": would_free,
        "deleted_count": 0,
        "freed_bytes": 0,
        "orphan_session_count": plan["orphan_session_count"],
        "eligible_count": len(plan["eligible"]),
        "skipped_protected": plan["skipped_protected"],
        "skipped_grace": plan["skipped_grace"],
        "sample_paths": sample_paths,
    }


def apply_orphan_recording_purge(*, limit: int = 500) -> dict[str, Any]:
    """Delete eligible disk-only sessions (no confirmation; reconcile/scheduler)."""
    plan = _plan_orphan_recording_purge(limit=limit)
    if not plan["eligible"] and plan["orphan_session_count"] == 0:
        return {
            "deleted_count": 0,
            "freed_bytes": 0,
            "orphan_session_count": 0,
            "skipped_protected": 0,
            "skipped_grace": 0,
            "errors": [],
        }

    eligible = plan["eligible"]
    skipped_protected = plan["skipped_protected"]
    skipped_grace = plan["skipped_grace"]
    orphans_count = plan["orphan_session_count"]

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

    if deleted or skipped_grace or skipped_protected:
        _log.info(
            "orphan purge: deleted=%s freed_bytes=%s skipped_grace=%s skipped_protected=%s orphans=%s",
            deleted,
            freed,
            skipped_grace,
            skipped_protected,
            orphans_count,
        )

    return {
        "deleted_count": deleted,
        "freed_bytes": freed,
        "orphan_session_count": orphans_count,
        "skipped_protected": skipped_protected,
        "skipped_grace": skipped_grace,
        "errors": errors,
    }


def purge_orphan_recording_files(payload: dict | None) -> tuple[dict, int]:
    data = payload if isinstance(payload, dict) else {}
    dry_run = bool(data.get("dry_run", True))
    limit = _coerce_orphan_purge_limit(data.get("limit"))
    if limit is None:
        return {"error": "limit must be an integer"}, 400

    rec_dir = recordings_dir()
    if not rec_dir or not os.path.isdir(rec_dir):
        return {"orphan_session_count": 0, "orphan_bytes": 0, "dry_run": dry_run, "deleted_count": 0}, 200

    grace_minutes = _orphan_purge_grace_minutes()
    min_bytes = _orphan_purge_min_bytes()
    db_paths = _db_video_paths()
    orphans = _iter_orphan_sessions(rec_dir=rec_dir, db_paths=db_paths)
    protected_dirs = protected_favorite_session_dirs(rec_dir)
    eligible: list[dict[str, Any]] = []
    skipped_protected = 0
    skipped_grace = 0
    for orphan in orphans:
        reason = _skip_orphan_session(
            rec_dir,
            orphan,
            protected_dirs,
            grace_minutes=grace_minutes,
            min_bytes=min_bytes,
        )
        if reason == "protected":
            skipped_protected += 1
        elif reason == "grace":
            skipped_grace += 1
        else:
            eligible.append(orphan)

    if dry_run:
        preview = eligible[:limit]
        freed = sum(int(o["bytes"]) for o in preview)
        return {
            "dry_run": True,
            "orphan_session_count": len(orphans),
            "eligible_count": len(eligible),
            "skipped_protected": skipped_protected,
            "skipped_grace": skipped_grace,
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

    result = apply_orphan_recording_purge(limit=limit)
    return {
        "dry_run": False,
        "deleted_count": result["deleted_count"],
        "freed_bytes": result["freed_bytes"],
        "skipped_protected": result["skipped_protected"],
        "skipped_grace": result.get("skipped_grace", 0),
        "errors": result["errors"],
    }, 200
