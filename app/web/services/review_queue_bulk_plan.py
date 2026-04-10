"""План bulk-delete unknowns из review queue (#265)."""
from __future__ import annotations

import os
from datetime import timezone

import util as util_mod
from models import Video

from routes.ui_overview_timeline_routes import fetch_review_queue_items


def _parse_unknown_ids(payload) -> list[int]:
    raw = (payload or {}).get('unknown_ids')
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ValueError('unknown_ids must be an array of integers')
    out: list[int] = []
    for x in raw:
        try:
            v = int(x)
        except (TypeError, ValueError):
            continue
        if v > 0:
            out.append(v)
    return sorted(set(out))


def resolve_review_queue_bulk_plan(session, payload) -> dict:
    """Превью и метаданные для bulk delete (confirm ``permanent_full``)."""
    date = str((payload or {}).get('date') or '').strip()
    if not date:
        raise ValueError('date is required')
    tod_raw = (payload or {}).get('time_of_day') or 'all'
    time_of_day = str(tod_raw).strip().lower()
    hour_raw = (payload or {}).get('hour')
    hour = None
    if hour_raw not in (None, ''):
        hour = int(hour_raw)
        if hour < 0 or hour > 23:
            raise ValueError('hour must be between 0 and 23')
    unknown_ids = _parse_unknown_ids(payload)
    if not unknown_ids:
        raise ValueError('unknown_ids is required')

    queue_items = fetch_review_queue_items(
        session,
        date_param=date,
        time_of_day=time_of_day,
        hour=hour,
        limit=500,
    )
    queue_by_id = {item['id']: item for item in queue_items}
    missing_unknown_ids = [
        uid for uid in unknown_ids if uid not in queue_by_id
    ]
    if missing_unknown_ids:
        raise ValueError(
            'Selected review items are not present in the current review queue: '
            + ', '.join(str(uid) for uid in missing_unknown_ids)
        )
    selected_items = [queue_by_id[uid] for uid in unknown_ids]
    by_video: dict[int, dict] = {}
    for item in selected_items:
        bucket = by_video.setdefault(item['video_id'], {
            'video_id': item['video_id'],
            'unknown_ids': [],
            'species_names': set(),
            'review_reasons': set(),
        })
        bucket['unknown_ids'].append(item['id'])
        bucket['species_names'].add(item.get('species_name'))
        bucket['review_reasons'].add(item.get('review_reason'))

    video_ids = sorted(by_video)
    videos = session.query(Video).filter(Video.id.in_(video_ids)).all()
    videos_by_id = {video.id: video for video in videos}

    preview_videos = []
    missing_video_ids = []
    for video_id in video_ids:
        video = videos_by_id.get(video_id)
        bucket = by_video[video_id]
        if not video:
            missing_video_ids.append(video_id)
            continue
        vp = video.video_path
        full_path = util_mod.full_path_for_video(vp) if vp else None
        preview_videos.append({
            'video_id': video.id,
            'video_path': video.video_path,
            'start_time': (
                video.start_time.astimezone(timezone.utc).isoformat()
                if video.start_time else None
            ),
            'end_time': (
                video.end_time.astimezone(timezone.utc).isoformat()
                if video.end_time else None
            ),
            'has_video_path': bool(video.video_path),
            'file_exists': bool(full_path and os.path.isfile(full_path)),
            'recording_dir': os.path.dirname(vp) if vp else None,
            'unknown_count': len(bucket['unknown_ids']),
            'unknown_ids': sorted(bucket['unknown_ids']),
            'species_names': sorted(
                n for n in bucket['species_names'] if n
            ),
            'review_reasons': sorted(
                r for r in bucket['review_reasons'] if r
            ),
        })

    return {
        'date': date,
        'time_of_day': time_of_day,
        'hour': hour,
        'confirmation_phrase': 'permanent_full',
        'unknown_ids': unknown_ids,
        'unknown_count': len(selected_items),
        'video_ids': video_ids,
        'video_count': len(preview_videos),
        'missing_video_ids': missing_video_ids,
        'videos_by_id': videos_by_id,
        'preview_videos': preview_videos,
    }
