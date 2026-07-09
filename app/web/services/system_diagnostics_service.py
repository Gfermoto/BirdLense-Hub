"""Логика admin diagnostics ``/api/ui/system/diagnostics/*`` (#293)."""

from __future__ import annotations

import json
import logging
import os
import shutil
import time
from datetime import datetime, timezone

import data_paths

from app_config.app_config import app_config
from models import ActivityLog, Species, Video, VideoSpecies, db
from services.broken_videos_inventory_service import (
    broken_video_row_payload,
    broken_video_row_reason,
    scan_broken_videos_inventory,
    video_row_has_no_species,
    videos_with_species_exist_clause,
)
from services.http_response_cache import bust_response_caches, bust_system_response_caches
from services.retention_service import _delete_video_row_cascade
from services.storage_tree_utils import get_tree_storage_info
from services.system_route_payload_parsers import parse_video_ids

_log = logging.getLogger(__name__)

BROKEN_VIDEOS_DELETE_CONFIRMATION = "delete_broken_video_rows"
BROKEN_VIDEOS_PURGE_CONFIRMATION = "purge_all_broken_video_rows"
NO_SPECIES_VIDEOS_PURGE_CONFIRMATION = "purge_videos_without_species"
# Squirrel — устаревшее имя в БД до канона Rodent
REVIEW_ONLY_NOISE_SPECIES = ("Bird", "Rodent", "Squirrel")


def parse_broken_videos_list_params(args) -> tuple[int, int, int]:
    """limit, after_id, max_scan; raises ValueError on bad input."""
    limit = int(args.get("limit") or 50)
    limit = max(1, min(limit, 200))
    after_id = int(args.get("after_id") or 0)
    max_scan = int(args.get("max_scan") or 5000)
    max_scan = max(1, min(max_scan, 20000))
    return limit, after_id, max_scan


def build_broken_videos_list_response(
    limit: int,
    after_id: int,
    max_scan: int,
) -> dict:
    items: list[dict] = []
    scanned = 0
    cursor = after_id
    while len(items) < limit and scanned < max_scan:
        batch = Video.query.filter(Video.id > cursor).order_by(Video.id.asc()).limit(200).all()
        if not batch:
            break
        for video in batch:
            scanned += 1
            if scanned > max_scan:
                break
            row = broken_video_row_payload(video)
            if row:
                items.append(row)
            if len(items) >= limit:
                break
        cursor = batch[-1].id

    next_after = None
    if items and len(items) == limit:
        next_after = items[-1]["video_id"]
    return {
        "bucket": "broken_video_row",
        "items": items,
        "scanned": scanned,
        "after_id": after_id,
        "next_after_id": next_after,
        "confirmation_phrase_delete": BROKEN_VIDEOS_DELETE_CONFIRMATION,
        "confirmation_phrase_purge": BROKEN_VIDEOS_PURGE_CONFIRMATION,
    }


def preview_broken_video_rows_delete(payload) -> tuple[dict, int]:
    try:
        video_ids = parse_video_ids(payload)
        if not video_ids:
            return {"error": "video_ids is required"}, 400
        videos = Video.query.filter(Video.id.in_(video_ids)).all()
        by_id = {v.id: v for v in videos}
        missing = [vid for vid in video_ids if vid not in by_id]
        if missing:
            return {"error": "Some video_ids not found", "missing_video_ids": missing}, 400
        previews = []
        not_broken = []
        for vid in video_ids:
            v = by_id[vid]
            row = broken_video_row_payload(v)
            if row:
                previews.append(row)
            else:
                not_broken.append(vid)
        if not_broken:
            return {
                "error": "Some videos are not broken (file exists); refusing preview",
                "not_broken_video_ids": sorted(not_broken),
            }, 400
        return {
            "confirmation_phrase": BROKEN_VIDEOS_DELETE_CONFIRMATION,
            "video_ids": video_ids,
            "video_count": len(video_ids),
            "videos": previews,
        }, 200
    except ValueError as exc:
        return {"error": str(exc)}, 400


