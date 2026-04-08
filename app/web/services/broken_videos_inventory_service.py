"""Диагностика Video без читаемого файла на диске (#265)."""
from __future__ import annotations

from collections import Counter

from sqlalchemy import exists

from data_paths import full_path_for_video
from models import Video, VideoSpecies, db


def broken_video_row_reason(video_path: str | None) -> tuple[str | None, str | None]:
    """(reason_code, absolute_path). reason None — файл ок."""
    import os

    vp = (video_path or '').strip()
    if not vp:
        return 'video_path_empty', None
    full = full_path_for_video(vp)
    if not full:
        return 'video_path_unresolvable', None
    if not os.path.isfile(full):
        return 'video_file_missing', full
    try:
        if os.path.getsize(full) <= 0:
            return 'video_file_empty', full
    except OSError:
        return 'video_file_unreadable', full
    try:
        if not os.access(full, os.R_OK):
            return 'video_file_unreadable', full
        with open(full, 'rb') as f:
            f.read(1)
    except OSError:
        return 'video_file_unreadable', full
    return None, full


def broken_video_row_payload(video: Video) -> dict | None:
    reason, resolved = broken_video_row_reason(video.video_path)
    if not reason:
        return None
    st = video.start_time
    return {
        'video_id': video.id,
        'video_path': video.video_path,
        'reason': reason,
        'resolved_path': resolved,
        'start_time': st.isoformat() if st else None,
    }


def scan_broken_videos_inventory(
    *,
    max_scan: int,
    collect_ids_limit: int | None,
    sample_limit: int = 40,
):
    """Проход Video.id: счётчики, sample id, опционально список на удаление."""
    by_reason: Counter = Counter()
    total_broken = 0
    sample_ids: list[int] = []
    collect: list[int] = []
    scanned = 0
    cursor = 0
    while scanned < max_scan:
        batch = (
            Video.query.filter(Video.id > cursor)
            .order_by(Video.id.asc())
            .limit(200)
            .all()
        )
        if not batch:
            break
        for video in batch:
            scanned += 1
            if scanned > max_scan:
                break
            row = broken_video_row_payload(video)
            if not row:
                continue
            total_broken += 1
            by_reason[row['reason']] += 1
            if len(sample_ids) < sample_limit:
                sample_ids.append(video.id)
            if collect_ids_limit is not None and len(collect) < collect_ids_limit:
                collect.append(video.id)
        cursor = batch[-1].id
    return {
        'scanned': scanned,
        'broken_total': total_broken,
        'by_reason': dict(by_reason),
        'sample_video_ids': sample_ids,
        'ids_to_delete': collect,
    }


def videos_with_species_exist_clause():
    """EXISTS (SELECT 1 FROM video_species WHERE video_id = video.id)."""
    return exists().where(VideoSpecies.video_id == Video.id)


def video_row_has_no_species(video_id: int) -> bool:
    return (
        db.session.query(VideoSpecies.id)
        .filter(VideoSpecies.video_id == video_id)
        .limit(1)
        .first()
        is None
    )
