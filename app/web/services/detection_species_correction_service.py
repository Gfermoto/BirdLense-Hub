"""Confirm и PATCH вида детекции (VideoSpecies), датасет-кропы (#293)."""

from __future__ import annotations

import logging
import threading
from datetime import timedelta

from app_config.app_config import app_config
from models import Species, VideoSpecies, db
from services.corrections_activity_service import (
    normalize_apply_scope,
    normalize_correction_source,
    write_correction_activity,
)
from services.dataset_export_service import (
    extract_and_save_crop_for_detection,
    move_crop_on_species_correction,
)
from services.http_response_cache import bust_response_caches
from services.visit_processor import VisitProcessor
from util import ensure_utc

_log = logging.getLogger(__name__)

_INLINE_DATASET_CROP_LIMIT = 5


def run_confirm_detection(
    session,
    detection_id: int,
    payload: dict,
) -> tuple[dict | None, dict | None]:
    """(error_dict, success_dict)."""
    source = normalize_correction_source(payload.get("source"))
    apply_scope = normalize_apply_scope(
        payload.get("apply_scope"),
        default="legacy_fanout",
    )
    reason = (payload.get("reason") or "").strip() or None

    vs = session.get(VideoSpecies, detection_id)
    if not vs:
        return {"error": "Detection not found"}, None

    if apply_scope == "single_track":
        to_confirm = [vs]
    else:
        to_confirm = list(vs.species_visit.video_species) if vs.species_visit else [vs]
    for v in to_confirm:
        v.manually_corrected = True
    session.commit()
    bust_response_caches()
    write_correction_activity(
        session,
        action="confirm_species",
        source=source,
        detection_id=detection_id,
        from_species_name=vs.species.name,
        to_species_name=vs.species.name,
        updated_count=len(to_confirm),
        apply_scope=apply_scope,
        reason=reason,
        video_id=vs.video_id,
        track_id=vs.track_id,
        species_visit_id=vs.species_visit_id,
        from_species_id=vs.species_id,
        to_species_id=vs.species_id,
    )

    return None, {
        "message": "Confirmed",
        "updated_count": len(to_confirm),
        "apply_scope": apply_scope,
    }


def _run_dataset_crop_followup(jobs, *, app_obj):
    with app_obj.app_context():
        for det_id, vid, tid, old_name, new_name in jobs:
            try:
                vrow = db.session.get(VideoSpecies, det_id)
                if not vrow or vrow.source != "video":
                    continue
                moved = move_crop_on_species_correction(
                    video_id=vid,
                    track_id=tid,
                    old_species_name=old_name,
                    new_species_name=new_name,
                )
                if not moved:
                    extract_and_save_crop_for_detection(vrow, new_name)
            except Exception:
                _log.exception(
                    "dataset crop follow-up failed (detection_id=%s video_id=%s)",
                    det_id,
                    vid,
                )


def apply_detection_species_patch(
    session,
    app_logger,
    detection_id: int,
    data: dict,
    *,
    app_obj_for_thread,
) -> tuple[dict | None, dict | None]:
    """(error_dict, success_dict)."""
    source = normalize_correction_source(data.get("source"))
    raw_scope = data.get("apply_scope")
    if raw_scope is None or (isinstance(raw_scope, str) and not str(raw_scope).strip()):
        apply_scope = "legacy_fanout" if source == "video" else "single_track"
    else:
        apply_scope = normalize_apply_scope(raw_scope, default="single_track")
    reason = (data.get("reason") or "").strip() or None
    species_id = data.get("species_id")
    if species_id is None:
        return {"error": "species_id is required"}, None
    try:
        species_id = int(species_id)
    except (TypeError, ValueError):
        return {"error": "species_id must be an integer"}, None

    vs = session.get(VideoSpecies, detection_id)
    if not vs:
        return {"error": "Detection not found"}, None

    species = session.get(Species, species_id)
    if not species:
        return {"error": "Species not found"}, None

    old_visit = vs.species_visit
    old_species_id = vs.species_id
    old_species_name = vs.species.name

    if vs.species_id == species_id:
        return None, {"message": "Species unchanged"}

    if apply_scope == "single_track":
        to_update = [vs]
    elif apply_scope == "whole_visit" and old_visit:
        to_update = list(old_visit.video_species)
    else:
        to_update_set = set()
        for v in vs.video.video_species:
            if v.species_id == old_species_id:
                to_update_set.add(v)
        if old_visit:
            for v in old_visit.video_species:
                to_update_set.add(v)
        to_update = list(to_update_set)
    old_visits = {v.species_visit for v in to_update if v.species_visit}

    visit_timeout = int(app_config.get("detection.dedup_window_seconds") or 60)
    vp = VisitProcessor(db, app_logger, visit_timeout=visit_timeout)
    video_start = ensure_utc(vs.video.start_time)
    detection_time = video_start + timedelta(seconds=vs.start_time)
    new_visit, _ = vp._get_or_create_visit(species, detection_time)

    for v in to_update:
        v.species_id = species_id
        v.species_visit_id = new_visit.id
        v.species_visit = new_visit
        v.manually_corrected = True
        v_start = ensure_utc(v.video.start_time) + timedelta(seconds=v.start_time)
        v_end = ensure_utc(v.video.start_time) + timedelta(seconds=v.end_time)
        new_visit.end_time = max(new_visit.end_time, v_end)
        new_visit.start_time = min(new_visit.start_time, v_start)

    session.flush()

    for ov in old_visits:
        if ov:
            remaining = [x for x in ov.video_species if x not in to_update]
            if not remaining:
                session.delete(ov)

    new_video_detections = [v for v in new_visit.video_species if v.source == "video"]
    if new_video_detections:
        vp._update_simultaneous_count(new_visit, new_video_detections)

    log_video_id = vs.video_id
    log_track_id = vs.track_id
    log_species_visit_id = vs.species_visit_id

    session.commit()
    bust_response_caches()

    video_crop_jobs = [
        (v.id, v.video_id, v.track_id, old_species_name, species.name) for v in to_update if v.source == "video"
    ]
    if len(video_crop_jobs) <= _INLINE_DATASET_CROP_LIMIT:
        for v in to_update:
            if v.source == "video":
                moved = move_crop_on_species_correction(
                    video_id=v.video_id,
                    track_id=v.track_id,
                    old_species_name=old_species_name,
                    new_species_name=species.name,
                )
                if not moved:
                    extract_and_save_crop_for_detection(v, species.name)
    elif video_crop_jobs:
        threading.Thread(
            target=_run_dataset_crop_followup,
            args=(video_crop_jobs,),
            kwargs={"app_obj": app_obj_for_thread},
            daemon=True,
        ).start()

    updated_count = len(to_update)
    write_correction_activity(
        session,
        action="correct_species",
        source=source,
        detection_id=detection_id,
        from_species_name=old_species_name,
        to_species_name=species.name,
        updated_count=updated_count,
        apply_scope=apply_scope,
        reason=reason,
        video_id=log_video_id,
        track_id=log_track_id,
        species_visit_id=log_species_visit_id,
        from_species_id=old_species_id,
        to_species_id=species.id,
    )
    return None, {
        "message": "Species updated" + (f" ({updated_count} videos)" if updated_count > 1 else ""),
        "species_id": species_id,
        "updated_count": updated_count,
        "apply_scope": apply_scope,
    }
