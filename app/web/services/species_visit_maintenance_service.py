"""Maintenance helpers for visit cleanup and visit time realignment."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import exists
from sqlalchemy.orm import joinedload

from models import SpeciesVisit, Video, VideoSpecies


@dataclass
class _VisitTiming:
    visit: SpeciesVisit
    min_time: datetime
    max_time: datetime


@dataclass
class _DetectionTiming:
    detection: VideoSpecies
    min_time: datetime
    max_time: datetime


@dataclass
class _VisitSplitPlan:
    visit: SpeciesVisit
    groups: list[list[_DetectionTiming]]


def _collect_orphaned_visits(session) -> list[SpeciesVisit]:
    has_detection = exists().where(
        VideoSpecies.species_visit_id == SpeciesVisit.id,
    )
    return session.query(SpeciesVisit).filter(~has_detection).all()


def _collect_species_sync_actions(session) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    rows = (
        session.query(VideoSpecies)
        .options(joinedload(VideoSpecies.species_visit))
        .filter(VideoSpecies.species_visit_id.isnot(None))
        .all()
    )
    for detection in rows:
        visit = detection.species_visit
        if not visit or detection.species_id == visit.species_id:
            continue
        if detection.manually_corrected:
            actions.append(
                {
                    "kind": "visit_species",
                    "detection_id": detection.id,
                    "visit_id": visit.id,
                    "species_id": detection.species_id,
                },
            )
        else:
            actions.append(
                {
                    "kind": "detection_species",
                    "detection_id": detection.id,
                    "visit_id": visit.id,
                    "species_id": visit.species_id,
                },
            )
    return actions


def preview_clean_orphaned_visits(session) -> dict[str, Any]:
    """Summarize orphan cleanup without mutating the DB."""
    orphaned = _collect_orphaned_visits(session)
    sync_actions = _collect_species_sync_actions(session)
    return {
        "dry_run": True,
        "orphaned": len(orphaned),
        "synced_would_update": len(sync_actions),
        "message": (f"Would remove {len(orphaned)} orphaned visits and sync {len(sync_actions)} detections"),
    }


def apply_clean_orphaned_visits(session) -> dict[str, Any]:
    """Apply orphan cleanup and species sync updates."""
    orphaned = _collect_orphaned_visits(session)
    sync_actions = _collect_species_sync_actions(session)

    for visit in orphaned:
        session.delete(visit)
    session.flush()

    synced = 0
    for action in sync_actions:
        if action["kind"] == "visit_species":
            visit = session.get(SpeciesVisit, action["visit_id"])
            if visit and visit.species_id != action["species_id"]:
                visit.species_id = action["species_id"]
                synced += 1
            continue
        detection = session.get(VideoSpecies, action["detection_id"])
        if detection and detection.species_id != action["species_id"]:
            detection.species_id = action["species_id"]
            synced += 1

    return {
        "dry_run": False,
        "orphaned": len(orphaned),
        "synced": synced,
        "message": (f"Removed {len(orphaned)} orphaned visits, synced {synced} detections"),
    }


def _detection_wall_time(
    video: Video,
    seconds_from_start: float | int | None,
) -> datetime:
    offset = float(seconds_from_start or 0.0)
    return video.start_time + timedelta(seconds=offset)


def _collect_visit_realignments(session) -> list[_VisitTiming]:
    timings: dict[int, _VisitTiming] = {}
    rows = (
        session.query(SpeciesVisit, VideoSpecies, Video)
        .join(VideoSpecies, VideoSpecies.species_visit_id == SpeciesVisit.id)
        .join(Video, Video.id == VideoSpecies.video_id)
        .all()
    )
    for visit, detection, video in rows:
        det_start = _detection_wall_time(video, detection.start_time)
        det_end = _detection_wall_time(video, detection.end_time)
        if det_end < det_start:
            det_end = det_start

        current = timings.get(visit.id)
        if current is None:
            timings[visit.id] = _VisitTiming(
                visit=visit,
                min_time=det_start,
                max_time=det_end,
            )
            continue
        if det_start < current.min_time:
            current.min_time = det_start
        if det_end > current.max_time:
            current.max_time = det_end

    changed: list[_VisitTiming] = []
    for timing in timings.values():
        if timing.visit.start_time != timing.min_time or timing.visit.end_time != timing.max_time:
            changed.append(timing)
    return changed


def _max_simultaneous_for_group(group: list[_DetectionTiming]) -> int:
    events: list[tuple[datetime, int]] = []
    for timing in group:
        events.append((timing.min_time, 1))
        events.append((timing.max_time, -1))
    events.sort(key=lambda item: (item[0], -item[1]))

    current = 0
    max_seen = 1
    for _, delta in events:
        current += delta
        if current > max_seen:
            max_seen = current
    return max_seen


def _collect_large_gap_visit_splits(
    session,
    gap_seconds: int,
) -> list[_VisitSplitPlan]:
    grouped: dict[int, tuple[SpeciesVisit, list[_DetectionTiming]]] = {}
    rows = (
        session.query(SpeciesVisit, VideoSpecies, Video)
        .join(VideoSpecies, VideoSpecies.species_visit_id == SpeciesVisit.id)
        .join(Video, Video.id == VideoSpecies.video_id)
        .all()
    )
    for visit, detection, video in rows:
        det_start = _detection_wall_time(video, detection.start_time)
        det_end = _detection_wall_time(video, detection.end_time)
        if det_end < det_start:
            det_end = det_start

        visit_data = grouped.get(visit.id)
        if visit_data is None:
            visit_data = (visit, [])
            grouped[visit.id] = visit_data

        visit_data[1].append(
            _DetectionTiming(
                detection=detection,
                min_time=det_start,
                max_time=det_end,
            ),
        )

    plans: list[_VisitSplitPlan] = []
    for visit, detections in grouped.values():
        detections.sort(key=lambda item: (item.min_time, item.max_time))
        groups: list[list[_DetectionTiming]] = []
        current_group: list[_DetectionTiming] = []
        current_end: datetime | None = None

        for timing in detections:
            if current_end is not None and timing.min_time - current_end > timedelta(seconds=gap_seconds):
                groups.append(current_group)
                current_group = []
                current_end = None
            current_group.append(timing)
            current_end = timing.max_time if current_end is None else max(current_end, timing.max_time)

        if current_group:
            groups.append(current_group)
        if len(groups) > 1:
            plans.append(_VisitSplitPlan(visit=visit, groups=groups))
    return plans


def _group_bounds(group: list[_DetectionTiming]) -> tuple[datetime, datetime]:
    starts = [timing.min_time for timing in group]
    ends = [timing.max_time for timing in group]
    return min(starts), max(ends)


def preview_realign_visit_times(session) -> dict[str, Any]:
    """Summarize visit timestamp realignment without mutating the DB."""
    pending = _collect_visit_realignments(session)
    return {
        "dry_run": True,
        "updated": len(pending),
        "message": f"Would realign {len(pending)} visits",
    }


def apply_realign_visit_times(session) -> dict[str, Any]:
    """Apply visit timestamp realignment."""
    pending = _collect_visit_realignments(session)
    for timing in pending:
        timing.visit.start_time = timing.min_time
        timing.visit.end_time = timing.max_time
    return {
        "dry_run": False,
        "updated": len(pending),
        "message": f"Realigned {len(pending)} visits",
    }


def preview_split_large_gap_visits(
    session,
    gap_seconds: int,
) -> dict[str, Any]:
    """Summarize visit splits for detections separated by large gaps."""
    plans = _collect_large_gap_visit_splits(session, gap_seconds)
    created_visits = sum(len(plan.groups) - 1 for plan in plans)
    reassigned_detections = sum(len(group) for plan in plans for group in plan.groups[1:])
    return {
        "dry_run": True,
        "affected_visits": len(plans),
        "created_visits": created_visits,
        "reassigned_detections": reassigned_detections,
        "message": (
            f"Would split {len(plans)} visits, "
            f"create {created_visits} visits, "
            f"reassign {reassigned_detections} detections"
        ),
    }


def apply_split_large_gap_visits(
    session,
    gap_seconds: int,
) -> dict[str, Any]:
    """Split visits whose detections contain gaps larger than the visit window."""
    plans = _collect_large_gap_visit_splits(session, gap_seconds)
    created_visits = 0
    reassigned_detections = 0

    for plan in plans:
        first_group = plan.groups[0]
        first_start, first_end = _group_bounds(first_group)
        plan.visit.start_time = first_start
        plan.visit.end_time = first_end
        plan.visit.max_simultaneous = _max_simultaneous_for_group(first_group)

        for group in plan.groups[1:]:
            group_start, group_end = _group_bounds(group)
            new_visit = SpeciesVisit(
                species_id=plan.visit.species_id,
                start_time=group_start,
                end_time=group_end,
                max_simultaneous=_max_simultaneous_for_group(group),
            )
            session.add(new_visit)
            session.flush()
            created_visits += 1

            for timing in group:
                timing.detection.species_visit_id = new_visit.id
                reassigned_detections += 1

    return {
        "dry_run": False,
        "affected_visits": len(plans),
        "created_visits": created_visits,
        "reassigned_detections": reassigned_detections,
        "message": (
            f"Split {len(plans)} visits, created {created_visits} visits, reassigned {reassigned_detections} detections"
        ),
    }
