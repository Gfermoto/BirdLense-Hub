"""Соседи ролика в пределах суток для GET /api/ui/videos/:id/neighbors (#293)."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import joinedload

from models import SpeciesVisit, Video, VideoSpecies
from util import ensure_utc, get_primary_video_for_visit_in_window

logger = logging.getLogger(__name__)


class VideoNeighborsParamError(ValueError):
    """Некорректные query-параметры neighbors."""


def parse_video_neighbors_request_args(args) -> tuple[str, bool, str, int | None, int]:
    """scope, cross_day, neighbor_mode, visit_id, tz_offset_minutes."""
    scope = (args.get("day_scope") or "utc").strip().lower()
    if scope not in ("utc", "local"):
        raise VideoNeighborsParamError('day_scope must be "utc" or "local"')
    cross_day = (args.get("cross_day") or "").strip().lower() in ("1", "true", "yes")
    neighbor_mode = (args.get("neighbor_mode") or "video").strip().lower()
    if neighbor_mode not in ("video", "visit_primary"):
        raise VideoNeighborsParamError(
            'neighbor_mode must be "video" or "visit_primary"',
        )
    visit_id = args.get("visit_id", type=int)
    if neighbor_mode == "visit_primary" and visit_id is None:
        raise VideoNeighborsParamError(
            "visit_id is required when neighbor_mode=visit_primary",
        )
    try:
        tz_offset_minutes = int(args.get("tz_offset_minutes", 0))
    except (TypeError, ValueError) as exc:
        raise VideoNeighborsParamError(
            "tz_offset_minutes must be an integer",
        ) from exc
    if tz_offset_minutes < -840 or tz_offset_minutes > 840:
        raise VideoNeighborsParamError(
            "tz_offset_minutes out of range [-840, 840]",
        )
    return scope, cross_day, neighbor_mode, visit_id, tz_offset_minutes


def build_video_neighbors_payload(
    session,
    video: Video,
    video_id: int,
    *,
    scope: str,
    cross_day: bool,
    neighbor_mode: str,
    visit_id: int | None,
    tz_offset_minutes: int,
) -> dict:
    st_utc = ensure_utc(video.start_time).astimezone(timezone.utc).replace(tzinfo=None)
    if scope == "local":
        local_dt = st_utc - timedelta(minutes=tz_offset_minutes)
        local_day_start = datetime(local_dt.year, local_dt.month, local_dt.day)
        local_day_end = local_day_start + timedelta(days=1)
        day_start = local_day_start + timedelta(minutes=tz_offset_minutes)
        day_end = local_day_end + timedelta(minutes=tz_offset_minutes)
        day_label = local_day_start.date().isoformat()
    else:
        day_start = datetime(st_utc.year, st_utc.month, st_utc.day)
        day_end = day_start + timedelta(days=1)
        day_label = day_start.date().isoformat()

    ids: list[int] = []
    idx = None
    if neighbor_mode == "visit_primary" and visit_id is not None:
        visit_rows = (
            session.query(SpeciesVisit)
            .options(
                joinedload(SpeciesVisit.video_species).joinedload(VideoSpecies.video),
            )
            .filter(
                SpeciesVisit.end_time >= day_start,
                SpeciesVisit.start_time < day_end,
            )
            .order_by(SpeciesVisit.start_time.asc(), SpeciesVisit.id.asc())
            .all()
        )
        ids = [
            primary.id
            for visit in visit_rows
            for primary in [
                get_primary_video_for_visit_in_window(visit, day_start, day_end),
            ]
            if primary is not None
        ]
        visit_ids = [
            visit.id
            for visit in visit_rows
            if get_primary_video_for_visit_in_window(visit, day_start, day_end) is not None
        ]
        try:
            idx = visit_ids.index(visit_id)
        except ValueError:
            idx = None
    if idx is None:
        day_rows = (
            session.query(Video)
            .filter(
                Video.end_time > day_start,
                Video.start_time < day_end,
            )
            .order_by(Video.start_time.asc(), Video.id.asc())
            .with_entities(Video.id)
            .all()
        )
        ids = [row[0] for row in day_rows]

    try:
        idx = ids.index(video_id) if idx is None else idx
    except ValueError:
        logger.warning(
            "Video %s start_time not in day list (scope=%s day %s–%s); ids=%s",
            video_id,
            scope,
            day_start,
            day_end,
            ids,
        )
        return {
            "day_scope": scope,
            "day_label": day_label,
            "timezone_offset_minutes": tz_offset_minutes if scope == "local" else 0,
            "cross_day": cross_day,
            "previous_id": None,
            "next_id": None,
            "index": 0,
            "total": len(ids),
        }

    prev_id = ids[idx - 1] if idx > 0 else None
    next_id = ids[idx + 1] if idx + 1 < len(ids) else None

    if cross_day and prev_id is None:
        prev = (
            session.query(Video)
            .filter(
                (Video.start_time < video.start_time)
                | ((Video.start_time == video.start_time) & (Video.id < video.id)),
            )
            .order_by(Video.start_time.desc(), Video.id.desc())
            .with_entities(Video.id)
            .first()
        )
        prev_id = prev[0] if prev else None
    if cross_day and next_id is None:
        nxt = (
            session.query(Video)
            .filter(
                (Video.start_time > video.start_time)
                | ((Video.start_time == video.start_time) & (Video.id > video.id)),
            )
            .order_by(Video.start_time.asc(), Video.id.asc())
            .with_entities(Video.id)
            .first()
        )
        next_id = nxt[0] if nxt else None

    return {
        "day_scope": scope,
        "day_label": day_label,
        "timezone_offset_minutes": tz_offset_minutes if scope == "local" else 0,
        "cross_day": cross_day,
        "previous_id": prev_id,
        "next_id": next_id,
        "index": idx,
        "total": len(ids),
    }
