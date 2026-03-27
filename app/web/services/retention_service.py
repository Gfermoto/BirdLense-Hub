"""
Retention policy: delete old recordings and DB records.
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
    return total / (1024 ** 3)


def run_retention():
    """Delete recordings by retention.days and/or retention.max_gb. Returns (deleted_count, deleted_size)."""
    days = app_config.get("retention.days")
    max_gb = app_config.get("retention.max_gb")
    if not days and not max_gb:
        return 0, 0

    cutoff = None
    if days and days > 0:
        cutoff = datetime.now(timezone.utc) - timedelta(days=int(days))
    deleted_count = 0
    deleted_size = 0

    # retention.days: delete videos older than cutoff
    if cutoff:
        videos = Video.query.filter(Video.start_time < cutoff).all()
        for video in videos:
            try:
                if video.video_path:
                    app_base = os.path.dirname(os.path.dirname(recordings_dir()))
                    dir_path = os.path.join(app_base, os.path.dirname(video.video_path))
                    if os.path.isdir(dir_path):
                        for f in os.listdir(dir_path):
                            fp = os.path.join(dir_path, f)
                            if os.path.isfile(fp):
                                deleted_size += os.path.getsize(fp)
                        shutil.rmtree(dir_path)
                        deleted_count += 1
                _delete_video_row_cascade(video)
            except Exception as e:
                logger.error(f"Retention delete failed for {video.video_path}: {e}")
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            logger.error(f"Retention commit failed: {e}")
            return 0, 0

    # Clean empty dirs
    if cutoff:
        try:
            rec_dir = recordings_dir()
            for year in os.listdir(rec_dir):
                year_path = os.path.join(rec_dir, year)
                if not os.path.isdir(year_path):
                    continue
                for month in os.listdir(year_path):
                    month_path = os.path.join(year_path, month)
                    if not os.path.isdir(month_path):
                        continue
                    for day in os.listdir(month_path):
                        day_path = os.path.join(month_path, day)
                        if not os.path.isdir(day_path):
                            continue
                        dir_date = datetime.strptime(f"{year}-{month}-{day}", "%Y-%m-%d")
                        if dir_date.replace(tzinfo=timezone.utc) < cutoff:
                            if not os.listdir(day_path):
                                shutil.rmtree(day_path)
                    if os.path.exists(month_path) and not os.listdir(month_path):
                        os.rmdir(month_path)
                if os.path.exists(year_path) and not os.listdir(year_path):
                    os.rmdir(year_path)
        except Exception as e:
            logger.warning(f"Retention dir cleanup: {e}")

    # retention.max_gb: delete oldest until under limit
    if max_gb and max_gb > 0:
        while _get_recordings_size_gb() > max_gb:
            oldest = Video.query.order_by(Video.start_time.asc()).first()
            if not oldest:
                break
            try:
                app_base = os.path.dirname(os.path.dirname(recordings_dir()))
                dir_path = os.path.join(app_base, os.path.dirname(oldest.video_path))
                if os.path.isdir(dir_path):
                    for f in os.listdir(dir_path):
                        fp = os.path.join(dir_path, f)
                        if os.path.isfile(fp):
                            deleted_size += os.path.getsize(fp)
                    shutil.rmtree(dir_path)
                    deleted_count += 1
                _delete_video_row_cascade(oldest)
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                logger.error(f"Retention max_gb delete failed: {e}")
                break

    if deleted_count:
        logger.info(f"Retention: deleted {deleted_count} videos, {deleted_size / 1024 / 1024:.1f} MB")
    return deleted_count, deleted_size