def _cascade_delete_videos_collect_dirs(videos: list[Video]) -> tuple[list[int], set[str]]:
    deleted_video_ids: list[int] = []
    deleted_dirs: set[str] = set()
    for video in videos:
        vp = video.video_path
        full_path = data_paths.full_path_for_video(vp) if vp else None
        if full_path and os.path.isdir(os.path.dirname(full_path)):
            deleted_dirs.add(os.path.dirname(full_path))
        _delete_video_row_cascade(video)
        deleted_video_ids.append(video.id)
    return deleted_video_ids, deleted_dirs


def _remove_recording_dirs(deleted_dirs: set[str]) -> tuple[int, int]:
    deleted_files = 0
    deleted_size = 0
    for dir_path in sorted(deleted_dirs):
        if not os.path.isdir(dir_path):
            continue
        count, size = get_tree_storage_info(dir_path)
        deleted_files += count
        deleted_size += size
        shutil.rmtree(dir_path)
    return deleted_files, deleted_size


def delete_broken_video_rows(payload) -> tuple[dict, int]:
    try:
        video_ids = parse_video_ids(payload)
        if not video_ids:
            return {"error": "video_ids is required"}, 400
        confirm_text = str((payload or {}).get("confirm_text") or "").strip()
        if confirm_text != BROKEN_VIDEOS_DELETE_CONFIRMATION:
            return {
                "error": f'Confirmation text must be "{BROKEN_VIDEOS_DELETE_CONFIRMATION}"',
            }, 400

        videos = Video.query.filter(Video.id.in_(video_ids)).all()
        by_id = {v.id: v for v in videos}
        missing = [vid for vid in video_ids if vid not in by_id]
        if missing:
            return {"error": "Some video_ids not found", "missing_video_ids": missing}, 400

        not_broken = []
        for vid in video_ids:
            if broken_video_row_payload(by_id[vid]) is None:
                not_broken.append(vid)
        if not_broken:
            return {
                "error": "Some videos are not broken (file exists); refusing delete",
                "not_broken_video_ids": sorted(not_broken),
            }, 400

        ordered = [by_id[vid] for vid in video_ids]
        deleted_video_ids, deleted_dirs = _cascade_delete_videos_collect_dirs(ordered)

        cleanup_log = ActivityLog(
            type="admin_diagnostics_cleanup",
            data=json.dumps(
                {
                    "action": "broken_video_rows_delete",
                    "bucket": "broken_video_row",
                    "video_ids": deleted_video_ids,
                }
            ),
        )
        db.session.add(cleanup_log)
        db.session.commit()

        deleted_files, deleted_size = _remove_recording_dirs(deleted_dirs)
        bust_response_caches()
        bust_system_response_caches()
        return {
            "message": f"Deleted {len(deleted_video_ids)} broken video rows",
            "deletedCount": len(deleted_video_ids),
            "deletedVideoIds": deleted_video_ids,
            "deletedDirs": len(deleted_dirs),
            "deletedFiles": deleted_files,
            "deletedSize": deleted_size,
            "confirmation_phrase": BROKEN_VIDEOS_DELETE_CONFIRMATION,
        }, 200
    except ValueError as exc:
        db.session.rollback()
        return {"error": str(exc)}, 400
    except Exception as e:
        db.session.rollback()
        _log.exception("Broken video rows delete failed: %s", e)
        return {"error": "Failed to delete broken video rows"}, 500


def preview_broken_video_rows_purge(*, limit: int = 100, max_scan: int = 100_000) -> dict:
    """Dry-run: report broken Video rows reconcile would delete."""
    max_scan = max(1000, min(max_scan, 500_000))
    limit = max(1, min(limit, 5000))
    inv = scan_broken_videos_inventory(
        max_scan=max_scan,
        collect_ids_limit=limit,
    )
    video_ids = inv["ids_to_delete"]
    if video_ids:
        _log.info(
            "broken db purge dry-run: would_delete=%s sample_video_ids=%s",
            len(video_ids),
            video_ids[:5],
        )
    return {
        "dry_run": True,
        "would_delete_count": len(video_ids),
        "deleted_count": 0,
        "sample_video_ids": video_ids[:10],
        "scanned": inv["scanned"],
        "broken_total": inv["broken_total"],
        "by_reason": inv["by_reason"],
        "more_batches_suggested": len(video_ids) >= limit,
    }


