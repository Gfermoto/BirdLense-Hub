"""
Retention policy: delete old recordings and optionally DB records (files_only mode).
Supports: mode=cascade|files_only|disabled; dataset TTL; migration TTL; batch_size; min_age_hours.
"""

import logging
import os
import shutil
from datetime import datetime, timedelta, timezone

from app_config.app_config import app_config
from models import SpeciesVisit, Video, VideoSpecies, db
from services.recording_protection import (
    protected_favorite_session_dirs,
    video_row_in_protected_session,
)
from util import recordings_dir

logger = logging.getLogger(__name__)

# Cache for last run metrics (updated after each successful run)
_last_run_metrics = {
    "retention_last_run": None,
    "retention_last_deleted_count": 0,
    "retention_last_freed_bytes": 0,
    "retention_mode": "cascade",
}


def _delete_video_row_cascade(video: Video) -> None:
    """Удалить VideoSpecies и осиротевшие SpeciesVisit, затем Video (как в delete_video API)."""
    video_id = video.id
    visit_ids = {vs.species_visit_id for vs in video.video_species if vs.species_visit_id}
    visits_to_delete = []
    for vid in visit_ids:
        other = VideoSpecies.query.filter(
            VideoSpecies.species_visit_id == vid,
            VideoSpecies.video_id != video_id,
        ).first()
        if not other:
            visits_to_delete.append(vid)
    for vs in list(video.video_species):
        db.session.delete(vs)
    for vid in visits_to_delete:
        visit = db.session.get(SpeciesVisit, vid)
        if visit:
            db.session.delete(visit)
    db.session.delete(video)


def _get_recordings_size_gb():
    """Total size of recordings dir in GB."""
    rec_dir = recordings_dir()
    if not os.path.isdir(rec_dir):
        return 0
    total = 0
    for root, _, files in os.walk(rec_dir):
        for f in files:
            try:
                total += os.path.getsize(os.path.join(root, f))
            except OSError:
                pass
    return total / (1024**3)


def _recordings_dir():
    """Return recordings directory path."""
    return recordings_dir()


def _files_only_cleanup(
    rec_dir: str, cutoff: datetime, batch_size: int, grace_hours: int, protect_favorites: bool, dry_run: bool
) -> tuple[int, int]:
    """Delete recording files older than cutoff without touching DB.
    Returns (deleted_count, freed_bytes).
    """
    protected_dirs: set[str] = protected_favorite_session_dirs(rec_dir) if protect_favorites else set()

    if not os.path.isdir(rec_dir):
        return 0, 0
    now = datetime.now(timezone.utc)
    deleted_count = 0
    freed_bytes = 0
    extensions = {".mp4", ".mkv", ".mov", ".avi", ".webm", ".ts", ".m3u8"}
    for year in sorted(os.listdir(rec_dir), reverse=True):
        year_path = os.path.join(rec_dir, year)
        if not os.path.isdir(year_path):
            continue
        for month in sorted(os.listdir(year_path), reverse=True):
            month_path = os.path.join(year_path, month)
            if not os.path.isdir(month_path):
                continue
            for day in sorted(os.listdir(month_path), reverse=True):
                day_path = os.path.join(month_path, day)
                if not os.path.isdir(day_path):
                    continue
                # prune empty dirs from leaves upward
                dir_date = datetime.strptime(f"{year}-{month}-{day}", "%Y-%m-%d")
                if dir_date.replace(tzinfo=timezone.utc) >= cutoff:
                    continue
                if (now - dir_date.replace(tzinfo=timezone.utc)).total_seconds() < grace_hours * 3600:
                    continue
                to_remove = []
                for root, _, files in os.walk(day_path):
                    for fname in files:
                        ext = os.path.splitext(fname)[1].lower()
                        if ext not in extensions:
                            continue
                        fp = os.path.join(root, fname)
                        try:
                            fsize = os.path.getsize(fp)
                            # Favorites: DB flag (whole session dir) + legacy filename heuristic
                            if protect_favorites:
                                if "favorite" in fname.lower():
                                    continue
                                try:
                                    if os.path.realpath(os.path.dirname(fp)) in protected_dirs:
                                        continue
                                except OSError:
                                    pass
                            to_remove.append(fp)
                            freed_bytes += fsize
                        except OSError:
                            pass
                if to_remove:
                    if not dry_run:
                        for fp in to_remove:
                            try:
                                os.remove(fp)
                            except OSError:
                                pass
                        # remove empty dirs
                        try:
                            os.removedirs(day_path)
                        except OSError:
                            pass
                    deleted_count += len(to_remove)
                    if deleted_count >= batch_size:
                        return deleted_count, freed_bytes
    return deleted_count, freed_bytes


