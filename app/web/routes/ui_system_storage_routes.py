"""Хранилище записей: stats, nearest day, purge (#265)."""
from __future__ import annotations

import os
import shutil
from datetime import datetime, timedelta, timezone

from flask import request

from models import Video, db
from services.cache import cache_get, cache_set
from services.http_response_cache import bust_system_response_caches
from services.retention_service import _delete_video_row_cascade
from services.storage_tree_utils import get_tree_storage_info
from services.system_metrics_constants import _CACHE_STORAGE_STATS_SEC
from util import recordings_dir, settings_check_access


def register_ui_system_storage_routes(app):
    """Маршруты ``/api/ui/storage/*``."""
    def get_day_storage_info(day_path):
        """Get total size and file count for a day directory including all timestamp subdirs"""
        total_size = 0
        total_files = 0
        try:
            # Iterate through timestamp directories
            for timestamp in os.listdir(day_path):
                timestamp_path = os.path.join(day_path, timestamp)
                if not os.path.isdir(timestamp_path):
                    continue

                # Count all files in timestamp directory
                for file in os.listdir(timestamp_path):
                    file_path = os.path.join(timestamp_path, file)
                    if os.path.isfile(file_path):
                        try:
                            total_size += os.path.getsize(file_path)
                            total_files += 1
                        except OSError as e:
                            app.logger.error(
                                f"Error getting size for {file_path}: {e}")

        except Exception as e:
            app.logger.error(f"Error processing day directory {day_path}: {e}")

        return total_files, total_size

    def _recording_days_with_files():
        days = set()
        rec_dir = recordings_dir()
        if not os.path.exists(rec_dir):
            return days
        try:
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
                        file_count, _ = get_day_storage_info(day_path)
                        if file_count > 0:
                            days.add(f'{year}-{month}-{day}')
        except Exception as e:
            app.logger.error(f'Error scanning recording days: {e}')
        return days

    @app.route('/api/ui/storage/stats', methods=['GET'])
    def get_storage_stats():
        sck = 'storage_stats:v1'
        hit, sc = cache_get(sck)
        if hit:
            return sc, 200
        if not os.path.exists(recordings_dir()):
            cache_set(sck, [], 30)
            return [], 200

        stats = []
        # Walk through year/month/day structure
        try:
            rec_dir = recordings_dir()
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

                        # Get storage info for this day (including all timestamp subdirs)
                        file_count, total_size = get_day_storage_info(day_path)

                        if file_count > 0:  # Only include days with files
                            stats.append({
                                'date': f"{year}-{month}-{day}",
                                'fileCount': file_count,
                                'totalSize': total_size
                            })

        except Exception as e:
            app.logger.error(f"Error scanning recordings directory: {e}")

        cache_set(sck, stats, _CACHE_STORAGE_STATS_SEC)
        return stats, 200

    @app.route('/api/ui/storage/nearest-recording-day', methods=['GET'])
    def get_nearest_recording_day():
        raw_date = (request.args.get('date') or '').strip()
        direction = (request.args.get('direction') or 'next').strip().lower()
        if not raw_date:
            return {'error': 'date is required'}, 400
        if direction not in ('prev', 'next'):
            return {'error': 'direction must be "prev" or "next"'}, 400
        try:
            pivot = datetime.strptime(raw_date, '%Y-%m-%d').date()
        except ValueError:
            return {'error': 'Invalid date format, use YYYY-MM-DD'}, 400

        day_values = sorted(_recording_days_with_files())
        if direction == 'prev':
            match = next((day for day in reversed(day_values) if day < pivot.isoformat()), None)
        else:
            match = next((day for day in day_values if day > pivot.isoformat()), None)
        return {
            'date': match,
            'direction': direction,
            'found': match is not None,
        }, 200

    @app.route('/api/ui/storage/purge', methods=['POST'])
    def purge_storage():
        if not settings_check_access():
            return {'error': 'Password required'}, 403
        try:
            data = request.json or {}
            date_str = (data.get('date') or '').strip()
            start_date_str = (data.get('start_date') or '').strip()
            end_date_str = (data.get('end_date') or '').strip()

            range_mode = bool(start_date_str or end_date_str)
            purge_date: datetime | None = None
            range_start: datetime | None = None
            range_end: datetime | None = None

            if range_mode:
                if not start_date_str or not end_date_str:
                    return {'error': 'start_date and end_date are required together'}, 400
                try:
                    range_start = datetime.strptime(start_date_str, '%Y-%m-%d')
                    range_end = datetime.strptime(end_date_str, '%Y-%m-%d')
                except ValueError:
                    return {'error': 'Invalid date format, use YYYY-MM-DD'}, 400
                if range_start > range_end:
                    return {'error': 'start_date must be on or before end_date'}, 400
                max_span_days = 366 * 5
                if (range_end - range_start).days > max_span_days:
                    return {'error': f'Date range too large (max {max_span_days} days)'}, 400
            elif date_str:
                try:
                    purge_date = datetime.strptime(date_str, '%Y-%m-%d')
                except ValueError:
                    return {'error': 'Invalid date format, use YYYY-MM-DD'}, 400
            else:
                return {'error': 'Provide date or both start_date and end_date'}, 400

            deleted_count = 0
            deleted_size = 0
            rec_dir = recordings_dir()
            app_base = os.path.dirname(os.path.dirname(rec_dir))

            if range_mode:
                assert range_start is not None and range_end is not None
                range_end_exclusive = range_end + timedelta(days=1)
                videos = (
                    Video.query
                    .filter(
                        Video.start_time >= range_start,
                        Video.start_time < range_end_exclusive,
                    )
                    .order_by(Video.start_time.asc())
                    .all()
                )
            else:
                assert purge_date is not None
                purge_cutoff = purge_date + timedelta(days=1)
                videos = (
                    Video.query
                    .filter(Video.start_time < purge_cutoff)
                    .order_by(Video.start_time.asc())
                    .all()
                )

            video_dirs_to_delete = set()
            for video in videos:
                rel_dir = os.path.dirname(video.video_path or '')
                if rel_dir:
                    video_dirs_to_delete.add(os.path.join(app_base, rel_dir))
                _delete_video_row_cascade(video)
            db.session.commit()

            for dir_path in sorted(video_dirs_to_delete):
                if not os.path.isdir(dir_path):
                    continue
                count, size = get_tree_storage_info(dir_path)
                deleted_count += count
                deleted_size += size
                shutil.rmtree(dir_path)

            # Walk the recordings tree to remove stray day directories that no longer have DB rows.
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

                        try:
                            dir_date = datetime.strptime(
                                f"{year}-{month}-{day}", '%Y-%m-%d')
                        except ValueError:
                            continue

                        if range_mode:
                            assert range_start is not None and range_end is not None
                            if dir_date < range_start or dir_date > range_end:
                                continue
                        else:
                            assert purge_date is not None
                            if dir_date > purge_date:
                                continue

                        count, size = get_day_storage_info(day_path)
                        deleted_count += count
                        deleted_size += size
                        shutil.rmtree(day_path)

                    if os.path.isdir(month_path) and not os.listdir(month_path):
                        os.rmdir(month_path)

                if os.path.isdir(year_path) and not os.listdir(year_path):
                    os.rmdir(year_path)

            bust_system_response_caches()
            return {
                'message': f'Successfully deleted {deleted_count} files',
                'deletedCount': deleted_count,
                'deletedSize': deleted_size
            }, 200

        except Exception as e:
            db.session.rollback()
            app.logger.exception('Purge storage failed')
            return {'error': 'Failed to purge storage'}, 500