def apply_broken_video_rows_purge(*, limit: int = 100, max_scan: int = 100_000) -> dict:
    """Remove broken Video rows (missing/unreadable file); reconcile internal path."""
    max_scan = max(1000, min(max_scan, 500_000))
    limit = max(1, min(limit, 5000))
    inv = scan_broken_videos_inventory(
        max_scan=max_scan,
        collect_ids_limit=limit,
    )
    video_ids = inv["ids_to_delete"]
    if not video_ids:
        return {
            "deleted_count": 0,
            "scanned": inv["scanned"],
            "more_batches_suggested": False,
        }

    videos = Video.query.filter(Video.id.in_(video_ids)).all()
    by_id = {v.id: v for v in videos}
    not_broken = [vid for vid in video_ids if vid not in by_id or broken_video_row_payload(by_id[vid]) is None]
    if not_broken:
        return {
            "deleted_count": 0,
            "skipped_not_broken": sorted(not_broken),
            "scanned": inv["scanned"],
        }

    ordered = [by_id[vid] for vid in video_ids if vid in by_id]
    deleted_video_ids, deleted_dirs = _cascade_delete_videos_collect_dirs(ordered)

    cleanup_log = ActivityLog(
        type="admin_diagnostics_cleanup",
        data=json.dumps(
            {
                "action": "broken_video_rows_reconcile_purge",
                "bucket": "broken_video_row",
                "video_ids": deleted_video_ids,
                "batch_limit": limit,
            }
        ),
    )
    db.session.add(cleanup_log)
    db.session.commit()

    deleted_files, deleted_size = _remove_recording_dirs(deleted_dirs)
    bust_response_caches()
    bust_system_response_caches()
    return {
        "deleted_count": len(deleted_video_ids),
        "deleted_video_ids": deleted_video_ids,
        "deleted_files": deleted_files,
        "deleted_size": deleted_size,
        "scanned": inv["scanned"],
        "more_batches_suggested": len(deleted_video_ids) >= limit,
    }