def _cleanup_dataset_ttl(dataset_max_age_days: int, grace_hours: int, dry_run: bool):
    """Delete dataset files older than dataset_max_age_days based on mtime."""
    if dataset_max_age_days <= 0:
        return
    root = os.path.join(os.path.dirname(recordings_dir()), "dataset")
    if not os.path.isdir(root):
        return
    cutoff = datetime.now(timezone.utc) - timedelta(days=dataset_max_age_days, hours=grace_hours)
    for base, dirs, files in os.walk(root, topdown=False):
        for fname in files:
            if fname.lower().endswith((".jpg", ".jpeg", ".png")):
                fp = os.path.join(base, fname)
                try:
                    mtime = datetime.fromtimestamp(os.path.getmtime(fp), tz=timezone.utc)
                    if mtime >= cutoff:
                        continue
                    if not dry_run:
                        os.remove(fp)
                except OSError:
                    pass


def _cleanup_migration_ttl(migration_max_age_days: int, grace_hours: int, dry_run: bool):
    """Remove SpeciesVisit rows older than migration_max_age_days that have no live references."""
    if migration_max_age_days <= 0:
        return
    cutoff = datetime.now(timezone.utc) - timedelta(days=migration_max_age_days, hours=grace_hours)
    subq = db.session.query(VideoSpecies.species_visit_id).distinct().subquery()
    q = db.session.query(SpeciesVisit).filter(
        SpeciesVisit.start_time < cutoff,
        ~SpeciesVisit.id.in_(subq),
    )
    if dry_run:
        deleted = q.count()
        logger.info(f"Migration TTL (dry_run): would remove {deleted} stale SpeciesVisit rows")
        return
    deleted = q.delete(synchronize_session=False)
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logger.error(f"Migration TTL cleanup failed: {e}")
    if deleted:
        logger.info(f"Migration TTL: removed {deleted} stale SpeciesVisit rows")


def _fetch_metrics():
    """Return last run metrics for UI display."""
    # Populate from cached state
    return {
        "retention_last_run": _last_run_metrics.get("retention_last_run"),
        "retention_mode": _last_run_metrics.get("retention_mode"),
        "retention_last_deleted_count": _last_run_metrics.get("retention_last_deleted_count"),
        "retention_last_freed_bytes": _last_run_metrics.get("retention_last_freed_bytes"),
    }


def _retention_cfg(key: str, default=None):
    """Read retention.* via AppConfig dot-path (nested YAML)."""
    return app_config.get(f"retention.{key}", default)


def _cleanup_orphaned_visits_after_retention(*, dry_run: bool) -> int:
    try:
        from services.species_visit_maintenance_service import (
            apply_clean_orphaned_visits,
            preview_clean_orphaned_visits,
        )

        if dry_run:
            result = preview_clean_orphaned_visits(db.session)
            removed = int(result.get("orphaned") or 0)
            if removed:
                logger.info(
                    "Retention dry-run: would remove %s orphaned visit(s) after cascade",
                    removed,
                )
            return removed

        result = apply_clean_orphaned_visits(db.session)
        db.session.commit()
        removed = int(result.get("orphaned") or 0)
        if removed:
            logger.info("Retention: removed %s orphaned visit(s) after cascade", removed)
        return removed
    except Exception:
        db.session.rollback()
        logger.exception("Retention: orphan visit cleanup failed")
        return 0


