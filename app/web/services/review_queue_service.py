"""Очередь ручной проверки низкоуверенных / generic Bird детекций."""

from __future__ import annotations

from datetime import timedelta, timezone

from sqlalchemy import or_
from sqlalchemy.orm import joinedload

from app_config.app_config import app_config
from models import Species, Video, VideoSpecies
from species_constants import GENERIC_BIRD_SPECIES
from util import ensure_utc, observer_local_range, parse_utc_timestamp

from routes.ui_route_constants import UNKNOWNS_LIMIT_MAX


def fetch_review_queue_items(
    session,
    *,
    date_param: str | None = None,
    time_of_day: str = "all",
    hour: int | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
    limit: int = 100,
) -> list[dict]:
    """Low-confidence review queue with explicit review-state fields."""
    limit = min(max(int(limit or 100), 1), UNKNOWNS_LIMIT_MAX)
    if date_param:
        try:
            start_dt, end_dt = observer_local_range(
                date_param,
                time_of_day=time_of_day,
                hour=hour,
            )
        except ValueError as exc:
            raise ValueError("Invalid local date range parameters") from exc
    else:
        if not start_time or not end_time:
            raise ValueError("Both start_time and end_time are required")
        try:
            start_dt = parse_utc_timestamp(start_time)
            end_dt = parse_utc_timestamp(end_time)
        except ValueError as exc:
            raise ValueError("Invalid datetime format") from exc

    if end_dt - start_dt > timedelta(days=1):
        raise ValueError("Interval must not exceed 1 day")

    threshold = float(app_config.get("ui.unknown_confidence_threshold") or 0.5)
    threshold = max(0.0, min(1.0, threshold))

    rows = (
        session.query(VideoSpecies)
        .join(Video)
        .join(Species)
        .options(
            joinedload(VideoSpecies.video),
            joinedload(VideoSpecies.species),
        )
        .filter(
            Video.end_time >= start_dt,
            Video.start_time <= end_dt,
            VideoSpecies.manually_corrected.is_(False),
            or_(
                VideoSpecies.confidence < threshold,
                VideoSpecies.classifier_needs_review.is_(True),
                Species.name == GENERIC_BIRD_SPECIES,
            ),
        )
        .order_by(VideoSpecies.created_at.desc())
        .limit(limit * 3)
        .all()
    )

    result = []
    for vs in rows:
        frames = (vs.frames or "").strip() if getattr(vs, "frames", None) else ""
        if (
            vs.detection_provider == "legacy"
            and vs.species.name == "Unknown"
            and float(vs.confidence or 0) <= 0
            and vs.source == "video"
            and not vs.manually_corrected
            and vs.track_id is None
            and not frames
            and float(vs.start_time or 0) == 0
            and float(vs.end_time or 0) == 30
        ):
            continue
        video_start = ensure_utc(vs.video.start_time)
        det_time = video_start + timedelta(seconds=vs.start_time)
        if vs.review_reason:
            review_reason = vs.review_reason
        elif bool(vs.classifier_needs_review):
            review_reason = "classifier_uncertainty"
        elif vs.species.name == GENERIC_BIRD_SPECIES:
            review_reason = "generic_bird"
        else:
            review_reason = "low_confidence"
        result.append(
            {
                "id": vs.id,
                "video_id": vs.video_id,
                "species_id": vs.species_id,
                "species_name": vs.species.name,
                "confidence": round(vs.confidence, 4),
                "start_time": det_time.astimezone(timezone.utc).isoformat(),
                "end_time": (video_start + timedelta(seconds=vs.end_time)).astimezone(timezone.utc).isoformat(),
                "source": vs.source,
                "detection_provider": vs.detection_provider,
                "image_url": vs.species.image_url,
                "review_state": "pending",
                "review_reason": review_reason,
                "review_source": "unknowns",
                "classifier_entropy": vs.classifier_entropy,
                "classifier_top1_top2_margin": vs.classifier_top1_top2_margin,
                "classifier_needs_review": bool(vs.classifier_needs_review),
            }
        )
        if len(result) >= limit:
            break

    return result