def purge_broken_video_rows(payload) -> tuple[dict, int]:
    try:
        dry_run = bool(payload.get("dry_run", True))
        max_scan = int(payload.get("max_scan") or 100_000)
        max_scan = max(1000, min(max_scan, 500_000))
        limit = int(payload.get("limit") or 500)
        limit = max(1, min(limit, 5000))

        if dry_run:
            inv = scan_broken_videos_inventory(
                max_scan=max_scan,
                collect_ids_limit=None,
            )
            return {
                "dry_run": True,
                "scanned": inv["scanned"],
                "broken_total": inv["broken_total"],
                "by_reason": inv["by_reason"],
                "sample_video_ids": inv["sample_video_ids"],
                "confirmation_phrase": BROKEN_VIDEOS_PURGE_CONFIRMATION,
                "note": ("Повторяйте POST с dry_run:false и тем же confirm_text, пока deletedCount не станет 0."),
            }, 200

        confirm_text = str((payload or {}).get("confirm_text") or "").strip()
        if confirm_text != BROKEN_VIDEOS_PURGE_CONFIRMATION:
            return {
                "error": (f'Confirmation text must be "{BROKEN_VIDEOS_PURGE_CONFIRMATION}"'),
            }, 400

        inv = scan_broken_videos_inventory(
            max_scan=max_scan,
            collect_ids_limit=limit,
        )
        video_ids = inv["ids_to_delete"]
        if not video_ids:
            return {
                "message": "No broken video rows found in scan range",
                "deletedCount": 0,
                "scanned": inv["scanned"],
                "more_batches_suggested": False,
                "confirmation_phrase": BROKEN_VIDEOS_PURGE_CONFIRMATION,
            }, 200

        videos = Video.query.filter(Video.id.in_(video_ids)).all()
        by_id = {v.id: v for v in videos}
        missing = [vid for vid in video_ids if vid not in by_id]
        if missing:
            return {"error": "Some video_ids not found", "missing_video_ids": missing}, 400

        not_broken = []
        for vid in video_ids:
            if broken_video_row_payload(by_id[vid]) is None:
                not_broken.append(vid)
        if not_broken:
            return {
                "error": "Race or stale list: some rows are no longer broken",
                "not_broken_video_ids": sorted(not_broken),
            }, 409

        ordered = [by_id[vid] for vid in video_ids]
        deleted_video_ids, deleted_dirs = _cascade_delete_videos_collect_dirs(ordered)

        cleanup_log = ActivityLog(
            type="admin_diagnostics_cleanup",
            data=json.dumps(
                {
                    "action": "broken_video_rows_purge_batch",
                    "bucket": "broken_video_row",
                    "video_ids": deleted_video_ids,
                    "batch_limit": limit,
                }
            ),
        )
        db.session.add(cleanup_log)
        db.session.commit()

        deleted_files, deleted_size = _remove_recording_dirs(deleted_dirs)
        bust_response_caches()
        bust_system_response_caches()
        more = len(deleted_video_ids) >= limit
        return {
            "message": f"Deleted {len(deleted_video_ids)} broken video rows (batch)",
            "deletedCount": len(deleted_video_ids),
            "deletedVideoIds": deleted_video_ids,
            "deletedDirs": len(deleted_dirs),
            "deletedFiles": deleted_files,
            "deletedSize": deleted_size,
            "scanned": inv["scanned"],
            "more_batches_suggested": more,
            "confirmation_phrase": BROKEN_VIDEOS_PURGE_CONFIRMATION,
        }, 200
    except ValueError as exc:
        db.session.rollback()
        return {"error": str(exc)}, 400
    except Exception as e:
        db.session.rollback()
        _log.exception("Broken video purge failed: %s", e)
        return {"error": "Failed to purge broken video rows"}, 500


def purge_no_species_video_rows(payload) -> tuple[dict, int]:
    try:
        dry_run = bool(payload.get("dry_run", True))
        limit = int(payload.get("limit") or 500)
        limit = max(1, min(limit, 5000))
        sample_limit = int(payload.get("sample_limit") or 40)
        sample_limit = max(1, min(sample_limit, 200))

        has_species = videos_with_species_exist_clause()
        base_q = Video.query.filter(~has_species).order_by(Video.id.asc())

        if dry_run:
            total = base_q.count()
            sample_ids = [v.id for v in base_q.limit(sample_limit).all()]
            return {
                "dry_run": True,
                "without_species_total": total,
                "sample_video_ids": sample_ids,
                "confirmation_phrase": NO_SPECIES_VIDEOS_PURGE_CONFIRMATION,
                "note": (
                    "Повторяйте POST с dry_run:false и confirm_text, пока deletedCount не 0. "
                    "Удаляются каталоги записей на диске."
                ),
            }, 200

        confirm_text = str((payload or {}).get("confirm_text") or "").strip()
        if confirm_text != NO_SPECIES_VIDEOS_PURGE_CONFIRMATION:
            return {
                "error": (f'Confirmation text must be "{NO_SPECIES_VIDEOS_PURGE_CONFIRMATION}"'),
            }, 400

        candidates = base_q.limit(limit).all()
        if not candidates:
            return {
                "message": "No videos without species detections",
                "deletedCount": 0,
                "more_batches_suggested": False,
                "confirmation_phrase": NO_SPECIES_VIDEOS_PURGE_CONFIRMATION,
            }, 200

        stale: list[int] = []
        for v in candidates:
            if not video_row_has_no_species(v.id):
                stale.append(v.id)
        if stale:
            return {
                "error": "Race: some videos now have species rows",
                "stale_video_ids": sorted(stale),
            }, 409

        deleted_video_ids, deleted_dirs = _cascade_delete_videos_collect_dirs(candidates)

        cleanup_log = ActivityLog(
            type="admin_diagnostics_cleanup",
            data=json.dumps(
                {
                    "action": "no_species_videos_purge_batch",
                    "bucket": "no_species_video",
                    "video_ids": deleted_video_ids,
                    "batch_limit": limit,
                }
            ),
        )
        db.session.add(cleanup_log)
        db.session.commit()

        deleted_files, deleted_size = _remove_recording_dirs(deleted_dirs)
        bust_response_caches()
        bust_system_response_caches()
        more = len(deleted_video_ids) >= limit
        return {
            "message": (f"Deleted {len(deleted_video_ids)} videos without species (batch)"),
            "deletedCount": len(deleted_video_ids),
            "deletedVideoIds": deleted_video_ids,
            "deletedDirs": len(deleted_dirs),
            "deletedFiles": deleted_files,
            "deletedSize": deleted_size,
            "more_batches_suggested": more,
            "confirmation_phrase": NO_SPECIES_VIDEOS_PURGE_CONFIRMATION,
        }, 200
    except ValueError as exc:
        db.session.rollback()
        return {"error": str(exc)}, 400
    except Exception as e:
        db.session.rollback()
        _log.exception("No-species video purge failed: %s", e)
        return {"error": "Failed to purge videos without species"}, 500


