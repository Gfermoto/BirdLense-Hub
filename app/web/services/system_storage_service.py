"""Сканирование каталога записей, stats, nearest day, purge (#293)."""

from __future__ import annotations

import logging
import os
import shutil
from datetime import datetime, timedelta

from models import Video, db
from services.http_response_cache import bust_system_response_caches
from services.api_json_validation import validation_error
from services.retention_service import _delete_video_row_cascade
from services.storage_tree_utils import get_tree_storage_info
import util as _util

_log = logging.getLogger(__name__)


def summarize_recording_day_directory(day_path: str) -> tuple[int, int]:
    """Число файлов и суммарный размер (байты) во всех timestamp-подкаталогах дня."""
    total_size = 0
    total_files = 0
    try:
        for timestamp in os.listdir(day_path):
            timestamp_path = os.path.join(day_path, timestamp)
            if not os.path.isdir(timestamp_path):
                continue
            for file in os.listdir(timestamp_path):
                file_path = os.path.join(timestamp_path, file)
                if os.path.isfile(file_path):
                    try:
                        total_size += os.path.getsize(file_path)
                        total_files += 1
                    except OSError as e:
                        _log.error("Error getting size for %s: %s", file_path, e)
    except Exception as e:
        _log.error("Error processing day directory %s: %s", day_path, e)
    return total_files, total_size


def recording_days_iso_sorted() -> list[str]:
    """Даты YYYY-MM-DD, в которых есть хотя бы один файл в дереве recordings."""
    days: set[str] = set()
    rec_dir = _util.recordings_dir()
    if not os.path.exists(rec_dir):
        return []
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
                    file_count, _ = summarize_recording_day_directory(day_path)
                    if file_count > 0:
                        days.add(f"{year}-{month}-{day}")
    except Exception as e:
        _log.error("Error scanning recording days: %s", e)
    return sorted(days)


def build_storage_stats_list() -> list[dict]:
    """Список по дням с fileCount/totalSize; пустой при отсутствии каталога или ошибке обхода."""
    stats: list[dict] = []
    if not os.path.exists(_util.recordings_dir()):
        return stats
    try:
        rec_dir = _util.recordings_dir()
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
                    file_count, total_size = summarize_recording_day_directory(day_path)
                    if file_count > 0:
                        stats.append(
                            {
                                "date": f"{year}-{month}-{day}",
                                "fileCount": file_count,
                                "totalSize": total_size,
                            }
                        )
    except Exception as e:
        _log.error("Error scanning recordings directory: %s", e)
    return stats


def nearest_recording_day_response(raw_date: str, direction: str) -> tuple[dict, int]:
    if not raw_date:
        return {"error": "date is required"}, 400
    if direction not in ("prev", "next"):
        return {"error": 'direction must be "prev" or "next"'}, 400
    try:
        pivot = datetime.strptime(raw_date, "%Y-%m-%d").date()
    except ValueError:
        return {"error": "Invalid date format, use YYYY-MM-DD"}, 400

    day_values = recording_days_iso_sorted()
    pivot_s = pivot.isoformat()
    if direction == "prev":
        match = next(
            (day for day in reversed(day_values) if day < pivot_s),
            None,
        )
    else:
        match = next((day for day in day_values if day > pivot_s), None)
    return {
        "date": match,
        "direction": direction,
        "found": match is not None,
    }, 200


def purge_storage_from_body(data: dict) -> tuple[dict, int]:
    try:
        field_types: dict[str, list[str]] = {}
        for key in ("date", "start_date", "end_date"):
            if key not in data:
                continue
            val = data[key]
            if val is None:
                continue
            if not isinstance(val, str):
                field_types.setdefault(key, []).append("must be a string")
        if field_types:
            return validation_error("Validation failed", field_types), 400

        date_str = (data.get("date") or "").strip()
        start_date_str = (data.get("start_date") or "").strip()
        end_date_str = (data.get("end_date") or "").strip()

        range_mode = bool(start_date_str or end_date_str)
        purge_date: datetime | None = None
        range_start: datetime | None = None
        range_end: datetime | None = None

        if range_mode:
            if not start_date_str or not end_date_str:
                return validation_error(
                    "start_date and end_date are required together",
                    {
                        "start_date": ["required with end_date"],
                        "end_date": ["required with start_date"],
                    },
                ), 400
            try:
                range_start = datetime.strptime(start_date_str, "%Y-%m-%d")
            except ValueError:
                return validation_error(
                    "Invalid date format, use YYYY-MM-DD",
                    {"start_date": ["use YYYY-MM-DD"]},
                ), 400
            try:
                range_end = datetime.strptime(end_date_str, "%Y-%m-%d")
            except ValueError:
                return validation_error(
                    "Invalid date format, use YYYY-MM-DD",
                    {"end_date": ["use YYYY-MM-DD"]},
                ), 400
            if range_start > range_end:
                return validation_error(
                    "start_date must be on or before end_date",
                    {"start_date": ["must be on or before end_date"], "end_date": ["must be on or after start_date"]},
                ), 400
            max_span_days = 366 * 5
            if (range_end - range_start).days > max_span_days:
                return validation_error(
                    f"Date range too large (max {max_span_days} days)",
                    {"start_date": ["range too large"], "end_date": ["range too large"]},
                ), 400
        elif date_str:
            try:
                purge_date = datetime.strptime(date_str, "%Y-%m-%d")
            except ValueError:
                return validation_error(
                    "Invalid date format, use YYYY-MM-DD",
                    {"date": ["use YYYY-MM-DD"]},
                ), 400
        else:
            return validation_error(
                "Provide date or both start_date and end_date",
                {
                    "date": ["required unless start_date and end_date are set"],
                    "start_date": ["required with end_date if date is omitted"],
                    "end_date": ["required with start_date if date is omitted"],
                },
            ), 400

        deleted_count = 0
        deleted_size = 0
        rec_dir = _util.recordings_dir()
        app_base = os.path.dirname(os.path.dirname(rec_dir))

        if range_mode:
            assert range_start is not None and range_end is not None
            range_end_exclusive = range_end + timedelta(days=1)
            videos = (
                Video.query.filter(
                    Video.start_time >= range_start,
                    Video.start_time < range_end_exclusive,
                )
                .order_by(Video.start_time.asc())
                .all()
            )
        else:
            assert purge_date is not None
            purge_cutoff = purge_date + timedelta(days=1)
            videos = Video.query.filter(Video.start_time < purge_cutoff).order_by(Video.start_time.asc()).all()

        video_dirs_to_delete: set[str] = set()
        for video in videos:
            rel_dir = os.path.dirname(video.video_path or "")
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
                        dir_date = datetime.strptime(f"{year}-{month}-{day}", "%Y-%m-%d")
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
                    count, size = summarize_recording_day_directory(day_path)
                    deleted_count += count
                    deleted_size += size
                    shutil.rmtree(day_path)
                if os.path.isdir(month_path) and not os.listdir(month_path):
                    os.rmdir(month_path)
            if os.path.isdir(year_path) and not os.listdir(year_path):
                os.rmdir(year_path)

        bust_system_response_caches()
        return {
            "message": f"Successfully deleted {deleted_count} files",
            "deletedCount": deleted_count,
            "deletedSize": deleted_size,
        }, 200
    except Exception:
        db.session.rollback()
        _log.exception("Purge storage failed")
        return {"error": "Failed to purge storage"}, 500
