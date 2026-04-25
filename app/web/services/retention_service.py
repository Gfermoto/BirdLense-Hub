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
from util import recordings_dir

logger = logging.getLogger(__name__)


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


def _files_only_cleanup(rec_dir: str, cutoff: datetime, batch_size: int, grace_hours: int,
                         protect_favorites: bool, dry_run: bool) -> tuple[int, int]:
    """Delete recording files older than cutoff without touching DB.
    Returns (deleted_count, freed_bytes).
    """
    if not os.path.isdir(rec_dir):
        return 0, 0
    now = datetime.now(timezone.utc)
    deleted_count = 0
    freed_bytes = 0
    extensions = {'.mp4', '.mkv', '.mov', '.avi', '.webm', '.ts', '.m3u8'}
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
                            # favorites check: inspect content (lightweight by filename heuristics)
                            if protect_favorites and 'favorite' in fname.lower():
                                continue
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
    root = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'app', 'data', 'dataset')
    if not os.path.isdir(root):
        return
    cutoff = datetime.now(timezone.utc) - timedelta(days=dataset_max_age_days, hours=grace_hours)
    for base, dirs, files in os.walk(root, topdown=False):
        for fname in files:
            if fname.lower().endswith(('.jpg', '.jpeg', '.png')):
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
    from sqlalchemy import and_
    from datetime import timedelta as td
    cutoff = datetime.now(timezone.utc) - td(days=migration_max_age_days, hours=grace_hours)
    from models import SpeciesVisit, VideoSpecies
    visits = db.session.query(SpeciesVisit).filter(SpeciesVisit.start_time < cutoff).all()
    deleted = 0
    for sv in visits:
        has_refs = db.session.query(VideoSpecies).filter(VideoSpecies.species_visit_id == sv.id).first() is not None
        if not has_refs:
            if not dry_run:
                db.session.delete(sv)
            deleted += 1
    if not dry_run and deleted:
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            logger.error(f"Migration TTL cleanup failed: {e}")
    if deleted:
        logger.info(f"Migration TTL: removed {deleted} stale SpeciesVisit rows")


def _fetch_metrics():
    from datetime import datetime
    return {
        "retention_last_run": datetime.now(timezone.utc).isoformat(),
        "retention_mode": app_config.get("retention.mode", "cascade"),
    }


def run_retention(dry_run: bool = False, mode: str = None):
    """Apply retention policies based on configured mode.
    Returns (deleted_count, deleted_size) for recordings cleanup.
    """
    cfg = app_config.config
    mode = mode or str(cfg.get("retention.mode", "cascade")).lower()
    if mode == "disabled":
        logger.info("Retention mode=disabled, skipping")
        return 0, 0

    grace_hours = int(cfg.get("retention.min_age_hours", 1))
    batch_size = int(cfg.get("retention.batch_size", 50))
    protect_favorites = bool(cfg.get("retention.protect_favorites", True))

    recordings_deleted = 0
    recordings_freed = 0
    deleted_video_ids = set()

    if mode == "files_only":
        # files_only: only remove files; mark Video as deleted
        rec_dir = _recordings_dir()
        cut_days = cfg.get("retention.days")
        max_gb = cfg.get("retention.max_gb")
        if not cut_days and not max_gb:
            return 0, 0
        cutoff = None
        if cut_days and int(cut_days) > 0:
            cutoff = datetime.now(timezone.utc) - timedelta(days=int(cut_days))

        deleted_files, freed = _files_only_cleanup(
            rec_dir, cutoff or datetime.min, batch_size, grace_hours,
            protect_favorites, dry_run
        )
        recordings_deleted = deleted_files
        recordings_freed = freed

        # Soft-delete Video rows
        if not dry_run and cutoff:
            videos = Video.query.filter(Video.start_time < cutoff).all()
            for v in videos:
                v.deleted_at = datetime.now(timezone.utc)
                v.video_path = None
                v.spectrogram_path = None
                deleted_video_ids.add(v.id)
            try:
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                logger.error(f"Soft-delete Video rows failed: {e}")
    else:
        # cascade or full_row: original behavior
        cut_days = cfg.get("retention.days")
        max_gb = cfg.get("retention.max_gb")
        if not cut_days and not max_gb:
            return 0, 0
        cutoff = None
        if cut_days and int(cut_days) > 0:
            cutoff = datetime.now(timezone.utc) - timedelta(days=int(cut_days))
        if max_gb and float(max_gb) > 0:
            # size-based loop (cascade mode must delete oldest first)
            while True:
                sz = _get_recordings_size_gb()
                if sz <= float(max_gb):
                    break
                oldest = Video.query.order_by(Video.start_time.asc()).first()
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
                    break
                if len(deleted_video_ids) >= int(cfg.get("retention.batch_size", 50)):
                    break
            try:
                db.session.commit()
            except Exception:
                db.session.rollback()

        if cutoff and mode == "cascade":
            videos = Video.query.filter(Video.start_time < cutoff).all()
            for video in videos:
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
        _cleanup_dataset_ttl(
            cfg.get("retention.dataset_max_age_days", 0),
            grace_hours,
            dry_run
        )
        # migration TTL
        _cleanup_migration_ttl(
            cfg.get("retention.migration_max_age_days", 0),
            grace_hours,
            dry_run
        )

        if recordings_deleted:
            logger.info(f"Retention: deleted {recordings_deleted} videos, {recordings_freed / 1024 / 1024:.1f} MB")
        if deleted_video_ids:
            logger.info(f"Retention: soft-deleted Video rows: {len(deleted_video_ids)}")

    # metrics
    m = _fetch_metrics()
    m["retention_last_deleted_count"] = recordings_deleted
    m["retention_last_freed_bytes"] = recordings_freed
    logger.info(f"Retention metrics: {m}")
    return recordings_deleted, recordings_freed