def build_birdnet_fifo_snapshot_response() -> tuple[dict, int]:
    from services.birdnet_fifo_view_service import try_build_birdnet_fifo_snapshot_from_db
    from services.system_operational_status import enrich_birdnet_fifo_response

    db_snapshot = try_build_birdnet_fifo_snapshot_from_db()
    if db_snapshot is not None:
        rel = os.path.join("diagnostics", "birdnet_fifo_snapshot.json").replace("\\", "/")
        try:
            stale_sec = int(app_config.get("processor.birdnet_fifo_snapshot_stale_sec") or 180)
        except (TypeError, ValueError):
            stale_sec = 180
        stale_sec = max(30, min(stale_sec, 86_400))
        body = {
            "snapshot_relative_path": rel,
            "snapshot_stale": False,
            "stale_threshold_sec": stale_sec,
            **db_snapshot,
        }
        return enrich_birdnet_fifo_response(body, app_config_get=app_config.get), 200

    rel = os.path.join("diagnostics", "birdnet_fifo_snapshot.json").replace("\\", "/")
    path = os.path.join(data_paths.data_dir(), "diagnostics", "birdnet_fifo_snapshot.json")
    try:
        stale_sec = int(app_config.get("processor.birdnet_fifo_snapshot_stale_sec") or 180)
    except (TypeError, ValueError):
        stale_sec = 180
    stale_sec = max(30, min(stale_sec, 86_400))
    meta: dict = {
        "snapshot_relative_path": rel,
        "file_exists": os.path.isfile(path),
    }
    if not meta["file_exists"]:
        body = {
            **meta,
            "available": False,
            "reason": "snapshot_file_missing",
            "note": (
                "Файл ещё не создан: нет процессора/MQTT, нет событий BirdNET, "
                "или отключено processor.birdnet_fifo_snapshot_enabled."
            ),
        }
        return enrich_birdnet_fifo_response(body, app_config_get=app_config.get), 200
    try:
        st = os.stat(path)
        meta["file_size_bytes"] = st.st_size
        meta["file_mtime_iso"] = datetime.fromtimestamp(st.st_mtime, tz=timezone.utc).isoformat()
        age_sec = max(0.0, time.time() - st.st_mtime)
        meta["file_age_sec"] = round(age_sec, 1)
        snapshot_stale = age_sec > float(stale_sec)
        meta["snapshot_stale"] = snapshot_stale
        meta["stale_threshold_sec"] = stale_sec
        with open(path, encoding="utf-8") as f:
            snapshot = json.load(f)
    except OSError as e:
        return {"error": f"Failed to read snapshot: {e}", **meta}, 500
    except json.JSONDecodeError as e:
        return {"error": f"Invalid snapshot JSON: {e}", **meta}, 500
    body = {
        **meta,
        "available": True,
        "snapshot": snapshot,
    }
    return enrich_birdnet_fifo_response(body, app_config_get=app_config.get), 200


