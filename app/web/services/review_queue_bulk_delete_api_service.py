"""Превью и применение bulk-delete review queue (#293)."""

from __future__ import annotations

import logging
import os
import shutil
from typing import Any

import util as _util
from services.http_response_cache import (
    bust_response_caches,
    bust_system_response_caches,
)
from services.retention_service import _delete_video_row_cascade
from services.review_queue_bulk_plan import resolve_review_queue_bulk_plan
from services.storage_tree_utils import get_tree_storage_info

_log = logging.getLogger(__name__)


def build_review_queue_delete_preview_payload(
    session: Any,
    payload: dict | None,
) -> tuple[dict, int]:
    try:
        plan = resolve_review_queue_bulk_plan(session, payload or {})
        return {
            "confirmation_phrase": plan["confirmation_phrase"],
            "date": plan["date"],
            "time_of_day": plan["time_of_day"],
            "hour": plan["hour"],
            "unknown_count": plan["unknown_count"],
            "video_count": plan["video_count"],
            "unknown_ids": plan["unknown_ids"],
            "video_ids": plan["video_ids"],
            "missing_video_ids": plan["missing_video_ids"],
            "videos": plan["preview_videos"],
        }, 200
    except ValueError as exc:
        return {"error": str(exc)}, 400
    except Exception:
        _log.exception("Review queue delete preview failed")
        return {"error": "Failed to build review queue delete preview"}, 500


def execute_review_queue_bulk_delete(
    session: Any,
    payload: dict | None,
) -> tuple[dict, int]:
    try:
        plan = resolve_review_queue_bulk_plan(session, payload or {})
        confirm_text = str((payload or {}).get("confirm_text") or "").strip()
        phrase = plan["confirmation_phrase"]
        if confirm_text != phrase:
            return {
                "error": f'Confirmation text must be "{phrase}"',
            }, 400

        deleted_video_ids: list[int] = []
        deleted_dirs: set[str] = set()
        deleted_files = 0
        deleted_size = 0
        for video_id in plan["video_ids"]:
            video = plan["videos_by_id"].get(video_id)
            if not video:
                continue
            vp = video.video_path
            full_path = _util.full_path_for_video(vp) if vp else None
            if full_path and os.path.isdir(os.path.dirname(full_path)):
                deleted_dirs.add(os.path.dirname(full_path))
            _delete_video_row_cascade(video)
            deleted_video_ids.append(video_id)

        session.commit()

        for dir_path in sorted(deleted_dirs):
            if not os.path.isdir(dir_path):
                continue
            count, size = get_tree_storage_info(dir_path)
            deleted_files += count
            deleted_size += size
            shutil.rmtree(dir_path)

        bust_response_caches()
        bust_system_response_caches()
        n = len(deleted_video_ids)
        return {
            "message": f"Deleted {n} review-queue videos",
            "deletedCount": n,
            "deletedVideoIds": deleted_video_ids,
            "deletedDirs": len(deleted_dirs),
            "deletedFiles": deleted_files,
            "deletedSize": deleted_size,
            "confirmation_phrase": phrase,
        }, 200
    except ValueError as exc:
        session.rollback()
        return {"error": str(exc)}, 400
    except Exception:
        session.rollback()
        _log.exception("Review queue delete failed")
        return {"error": "Failed to delete review queue videos"}, 500
