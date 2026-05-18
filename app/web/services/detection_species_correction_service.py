"""Confirm и PATCH вида детекции (VideoSpecies), датасет-кропы (#293)."""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone

from app_config.app_config import app_config
from sqlalchemy import text

from models import ActiveLearningCase, Species, VideoSpecies, db
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
from services.feedback_loop_service import (
    delete_dataset_crops_for_track,
    record_feedback_event,
)
from services.visit_processor import VisitProcessor
from util import ensure_utc

_log = logging.getLogger(__name__)

_INLINE_DATASET_CROP_LIMIT = 5

_SEMANTIC_REVIEW_REASON = "semantic_review_required"
_OPEN_AL_STATUSES = ("pending", "semantic_review_required")


def _resolve_review_queue_on_confirm(session, detections: list[VideoSpecies]) -> None:
    """Clear expert/unknowns review flags so confirmed items leave queue=expert."""
    if not detections:
        return
    now = datetime.now(timezone.utc)
    vs_ids: list[int] = []
    for vs in detections:
        vs.classifier_needs_review = False
        if vs.review_reason in {
            _SEMANTIC_REVIEW_REASON,
            "classifier_uncertainty",
            "generic_bird",
            "low_confidence",
            "bbox_rejected",
        }:
            vs.review_reason = None
        vs_ids.append(int(vs.id))
    if not vs_ids:
        return
    session.query(ActiveLearningCase).filter(
        ActiveLearningCase.video_species_id.in_(vs_ids),
        ActiveLearningCase.status.in_(_OPEN_AL_STATUSES),
    ).update(
        {"status": "approved", "updated_at": now},
        synchronize_session=False,
    )


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
    _resolve_review_queue_on_confirm(session, to_confirm)
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
                # Фоновый best-effort: одна задача не должна рвать весь список.
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
    new_visit, _ = vp.get_or_create_visit(species, detection_time)

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
        vp.update_simultaneous_count(new_visit, new_video_detections)

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
    try:
        # #397 MVP: persist relabel/background-delete feedback signal from operator action.
        record_feedback_event(
            session,
            video_species_id=detection_id,
            video_id=log_video_id,
            track_id=log_track_id,
            from_species_id=old_species_id,
            to_species_id=species.id,
            from_species_name=old_species_name,
            to_species_name=species.name,
            trigger_source=source,
            apply_scope=apply_scope,
            reason=reason,
            detection_provider=getattr(vs, "detection_provider", None),
            confidence=getattr(vs, "confidence", None),
            frames_json=getattr(vs, "frames", None),
        )
    except Exception:
        _log.exception("Failed to persist detection feedback event for #%s", detection_id)
    return None, {
        "message": "Species updated" + (f" ({updated_count} videos)" if updated_count > 1 else ""),
        "species_id": species_id,
        "updated_count": updated_count,
        "apply_scope": apply_scope,
    }


def apply_detection_nickname_patch(
    session,
    detection_id: int,
    data: dict,
) -> tuple[dict | None, dict | None]:
    """Update per-detection nickname (and sidecar label when present)."""
    if "individual_nickname" not in data:
        return {"error": "individual_nickname is required"}, None

    raw = data.get("individual_nickname")
    if raw is None:
        nickname = None
    elif isinstance(raw, str):
        nickname = raw.strip() or None
    else:
        return {"error": "individual_nickname must be a string or null"}, None

    if nickname and len(nickname) > 64:
        return {"error": "individual_nickname is too long (max 64)"}, None

    vs = session.get(VideoSpecies, detection_id)
    if not vs:
        return {"error": "Detection not found"}, None

    vs.individual_nickname = nickname
    session.flush()

    try:
        has_reid = bool(
            session.execute(text("SELECT 1 FROM sqlite_master WHERE type='table' AND name='reid_embedding'")).scalar()
        )
        if has_reid:
            session.execute(
                text("UPDATE reid_embedding SET individual_label = :label WHERE video_species_id = :vsid"),
                {"label": nickname, "vsid": vs.id},
            )
    except Exception:
        _log.exception("Failed to sync nickname into reid_embedding sidecar")

    session.commit()
    bust_response_caches()
    return None, {
        "message": "Nickname updated",
        "detection_id": vs.id,
        "individual_nickname": nickname,
    }


def delete_detection_with_feedback(
    session,
    app_logger,
    detection_id: int,
    data: dict,
) -> tuple[dict | None, dict | None]:
    """Delete one detection row and emit feedback-loop/audit events (#397)."""
    source = normalize_correction_source(data.get("source"))
    reason = (data.get("reason") or "").strip() or None

    vs = session.get(VideoSpecies, detection_id)
    if not vs:
        return {"error": "Detection not found"}, None

    old_species_id = vs.species_id
    old_species_name = vs.species.name if vs.species else None
    video_id = vs.video_id
    track_id = vs.track_id
    species_visit_id = vs.species_visit_id
    detection_provider = vs.detection_provider
    confidence = vs.confidence
    frames_json = vs.frames

    visit = vs.species_visit
    session.delete(vs)
    session.flush()

    if visit:
        remaining = list(visit.video_species)
        if not remaining:
            session.delete(visit)
        else:
            starts = []
            ends = []
            for item in remaining:
                if not item.video or item.start_time is None or item.end_time is None:
                    continue
                base = ensure_utc(item.video.start_time)
                starts.append(base + timedelta(seconds=float(item.start_time)))
                ends.append(base + timedelta(seconds=float(item.end_time)))
            if starts and ends:
                visit.start_time = min(starts)
                visit.end_time = max(ends)
            visit.max_simultaneous = max(1, int(getattr(visit, "max_simultaneous", 1) or 1))

    session.commit()
    bust_response_caches()

    try:
        data_dir = str(app_config.get("directories.data") or "data")
        removed_crops = delete_dataset_crops_for_track(
            data_dir=data_dir,
            video_id=int(video_id),
            track_id=track_id,
        )
    except Exception:
        removed_crops = 0
        _log.exception("Failed to delete dataset crops for detection #%s", detection_id)

    write_correction_activity(
        session,
        action="delete_detection",
        source=source,
        detection_id=detection_id,
        from_species_name=old_species_name,
        to_species_name="Background",
        updated_count=1,
        apply_scope="single_track",
        reason=reason,
        video_id=video_id,
        track_id=track_id,
        species_visit_id=species_visit_id,
        from_species_id=old_species_id,
        to_species_id=None,
    )
    try:
        record_feedback_event(
            session,
            video_species_id=detection_id,
            video_id=video_id,
            track_id=track_id,
            from_species_id=old_species_id,
            to_species_id=None,
            from_species_name=old_species_name,
            to_species_name="Background",
            trigger_source=source,
            apply_scope="single_track",
            reason=reason,
            detection_provider=detection_provider,
            confidence=confidence,
            frames_json=frames_json,
        )
    except Exception:
        _log.exception("Failed to persist delete feedback event for #%s", detection_id)

    app_logger.info(
        "Detection deleted by operator: id=%s video_id=%s track_id=%s crops_removed=%s",
        detection_id,
        video_id,
        track_id,
        removed_crops,
    )
    return None, {
        "message": "Detection deleted",
        "detection_id": detection_id,
        "video_id": video_id,
        "track_id": track_id,
        "removed_dataset_crops": int(removed_crops),
    }