def build_processor_backpressure_response() -> tuple[dict, int]:
    """Queue depths and drop counters from processor runtime snapshot (#510)."""
    body, code = build_processor_runtime_snapshot_response()
    if code != 200:
        return body, code
    snap = body.get("snapshot") if isinstance(body, dict) else None
    gauges = (snap or {}).get("gauges") if isinstance(snap, dict) else {}
    counters = (snap or {}).get("counters") if isinstance(snap, dict) else {}
    keys_g = (
        "finalize_queue_depth",
        "finalize_queue_maxsize",
        "finalize_queue_saturated",
        "classification_queue_depth",
        "classification_queue_maxsize",
        "classification_task_drops_total",
        "mqtt_events_queue_depth",
        "mqtt_outbound_queue_depth",
    )
    keys_c = (
        "recording_trigger_deferred_finalize_backpressure_total",
        "classification_task_drops_total",
    )
    return {
        "available": bool(body.get("available")),
        "generated_at": (snap or {}).get("generated_at"),
        "gauges": {k: gauges[k] for k in keys_g if k in gauges},
        "counters": {k: counters[k] for k in keys_c if k in counters},
        "snapshot_stale": body.get("file_age_sec", 0) > 120 if body.get("file_age_sec") else None,
    }, 200


def build_processor_runtime_snapshot_response() -> tuple[dict, int]:
    rel = os.path.join("diagnostics", "processor_runtime_stats.json").replace("\\", "/")
    path = os.path.join(data_paths.data_dir(), "diagnostics", "processor_runtime_stats.json")
    meta: dict = {
        "snapshot_relative_path": rel,
        "file_exists": os.path.isfile(path),
    }
    if not meta["file_exists"]:
        return {
            **meta,
            "available": False,
            "reason": "snapshot_file_missing",
            "note": "Процессор ещё не создал runtime snapshot.",
        }, 200
    try:
        st = os.stat(path)
        meta["file_size_bytes"] = st.st_size
        meta["file_mtime_iso"] = datetime.fromtimestamp(st.st_mtime, tz=timezone.utc).isoformat()
        meta["file_age_sec"] = round(max(0.0, time.time() - st.st_mtime), 1)
        with open(path, encoding="utf-8") as f:
            snapshot = json.load(f)
    except OSError as e:
        return {"error": f"Failed to read runtime snapshot: {e}", **meta}, 500
    except json.JSONDecodeError as e:
        return {"error": f"Invalid runtime snapshot JSON: {e}", **meta}, 500
    return {
        **meta,
        "available": True,
        "snapshot": snapshot,
    }, 200


def build_review_only_noise_candidates_response(limit: int) -> dict:
    rows = (
        db.session.query(VideoSpecies, Species, Video)
        .join(Species, Species.id == VideoSpecies.species_id)
        .join(Video, Video.id == VideoSpecies.video_id)
        .filter(
            VideoSpecies.source == "video",
            VideoSpecies.species_visit_id.is_(None),
            Species.name.in_(REVIEW_ONLY_NOISE_SPECIES),
        )
        .order_by(VideoSpecies.id.desc())
        .limit(limit)
        .all()
    )
    items = []
    for vs, sp, v in rows:
        br, _ = broken_video_row_reason(v.video_path)
        vst = vs.created_at
        items.append(
            {
                "detection_id": vs.id,
                "video_id": v.id,
                "species": sp.name,
                "confidence": vs.confidence,
                "detection_provider": vs.detection_provider,
                "created_at": vst.isoformat() if vst else None,
                "video_path": v.video_path,
                "video_file_issue": br,
            }
        )
    return {
        "bucket": "review_only_noise_candidate",
        "items": items,
        "note": (
            "Автоудаление истории не выполняется. Для массового снятия unknowns используйте "
            "review-queue delete при необходимости."
        ),
    }


def parse_review_only_noise_limit(args) -> int:
    limit = int(args.get("limit") or 100)
    return max(1, min(limit, 500))
