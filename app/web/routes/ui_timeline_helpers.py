"""Сборка merged timeline для /api/ui/timeline и export (#198)."""

from datetime import datetime, timezone

from sqlalchemy.orm import joinedload

from models import Species, SpeciesVisit, Video, VideoSpecies
from species_constants import GENERIC_BIRD_SPECIES
from util import ensure_utc, format_unlinked_video_for_timeline, format_visit_for_timeline


def _timeline_visits_deduped_ordered(visits_raw):
    """JOIN с VideoSpecies даёт дубликаты SpeciesVisit при нескольких роликах в одном визите."""
    seen = set()
    visits = []
    for v in visits_raw:
        if v.id in seen:
            continue
        seen.add(v.id)
        visits.append(v)
    visits.sort(
        key=lambda x: (ensure_utc(x.start_time), x.id or 0),
        reverse=True,
    )
    return visits


def _timeline_entry_sort_key(item: dict):
    s = item.get('start_time')
    if not isinstance(s, str):
        return datetime.min.replace(tzinfo=timezone.utc)
    if s.endswith('Z'):
        s = s[:-1] + '+00:00'
    try:
        parsed = datetime.fromisoformat(s)
    except ValueError:
        return datetime.min.replace(tzinfo=timezone.utc)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def build_merged_timeline_items(session, start_dt, end_dt) -> list:
    """Визиты за интервал + ролики, которые ни в один визит не попали."""
    visits_raw = (
        session.query(SpeciesVisit)
        .join(Species)
        .join(VideoSpecies)
        .join(Video)
        .options(
            joinedload(SpeciesVisit.video_species).joinedload(VideoSpecies.video),
            joinedload(SpeciesVisit.species),
        )
        .filter(
            SpeciesVisit.end_time >= start_dt,
            SpeciesVisit.start_time <= end_dt,
        )
        .order_by(SpeciesVisit.start_time.desc())
        .all()
    )
    visits = _timeline_visits_deduped_ordered(visits_raw)
    visit_payloads = [format_visit_for_timeline(v) for v in visits]
    video_ids_in_visits: set[int] = set()
    for p in visit_payloads:
        for d in p.get('detections') or []:
            vid = d.get('video_id')
            if vid is not None:
                video_ids_in_visits.add(int(vid))
    fallback_species = (
        session.query(Species).filter(Species.name == GENERIC_BIRD_SPECIES).first()
    )
    unlinked_videos = (
        session.query(Video)
        .options(
            joinedload(Video.video_species).joinedload(VideoSpecies.species),
        )
        .filter(
            Video.end_time > start_dt,
            Video.start_time < end_dt,
        )
        .order_by(Video.start_time.desc())
        .all()
    )
    unlinked_payloads = [
        format_unlinked_video_for_timeline(v, fallback_species=fallback_species)
        for v in unlinked_videos
        if v.id not in video_ids_in_visits
    ]
    merged = visit_payloads + unlinked_payloads
    merged.sort(key=_timeline_entry_sort_key, reverse=True)
    return merged
