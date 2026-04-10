"""Статистика ручных правок и коррекций видов за окно (#265)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func

from models import ActivityLog, Species, Video, VideoSpecies, db

from services.activity_notify_insights_service import activity_log_payload


def species_correction_rows_since(cutoff: datetime):
    return (
        db.session.query(ActivityLog)
        .filter(
            ActivityLog.type == 'species_correction',
            ActivityLog.created_at >= cutoff,
        )
        .order_by(ActivityLog.created_at.desc())
        .all()
    )


def ml_health_snapshot(days: int) -> dict:
    now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
    cutoff = now_utc - timedelta(days=max(1, int(days or 1)))
    correction_rows = species_correction_rows_since(cutoff)
    action_counts = {
        'confirm_species': 0,
        'correct_species': 0,
        'other': 0,
    }
    top_pairs: dict[str, int] = {}
    for row in correction_rows:
        payload = activity_log_payload(row) or {}
        action = str(payload.get('action') or 'other')
        if action not in action_counts:
            action = 'other'
        action_counts[action] += 1
        if action == 'correct_species':
            pair = (
                f'{payload.get("from_species_name") or "?"} -> '
                f'{payload.get("to_species_name") or "?"}'
            )
            top_pairs[pair] = top_pairs.get(pair, 0) + 1

    total_video = (
        db.session.query(func.count(VideoSpecies.id))
        .join(Video, Video.id == VideoSpecies.video_id)
        .filter(
            Video.start_time >= cutoff,
            VideoSpecies.source == 'video',
        )
        .scalar()
        or 0
    )
    corrected_video = (
        db.session.query(func.count(VideoSpecies.id))
        .join(Video, Video.id == VideoSpecies.video_id)
        .filter(
            Video.start_time >= cutoff,
            VideoSpecies.source == 'video',
            VideoSpecies.manually_corrected == True,  # noqa: E712
        )
        .scalar()
        or 0
    )
    unknown_video = (
        db.session.query(func.count(VideoSpecies.id))
        .join(Video, Video.id == VideoSpecies.video_id)
        .join(Species, Species.id == VideoSpecies.species_id)
        .filter(
            Video.start_time >= cutoff,
            VideoSpecies.source == 'video',
            Species.name == 'Unknown',
        )
        .scalar()
        or 0
    )
    generic_video = (
        db.session.query(func.count(VideoSpecies.id))
        .join(Video, Video.id == VideoSpecies.video_id)
        .join(Species, Species.id == VideoSpecies.species_id)
        .filter(
            Video.start_time >= cutoff,
            VideoSpecies.source == 'video',
            Species.name.in_(['Bird', 'Squirrel', 'Rodent']),
        )
        .scalar()
        or 0
    )

    def _rate(part: int, whole: int) -> float:
        if not whole:
            return 0.0
        return round(float(part) / float(whole), 4)

    return {
        'window_days': int(days),
        'video_detections': int(total_video),
        'manually_corrected_video_detections': int(corrected_video),
        'corrections_logged': int(len(correction_rows)),
        'confirm_actions': int(action_counts['confirm_species']),
        'species_change_actions': int(action_counts['correct_species']),
        'correction_rate': _rate(action_counts['correct_species'], total_video),
        'manual_annotation_rate': _rate(corrected_video, total_video),
        'unknown_rate': _rate(unknown_video, total_video),
        'generic_rate': _rate(generic_video, total_video),
        'top_species_changes': [
            {'pair': pair, 'count': count}
            for pair, count in sorted(
                top_pairs.items(),
                key=lambda item: (-item[1], item[0]),
            )[:5]
        ],
    }
