"""Сборка merged timeline для /api/ui/timeline и export (#198)."""

from datetime import datetime, timezone

from sqlalchemy.orm import joinedload

from models import Species, SpeciesVisit, Video, VideoSpecies
from species_constants import GENERIC_BIRD_SPECIES
from util import (
    ensure_utc,
    format_unlinked_video_for_timeline,
    format_visit_for_timeline,
)


def _visit_has_favorite_active_video(visit) -> bool:
    """Есть ли у визита связанный ролик с favorite и без soft-delete."""
    for vs in visit.video_species or []:
        vid = getattr(vs, "video", None)
        if (
            vid is not None
            and bool(getattr(vid, "favorite", False))
            and getattr(vid, "deleted_at", None) is None
        ):
            return True
    return False


def _timeline_visits_deduped_ordered(visits_raw):
    """JOIN с VideoSpecies даёт дубликаты SpeciesVisit при множестве роликов."""
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
    s = item.get("start_time")
    if not isinstance(s, str):
        return datetime.min.replace(tzinfo=timezone.utc)
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(s)
    except ValueError:
        return datetime.min.replace(tzinfo=timezone.utc)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _timeline_item_best_confidence(item: dict) -> float:
    detections = item.get("detections") or []
    if not isinstance(detections, list) or not detections:
        return 0.0
    best = 0.0
    for detection in detections:
        if not isinstance(detection, dict):
            continue
        try:
            best = max(best, float(detection.get("confidence") or 0.0))
        except (TypeError, ValueError):
            continue
    return best


def _timeline_item_duration_seconds(item: dict) -> float:
    for key in ("video_duration_seconds", "total_recording_seconds"):
        value = item.get(key)
        if isinstance(value, (int, float)) and value > 0:
            return float(value)
    return 0.0


def _timeline_item_matches_source(item: dict, source_filter: str) -> bool:
    detections = item.get("detections") or []
    if source_filter == "all":
        return True
    if not isinstance(detections, list) or not detections:
        return False
    sources = {
        str(d.get("source") or "").strip().lower()
        for d in detections
        if isinstance(d, dict)
    }
    sources.discard("")
    if not sources:
        return False
    if source_filter == "video_only":
        return sources == {"video"}
    if source_filter == "audio_only":
        return sources == {"audio"}
    if source_filter == "mixed":
        return "video" in sources and "audio" in sources
    return True


def build_merged_timeline_items(
    session,
    start_dt,
    end_dt,
    favorite_only: bool = False,
    *,
    min_confidence: float | None = None,
    min_duration_sec: int | None = None,
    detection_source: str = "all",
    limit: int | None = None,
    offset: int = 0,
) -> list | dict:
    """Визиты за интервал + ролики, которые ни в один визит не попали.

    favorite_only: только визиты с избранным роликом и «осиротевшие»
    ролики с favorite=true.
    """
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
    if favorite_only:
        visits = [v for v in visits if _visit_has_favorite_active_video(v)]
    visit_payloads = [format_visit_for_timeline(v) for v in visits]
    video_ids_in_visits: set[int] = set()
    for p in visit_payloads:
        for d in p.get("detections") or []:
            vid = d.get("video_id")
            if vid is not None:
                video_ids_in_visits.add(int(vid))
    fallback_species = (
        session.query(Species).filter(Species.name == GENERIC_BIRD_SPECIES).first()
    )
    uq = (
        session.query(Video)
        .options(
            joinedload(Video.video_species).joinedload(VideoSpecies.species),
        )
        .filter(
            Video.end_time > start_dt,
            Video.start_time < end_dt,
            Video.deleted_at.is_(None),
        )
    )
    if favorite_only:
        uq = uq.filter(Video.favorite.is_(True))
    unlinked_videos = uq.order_by(Video.start_time.desc()).all()
    unlinked_payloads = [
        format_unlinked_video_for_timeline(v, fallback_species=fallback_species)
        for v in unlinked_videos
        if v.id not in video_ids_in_visits
    ]
    merged = visit_payloads + unlinked_payloads
    merged.sort(key=_timeline_entry_sort_key, reverse=True)
    if min_confidence is not None:
        merged = [
            item
            for item in merged
            if _timeline_item_best_confidence(item) >= float(min_confidence)
        ]
    if min_duration_sec is not None:
        merged = [
            item
            for item in merged
            if _timeline_item_duration_seconds(item) >= int(min_duration_sec)
        ]
    if detection_source != "all":
        merged = [
            item
            for item in merged
            if _timeline_item_matches_source(item, detection_source)
        ]
    total = len(merged)
    if limit is not None:
        off = max(0, int(offset or 0))
        lim = max(1, min(int(limit), 500))
        page = merged[off:off + lim]
        return {
            "items": page,
            "total": total,
            "limit": lim,
            "offset": off,
            "has_more": off + lim < total,
        }
    return merged
