"""Domain-level integrity metrics for recording, visits, review-only rows and species registry."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

from app_config.app_config import app_config
from models import Species, SpeciesUnresolvedName, Video, VideoSpecies, db
from services.species_data_quality_service import find_duplicate_name_groups
from services.species_visit_maintenance_service import (
    _collect_large_gap_visit_splits,
    _collect_orphaned_visits,
    _collect_species_sync_actions,
)
from species_constants import GENERIC_BIRD_SPECIES


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _clip_duplicate_gap_seconds() -> int:
    raw = app_config.get("processor.min_seconds_between_recordings")
    try:
        cooldown = int(float(raw or 0))
    except (TypeError, ValueError):
        cooldown = 0
    if cooldown > 0:
        return max(5, cooldown)
    try:
        visit_timeout = int(app_config.get("detection.dedup_window_seconds") or 60)
    except (TypeError, ValueError):
        visit_timeout = 60
    return max(15, min(visit_timeout, 120))


def _large_gap_seconds() -> int:
    try:
        visit_timeout = int(app_config.get("detection.dedup_window_seconds") or 60)
    except (TypeError, ValueError):
        visit_timeout = 60
    return max(300, visit_timeout * 4)


def _duplicate_clip_candidates(*, recent_hours: int = 24, limit: int = 12) -> list[dict[str, Any]]:
    cutoff = _utc_now() - timedelta(hours=max(1, int(recent_hours or 24)))
    rows = (
        db.session.query(
            VideoSpecies.video_id,
            Video.start_time,
            Video.end_time,
            Species.id,
            Species.name,
        )
        .join(Video, Video.id == VideoSpecies.video_id)
        .join(Species, Species.id == VideoSpecies.species_id)
        .filter(
            VideoSpecies.source == "video",
            VideoSpecies.species_visit_id.isnot(None),
            Video.start_time >= cutoff,
            Species.name != GENERIC_BIRD_SPECIES,
        )
        .order_by(Species.id.asc(), Video.start_time.asc(), Video.id.asc())
        .all()
    )

    deduped: dict[int, list[dict[str, Any]]] = defaultdict(list)
    seen_pairs: set[tuple[int, int]] = set()
    for video_id, start_time, end_time, species_id, species_name in rows:
        key = (int(species_id), int(video_id))
        if key in seen_pairs:
            continue
        seen_pairs.add(key)
        deduped[int(species_id)].append(
            {
                "video_id": int(video_id),
                "species_id": int(species_id),
                "species_name": species_name,
                "start_time": start_time,
                "end_time": end_time,
            }
        )

    out: list[dict[str, Any]] = []
    gap_threshold = timedelta(seconds=_clip_duplicate_gap_seconds())
    for clips in deduped.values():
        prev: dict[str, Any] | None = None
        for clip in clips:
            if prev is None:
                prev = clip
                continue
            gap = clip["start_time"] - prev["end_time"]
            if timedelta(0) <= gap <= gap_threshold:
                out.append(
                    {
                        "species_name": clip["species_name"],
                        "previous_video_id": prev["video_id"],
                        "video_id": clip["video_id"],
                        "gap_seconds": round(gap.total_seconds(), 3),
                        "previous_end_time": prev["end_time"].isoformat() if prev["end_time"] else None,
                        "start_time": clip["start_time"].isoformat() if clip["start_time"] else None,
                    }
                )
                if len(out) >= limit:
                    return out
            prev = clip
    return out


def _recent_unresolved_names(limit: int = 10) -> list[dict[str, Any]]:
    rows = (
        SpeciesUnresolvedName.query.order_by(SpeciesUnresolvedName.last_seen_at.desc())
        .limit(max(1, int(limit or 10)))
        .all()
    )
    return [
        {
            "raw_name": row.raw_name,
            "normalized_key": row.normalized_key,
            "source": row.source,
            "reason": row.reason,
            "seen_count": int(row.seen_count or 0),
            "last_seen_at": row.last_seen_at.isoformat() if row.last_seen_at else None,
        }
        for row in rows
    ]


def _recent_review_only_detections(limit: int = 10) -> list[dict[str, Any]]:
    rows = (
        db.session.query(VideoSpecies, Species, Video)
        .join(Species, Species.id == VideoSpecies.species_id)
        .join(Video, Video.id == VideoSpecies.video_id)
        .filter(
            VideoSpecies.source == "video",
            VideoSpecies.species_visit_id.is_(None),
        )
        .order_by(VideoSpecies.created_at.desc(), VideoSpecies.id.desc())
        .limit(max(1, int(limit or 10)))
        .all()
    )
    items: list[dict[str, Any]] = []
    for detection, species, video in rows:
        items.append(
            {
                "detection_id": detection.id,
                "video_id": detection.video_id,
                "species_name": species.name,
                "confidence": float(detection.confidence or 0.0),
                "detection_provider": detection.detection_provider,
                "created_at": detection.created_at.isoformat() if detection.created_at else None,
                "video_path": video.video_path,
            }
        )
    return items


def build_domain_health_payload() -> tuple[dict[str, Any], int]:
    orphaned_visits = _collect_orphaned_visits(db.session)
    species_sync_actions = _collect_species_sync_actions(db.session)
    duplicate_groups = find_duplicate_name_groups(
        db.session,
        limit_groups=500,
        skip_inactive_empty_groups=False,
    )
    large_gap_plans = _collect_large_gap_visit_splits(db.session, _large_gap_seconds())
    duplicate_clip_candidates = _duplicate_clip_candidates(limit=200)
    review_only_count = (
        db.session.query(VideoSpecies)
        .filter(
            VideoSpecies.source == "video",
            VideoSpecies.species_visit_id.is_(None),
        )
        .count()
    )

    payload = {
        "domain_contract_version": "2026-04-polish-v1",
        "thresholds": {
            "clip_duplicate_gap_seconds": _clip_duplicate_gap_seconds(),
            "visit_large_gap_seconds": _large_gap_seconds(),
            "visit_timeout_seconds": int(app_config.get("detection.dedup_window_seconds") or 60),
            "min_seconds_between_recordings": float(app_config.get("processor.min_seconds_between_recordings") or 0),
        },
        "metrics": {
            "orphaned_visits": len(orphaned_visits),
            "visit_species_mismatches": len(species_sync_actions),
            "duplicate_species_name_groups": len(duplicate_groups),
            "large_gap_visits": len(large_gap_plans),
            "review_only_video_detections": int(review_only_count or 0),
            "unresolved_species_names": SpeciesUnresolvedName.query.count(),
            "duplicate_clip_candidates_24h": len(duplicate_clip_candidates),
        },
        "samples": {
            "duplicate_clip_candidates": duplicate_clip_candidates[:12],
            "recent_unresolved_species": _recent_unresolved_names(),
            "recent_review_only_video_detections": _recent_review_only_detections(),
        },
        "contracts": {
            "review_only_detection_has_no_visit": True,
            "species_visit_is_derived_from_video_species": True,
            "duplicate_clip_candidates_are_gap_based": True,
        },
    }
    return payload, 200