def run_retention(dry_run: bool = False, mode: str = None):
    """Apply retention policies based on configured mode.
    Returns (deleted_count, deleted_size) for recordings cleanup.
    """
    mode_raw = mode if mode is not None else _retention_cfg("mode", "cascade")
    mode = str(mode_raw).strip().lower() if mode_raw else "cascade"
    if mode == "disabled":
        logger.info("Retention mode=disabled, skipping")
        return 0, 0

    grace_hours = int(_retention_cfg("min_age_hours", 1))
    batch_size = int(_retention_cfg("batch_size", 50))
    try:
        max_deletes_per_run = int(_retention_cfg("max_deletes_per_run") or 500)
    except (TypeError, ValueError):
        max_deletes_per_run = 500
    max_deletes_per_run = max(1, min(5000, max_deletes_per_run))
    protect_favorites = bool(_retention_cfg("protect_favorites", True))

    recordings_deleted = 0
    recordings_freed = 0
    deleted_video_ids = set()

    if mode == "files_only":
        # files_only: only remove files; mark Video as deleted
        rec_dir = _recordings_dir()
        cut_days = _retention_cfg("days")
        max_gb = _retention_cfg("max_gb")
        if not cut_days and not max_gb:
            return 0, 0
        if not cut_days and max_gb and float(max_gb) > 0:
            logger.warning(
                "Retention mode=files_only: max_gb is set but retention.days is empty — "
                "size-based trimming is only implemented for cascade; skipping files_only run."
            )
            return 0, 0
        cutoff = None
        if cut_days and int(cut_days) > 0:
            cutoff = datetime.now(timezone.utc) - timedelta(days=int(cut_days), hours=grace_hours)

        deleted_files, freed = _files_only_cleanup(
            rec_dir, cutoff or datetime.min, batch_size, grace_hours, protect_favorites, dry_run
        )
        recordings_deleted = deleted_files
        recordings_freed = freed

        # Soft-delete Video rows (align with cascade: skip favorites when enabled)
        if not dry_run and cutoff:
            q = Video.query.filter(Video.start_time < cutoff, Video.deleted_at.is_(None))
            if protect_favorites:
                q = q.filter(Video.favorite.is_(False))
            videos = q.all()
            if protect_favorites:
                prot_sd = protected_favorite_session_dirs(rec_dir)
                videos = [v for v in videos if not video_row_in_protected_session(rec_dir, v.video_path, prot_sd)]
            for v in videos:
                v.deleted_at = datetime.now(timezone.utc)
                # keep paths unchanged to avoid NOT NULL violation
                deleted_video_ids.add(v.id)
            try:
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                logger.error(f"Soft-delete Video rows failed: {e}")
    else:
        # cascade or full_row: original behavior
        cut_days = _retention_cfg("days")
        max_gb = _retention_cfg("max_gb")
        if not cut_days and not max_gb:
            return 0, 0
        cutoff = None
        if cut_days and int(cut_days) > 0:
            cutoff = datetime.now(timezone.utc) - timedelta(days=int(cut_days), hours=grace_hours)
        if max_gb and float(max_gb) > 0:
            rec_max = _recordings_dir()
            prot_max = protected_favorite_session_dirs(rec_max) if protect_favorites else set()
            # size-based loop (cascade mode must delete oldest first)
            while True:
                sz = _get_recordings_size_gb()
                if sz <= float(max_gb):
                    break
                q = Video.query.order_by(Video.start_time.asc())
                if protect_favorites:
                    q = q.filter(Video.favorite.is_(False))
                oldest = None
                for cand in q:
                    if protect_favorites and video_row_in_protected_session(rec_max, cand.video_path, prot_max):
                        continue
                    oldest = cand
                    break
                if not oldest:
                    break
                try:
                    app_base = os.path.dirname(os.path.dirname(_recordings_dir()))
                    dir_path = os.path.join(app_base, os.path.dirname(oldest.video_path or ""))
                    if os.path.isdir(dir_path):
                        for f in os.listdir(dir_path):
                            fp = os.path.join(dir_path, f)
                            if os.path.isfile(fp):
                                recordings_freed += os.path.getsize(fp)
                        shutil.rmtree(dir_path)
                        recordings_deleted += 1
                    _delete_video_row_cascade(oldest)
                    deleted_video_ids.add(oldest.id)
                except Exception as e:
                    logger.error(f"Retention max_gb delete failed: {e}")
                    db.session.rollback()
                    break
                if len(deleted_video_ids) % 25 == 0:
                    try:
                        db.session.commit()
                    except Exception:
                        db.session.rollback()
                        logger.exception("Retention interim commit failed during max_gb trim")
                        break
                if len(deleted_video_ids) >= max_deletes_per_run:
                    logger.info(
                        "Retention max_gb: reached max_deletes_per_run=%s (size_gb=%.2f target=%s)",
                        max_deletes_per_run,
                        sz,
                        max_gb,
                    )
                    break
            try:
                db.session.commit()
            except Exception:
                db.session.rollback()
                logger.exception("Retention commit failed after max_gb cascade deletes")

        if cutoff and mode == "cascade":
            rec_cascade = _recordings_dir()
            prot_cascade = protected_favorite_session_dirs(rec_cascade) if protect_favorites else set()
            videos = Video.query.filter(Video.start_time < cutoff)
            if protect_favorites:
                videos = videos.filter(Video.favorite.is_(False))
            videos = videos.all()
            for video in videos:
                if protect_favorites and video_row_in_protected_session(rec_cascade, video.video_path, prot_cascade):
                    continue
                try:
                    if video.video_path:
                        app_base = os.path.dirname(os.path.dirname(_recordings_dir()))
                        dir_path = os.path.join(app_base, os.path.dirname(video.video_path))
                        if os.path.isdir(dir_path):
                            for f in os.listdir(dir_path):
                                fp = os.path.join(dir_path, f)
                                if os.path.isfile(fp):
                                    recordings_freed += os.path.getsize(fp)
                            shutil.rmtree(dir_path)
                            recordings_deleted += 1
                    _delete_video_row_cascade(video)
                    deleted_video_ids.add(video.id)
                except Exception as e:
                    logger.error(f"Retention delete failed: {e}")
            try:
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                logger.error(f"Retention commit failed: {e}")

        # dataset TTL
        _cleanup_dataset_ttl(_retention_cfg("dataset_max_age_days", 0), grace_hours, dry_run)
        # migration TTL
        _cleanup_migration_ttl(_retention_cfg("migration_max_age_days", 0), grace_hours, dry_run)

        if recordings_deleted:
            logger.info(f"Retention: deleted {recordings_deleted} videos, {recordings_freed / 1024 / 1024:.1f} MB")
        if deleted_video_ids:
            logger.info(f"Retention: soft-deleted Video rows: {len(deleted_video_ids)}")

    _cleanup_orphaned_visits_after_retention(dry_run=dry_run)

    # Update cached metrics for UI
    _last_run_metrics["retention_last_run"] = datetime.now(timezone.utc).isoformat()
    _last_run_metrics["retention_last_deleted_count"] = recordings_deleted
    _last_run_metrics["retention_last_freed_bytes"] = recordings_freed
    _last_run_metrics["retention_mode"] = mode

    # metrics
    m = _fetch_metrics()
    m["retention_last_deleted_count"] = recordings_deleted
    m["retention_last_freed_bytes"] = recordings_freed
    logger.info(f"Retention metrics: {m}")
    return recordings_deleted, recordings_freed
