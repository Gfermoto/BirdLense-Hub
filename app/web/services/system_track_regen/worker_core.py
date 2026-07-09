"""Фоновая перегенерация треков (YOLO+ByteTrack) для UI system API (#293).

Реализация: ``services/system_track_regen/worker_core.py``; shim —
``services/system_track_regen_worker.py`` (#344).
"""

from __future__ import annotations

import os
import sys
import json
from datetime import datetime, timedelta, timezone

import routes.ui_system_jobs_state as job_state
from app_config.app_config import app_config
from data_paths import resolve_recording_video_file
from models import ActivityLog, Species, Video, VideoSpecies, db
from services.http_response_cache import bust_response_caches
from services.species_identity_service import SpeciesIdentityService
from services.species_registry_service import resolve_species_name
from services.track_regen_service import (
    build_track_regen_policy_snapshot as _build_track_regen_policy_snapshot,
    derive_track_regen_species_scope as _derive_track_regen_species_scope,
    remap_detection_to_local_scope as _remap_detection_to_local_scope,
    run_track_regen_with_precise_fallback as _run_track_regen_with_precise_fallback,
    summarize_track_regen_detections as _summarize_track_regen_detections,
)
from services.visit_processor import VisitProcessor
from shared.ctor_kwarg_guard import assert_ctor_kwargs
from sqlalchemy import or_, select


def _processor_src_dir() -> str:
    """``app/processor/src`` от каталога ``app/web`` (где ``app.py``), независимо от вложенности модуля."""
    d = os.path.dirname(os.path.abspath(__file__))
    while d != os.path.dirname(d):
        if os.path.isfile(os.path.join(d, "app.py")):
            return os.path.normpath(os.path.join(d, "..", "processor", "src"))
        d = os.path.dirname(d)
    raise RuntimeError("BirdLense web app root (app.py) not found for processor src")


def manual_conflict_with_detection(
    manual_rows,
    detection: dict,
    tracks_same_species,
) -> bool:
    """Drop auto detections that conflict with already manual-corrected rows."""
    det_name = (detection.get("species_name") or "").strip()
    det_track_id = detection.get("track_id")
    det_start = float(detection.get("start_time") or 0.0)
    det_end = float(detection.get("end_time") or 0.0)
    for row in manual_rows:
        manual_species = getattr(getattr(row, "species", None), "name", "") or ""
        if manual_species and tracks_same_species(manual_species, det_name):
            continue
        row_track_id = getattr(row, "track_id", None)
        if row_track_id is not None and det_track_id is not None and row_track_id == det_track_id:
            return True
        overlap = min(float(getattr(row, "end_time", 0.0) or 0.0), det_end) - max(
            float(getattr(row, "start_time", 0.0) or 0.0),
            det_start,
        )
        if overlap > 0.3:
            return True
    return False


def run_regenerate_tracks_worker(
    flask_app,
    force: bool,
    start_date: str | None,
    end_date: str | None,
    frame_step_override: int | None = None,
    video_ids: list[int] | None = None,
    species_ids: list[int] | None = None,
) -> None:
    """Background: run YOLO+ByteTrack; mutates job_state._regenerate_tracks_status."""
    target_video_ids = sorted(set(video_ids or []))
    active_request_video_id = target_video_ids[0] if len(target_video_ids) == 1 else None
    job_state._regenerate_tracks_status = {
        "status": "running",
        "result": None,
        "error": None,
        "progress": {
            "processed": 0,
            "total": 0,
            "generated": 0,
            "failed": 0,
            "skipped": 0,
            "current_video": None,
            "current_video_id": None,
            "active_request_video_id": active_request_video_id,
            "phase": "initializing",
        },
    }
    try:
        with flask_app.app_context():
            sys.path.insert(0, _processor_src_dir())
            from track_regenerator import (
                build_detection_pipeline,
                process_video_for_tracks,
            )
            from decision_trace_builder import build_decision_trace_payload
            from detection_fusion import build_fused_video_detections

            match_live = bool(
                app_config.get("processor.track_regen_match_live_pipeline", True),
            )
            single_video_mode = len(target_video_ids) == 1
            profile = "match_live" if match_live else "batch"
            from inference_lores import (
                resolve_inference_lores_size,
                resolve_track_regen_lores_size,
            )

            if match_live:
                lores_size = resolve_inference_lores_size(app_config)
                lores_px = max(lores_size)
                frame_step = 1
            else:
                lores_size = resolve_track_regen_lores_size(app_config)
                lores_px = max(lores_size)
                frame_step = int(frame_step_override or app_config.get("processor.track_regen_frame_step") or 1)
                frame_step = max(1, min(frame_step, 30))
            regen_strategy = (
                app_config.get("processor.track_regen_detection_strategy")
                or app_config.get("processor.detection_strategy")
                or "two_stage"
            )
            max_runtime_sec = int(app_config.get("processor.track_regen_video_timeout_sec") or 300)
            if single_video_mode and not match_live:
                live_wh = resolve_inference_lores_size(app_config)
                lores_size = (
                    max(lores_size[0], live_wh[0]),
                    max(lores_size[1], live_wh[1]),
                )
                lores_px = max(lores_size)
                frame_step = min(frame_step, 2)
                max_runtime_sec = max(
                    max_runtime_sec,
                    int(app_config.get("processor.track_regen_precise_timeout_sec") or 420),
                )
                profile = "single_video_quality"
            effective_match_live = bool(match_live or single_video_mode)
            dt_start = None
            dt_end = None
            species_ids_f = sorted(set(species_ids or []))
            regen_params = {
                "frame_step": frame_step,
                "lores_px": lores_px,
                "detection_strategy": str(regen_strategy).strip(),
                "max_runtime_sec": max_runtime_sec,
                "profile": profile,
            }
            if species_ids_f:
                regen_params["species_ids"] = species_ids_f
                regen_params["species_partial_regen"] = True
            regen_params["ignore_regional_species"] = bool(
                app_config.get("processor.track_regen_ignore_regional_species", True)
            )
            regen_params["match_live_pipeline"] = effective_match_live
            parallel_auto_with_manual = bool(
                app_config.get(
                    "processor.track_regen_parallel_auto_with_manual",
                    False,
                ),
            )
            regen_params["parallel_auto_with_manual"] = parallel_auto_with_manual
            job_state._regenerate_tracks_status["progress"]["regen_params"] = regen_params

            if target_video_ids:
                q = Video.query.filter(Video.id.in_(target_video_ids))
            elif force:
                q = Video.query
            elif species_ids_f:
                q = Video.query.join(VideoSpecies).filter(VideoSpecies.species_id.in_(species_ids_f)).distinct()
            else:
                q = (
                    Video.query.join(VideoSpecies)
                    .filter(
                        or_(
                            VideoSpecies.frames.is_(None),
                            VideoSpecies.frames == "",
                            VideoSpecies.frames == "[]",
                        )
                    )
                    .distinct()
                )

            if start_date:
                try:
                    dt_start = datetime.strptime(start_date, "%Y-%m-%d").replace(
                        tzinfo=timezone.utc,
                    )
                    q = q.filter(Video.start_time >= dt_start)
                except ValueError:
                    flask_app.logger.warning("Invalid start_date %s, ignoring", start_date)
            if end_date:
                try:
                    dt_end = datetime.strptime(end_date, "%Y-%m-%d").replace(
                        tzinfo=timezone.utc,
                    ) + timedelta(days=1)
                    q = q.filter(Video.start_time < dt_end)
                except ValueError:
                    flask_app.logger.warning("Invalid end_date %s, ignoring", end_date)

            if species_ids_f and force:
                vid_subq = select(VideoSpecies.video_id).where(VideoSpecies.species_id.in_(species_ids_f)).distinct()
                q = q.filter(Video.id.in_(vid_subq))

            videos = q.order_by(Video.start_time.asc()).all()
            total = len(videos)
            job_state._regenerate_tracks_status["progress"]["total"] = total
            if total == 0 and target_video_ids:
                flask_app.logger.warning(
                    "Track regen: no videos for explicit ids %s (missing or filtered out)",
                    target_video_ids,
                )
            if total == 0 and species_ids_f:
                flask_app.logger.info(
                    "Track regen: empty queue (species_ids=%s, start_date=%s, end_date=%s, force=%s)",
                    species_ids_f,
                    start_date,
                    end_date,
                    force,
                )

            generated = 0
            failed = 0
            skipped = 0
            frames_updated = 0
            single_video_regen_summary: dict | None = None
            precise_candidates: list[dict] = []
            regen_species_scope = None
            regen_species_scope_lc: set[str] = set()
            if app_config.get("processor.track_regen_ignore_regional_species", True) and not effective_match_live:
                regen_species_scope = _derive_track_regen_species_scope(dt_start)
                if regen_species_scope:
                    regen_species_scope_lc = {
                        str(name).strip().lower() for name in regen_species_scope if str(name).strip()
                    }
                    regen_params["local_species_scope_count"] = len(regen_species_scope)
            regional_species_override = (
                list(app_config.get("processor.regional_species") or []) if effective_match_live else None
            )

            visit_timeout = int(app_config.get("detection.dedup_window_seconds") or 60)
            _vp_kw = {"visit_timeout": visit_timeout, "update_species_metadata": False}
            assert_ctor_kwargs(
                VisitProcessor.__init__,
                _vp_kw,
                label="track_regen VisitProcessor",
            )
            visit_processor = VisitProcessor(db, flask_app.logger, **_vp_kw)
            species_identity = SpeciesIdentityService(db, flask_app.logger)
            frame_processor, decision_maker = build_detection_pipeline(
                app_config,
                strategy_override=regen_strategy,
                for_track_regen=True,
                regional_species_override=regional_species_override,
            )
            precise_lores_px = max(lores_px, max(resolve_inference_lores_size(app_config)))
            precise_frame_step = 1 if single_video_mode else min(frame_step, 2)
            precise_strategy = (
                app_config.get("processor.track_regen_precise_detection_strategy")
                or app_config.get("processor.track_regen_detection_strategy")
                or app_config.get("processor.detection_strategy")
                or regen_strategy
                or "two_stage"
            )
            precise_max_runtime_sec = max(
                max_runtime_sec,
                int(app_config.get("processor.track_regen_precise_timeout_sec") or 420),
            )
            precise_min_center_dist = float(app_config.get("processor.track_regen_precise_min_center_dist") or 0.02)
            precise_enabled = any(
                (
                    precise_lores_px != lores_px,
                    precise_frame_step != frame_step,
                    str(precise_strategy).strip() != str(regen_strategy).strip(),
                    precise_max_runtime_sec != max_runtime_sec,
                    app_config.get("processor.track_regen_precise_min_center_dist") is not None,
                )
            )
            precise_params = (
                {
                    "frame_step": precise_frame_step,
                    "lores_px": precise_lores_px,
                    "detection_strategy": str(precise_strategy).strip(),
                    "max_runtime_sec": precise_max_runtime_sec,
                    "min_center_dist": precise_min_center_dist,
                }
                if precise_enabled
                else None
            )
            if precise_params:
                regen_params["precise_fallback"] = precise_params
            precise_pipeline = None
            try:
                _trff = app_config.get("processor.track_regen_fusion_min_confidence_to_store")
                track_regen_fusion_floor = float(_trff) if _trff is not None else None
            except (TypeError, ValueError):
                track_regen_fusion_floor = None
            species_scope = set(species_ids_f) if species_ids_f else None
            scope_catalog_species: list[Species] = []
            scope_names_lc: set[str] = set()
            scope_taxon_ids: set[int] = set()
            if species_scope:
                for sid in species_ids_f:
                    sp = db.session.get(Species, sid)
                    if not sp:
                        continue
                    scope_catalog_species.append(sp)
                    if sp.name:
                        scope_names_lc.add(sp.name.strip().lower())
                    if sp.taxon_id is not None:
                        scope_taxon_ids.add(sp.taxon_id)
            species_name_to_id_cache: dict[str, int | None] = {}

            def _resolved_species_id_for_det(detection: dict) -> int | None:
                name = (detection.get("species_name") or "").strip()
                if not name:
                    return None
                if name not in species_name_to_id_cache:
                    sp = species_identity.resolve_or_create_species(name, source="ingest")
                    species_name_to_id_cache[name] = sp.id if sp else None
                return species_name_to_id_cache[name]

            def _detection_in_species_scope(detection: dict) -> bool:
                if not species_scope:
                    return True
                sid = _resolved_species_id_for_det(detection)
                if sid and sid in species_scope:
                    return True
                name = (detection.get("species_name") or "").strip()
                if not name:
                    return False
                if name.lower() in scope_names_lc:
                    return True
                res = resolve_species_name(name, source="ingest")
                if res.found and res.taxon and res.taxon.id in scope_taxon_ids:
                    return True
                return False

            def _remap_det_for_scope(detection: dict) -> dict:
                if not species_scope:
                    return detection
                sid = _resolved_species_id_for_det(detection)
                if sid and sid in species_scope:
                    return detection
                name = (detection.get("species_name") or "").strip()
                if not name:
                    return detection
                nlc = name.lower()
                if nlc in scope_names_lc:
                    for sp in scope_catalog_species:
                        if sp.name and sp.name.strip().lower() == nlc:
                            return {**detection, "species_name": sp.name}
                res = resolve_species_name(name, source="ingest")
                if res.found and res.taxon:
                    tid = res.taxon.id
                    for sp in scope_catalog_species:
                        if sp.taxon_id == tid:
                            return {**detection, "species_name": sp.name}
                return detection

            def _tracks_same_species(db_name: str, det_name: str) -> bool:
                if not db_name or not det_name:
                    return False
                if db_name.strip().lower() == det_name.strip().lower():
                    return True
                ra = resolve_species_name(db_name.strip(), source="ingest")
                rb = resolve_species_name(det_name.strip(), source="ingest")
                if ra.found and rb.found and ra.taxon and rb.taxon and ra.taxon.id == rb.taxon.id:
                    return True
                return False

            for video in videos:
                if job_state._regenerate_tracks_cancel_requested:
                    job_state._regenerate_tracks_status = {
                        "status": "cancelled",
                        "result": {
                            "generated": generated,
                            "failed": failed,
                            "skipped": skipped,
                            "frames_updated": frames_updated,
                            "cancelled": True,
                        },
                        "error": None,
                        "progress": job_state._regenerate_tracks_status.get("progress"),
                    }
                    job_state._regenerate_tracks_cancel_requested = False
                    return

                species_name_to_id_cache.clear()

                def _regen_progress(meta: dict):
                    try:
                        job_state._regenerate_tracks_status["progress"].update(meta)
                    except Exception:
                        flask_app.logger.debug(
                            "track regen progress update failed",
                            exc_info=True,
                        )

                job_state._regenerate_tracks_status["progress"].update(
                    current_video=video.video_path or None,
                    current_video_id=video.id,
                    phase="yolo_decode",
                    yolo_frames_done=0,
                    yolo_frames_total=None,
                )
                if not video.video_path:
                    skipped += 1
                    precise_candidates.append(
                        {
                            "video_id": video.id,
                            "video_path": None,
                            "reason": "missing_video_path",
                        }
                    )
                    job_state._regenerate_tracks_status["progress"].update(
                        processed=generated + failed + skipped,
                        generated=generated,
                        failed=failed,
                        skipped=skipped,
                    )
                    continue
                full_video = resolve_recording_video_file(video.video_path)
                if not full_video:
                    skipped += 1
                    precise_candidates.append(
                        {
                            "video_id": video.id,
                            "video_path": video.video_path,
                            "reason": "video_file_missing",
                        }
                    )
                    job_state._regenerate_tracks_status["progress"].update(
                        processed=generated + failed + skipped,
                        generated=generated,
                        failed=failed,
                        skipped=skipped,
                    )
                    continue

                try:
                    persisted_detections_for_trace: list[dict] = []
                    fast_kwargs = {
                        "lores_size": lores_size,
                        "frame_processor": frame_processor,
                        "decision_maker": decision_maker,
                        "frame_step": frame_step,
                        "max_runtime_sec": max_runtime_sec,
                        "progress_hook": _regen_progress,
                        "progress_hook_interval": 15,
                    }

                    def _precise_kwargs():
                        nonlocal precise_pipeline
                        if not precise_params:
                            return None
                        if precise_pipeline is None:
                            precise_scope_override = (
                                regional_species_override if effective_match_live else regen_species_scope
                            )
                            precise_pipeline = build_detection_pipeline(
                                app_config,
                                strategy_override=precise_strategy,
                                for_track_regen=True,
                                regional_species_override=precise_scope_override,
                                min_center_dist_override=precise_min_center_dist,
                            )
                        precise_frame_processor, precise_decision_maker = precise_pipeline
                        return {
                            "lores_size": (precise_lores_px, precise_lores_px),
                            "frame_processor": precise_frame_processor,
                            "decision_maker": precise_decision_maker,
                            "frame_step": precise_frame_step,
                            "max_runtime_sec": precise_max_runtime_sec,
                            "progress_hook": _regen_progress,
                            "progress_hook_interval": 15,
                        }

                    track_detections, precise_used = _run_track_regen_with_precise_fallback(
                        full_video,
                        process_video_for_tracks,
                        fast_kwargs,
                        _precise_kwargs if precise_enabled else None,
                    )
                    detections = build_fused_video_detections(
                        track_detections,
                        [],
                        start_time=video.start_time,
                        end_time=video.end_time,
                        app_config=app_config,
                        fusion_min_confidence_to_store=track_regen_fusion_floor,
                    )
                    if not detections and track_detections and precise_enabled and not precise_used:
                        precise_kwargs = _precise_kwargs()
                        if precise_kwargs:
                            assert_ctor_kwargs(
                                process_video_for_tracks,
                                precise_kwargs,
                                label="track_regen post-fusion precise_kwargs",
                            )
                            track_detections = process_video_for_tracks(
                                full_video,
                                **precise_kwargs,
                            )
                            precise_used = True
                            detections = build_fused_video_detections(
                                track_detections,
                                [],
                                start_time=video.start_time,
                                end_time=video.end_time,
                                app_config=app_config,
                                fusion_min_confidence_to_store=track_regen_fusion_floor,
                            )
                            flask_app.logger.info(
                                "Track regen: post-fusion precise pass (video_id=%s path=%s)",
                                video.id,
                                video.video_path,
                            )
                    if regen_species_scope_lc:
                        detections = [_remap_detection_to_local_scope(d, regen_species_scope_lc) for d in detections]
                    if not detections:
                        flask_app.logger.warning(
                            "Track regen: fused empty (video_id=%s path=%s precise_used=%s "
                            "raw_track_rows=%s regen_fusion_floor=%s)",
                            video.id,
                            video.video_path,
                            precise_used,
                            len(track_detections or []),
                            track_regen_fusion_floor,
                        )
                        reason = "no_detections_after_precise_pass" if precise_used else "no_detections_fast_run"
                        skipped += 1
                        precise_candidates.append(
                            {
                                "video_id": video.id,
                                "video_path": video.video_path,
                                "reason": reason,
                            }
                        )
                        job_state._regenerate_tracks_status["progress"].update(
                            processed=generated + failed + skipped,
                            generated=generated,
                            failed=failed,
                            skipped=skipped,
                        )
                        continue
                    if precise_used:
                        flask_app.logger.info(
                            "Track regen precise fallback recovered detections "
                            "(video_id=%s path=%s strategy=%s frame_step=%s lores_px=%s)",
                            video.id,
                            video.video_path,
                            precise_strategy,
                            precise_frame_step,
                            precise_lores_px,
                        )
                    single_video_summary_extra = {
                        "profile": profile,
                        "raw_track_fragment_count": len(track_detections),
                        "post_fusion_track_count": len(detections),
                    }
                    precise_policy = {}
                    if precise_used and precise_pipeline:
                        precise_policy = dict(getattr(precise_pipeline[0], "pipeline_policy", {}) or {})
                    regen_policy = _build_track_regen_policy_snapshot(
                        profile=profile,
                        match_live_pipeline=effective_match_live,
                        strategy=regen_strategy,
                        frame_step=frame_step,
                        lores_px=lores_px,
                        max_runtime_sec=max_runtime_sec,
                        precise_used=precise_used,
                        precise_params=precise_params,
                        local_species_scope_count=len(regen_species_scope_lc),
                        species_scope_selected=bool(species_scope),
                    )
                    fast_policy = dict(getattr(frame_processor, "pipeline_policy", {}) or {})

                    scoped_detections: list[dict] | None = None
                    if species_scope:
                        scoped_detections = []
                        for d in detections:
                            if not _detection_in_species_scope(d):
                                continue
                            scoped_detections.append(_remap_det_for_scope(d))
                        if not scoped_detections:
                            sample = [d.get("species_name") for d in detections[:8]]
                            flask_app.logger.info(
                                "Track regen: no detections match species scope "
                                "(video_id=%s scope=%s sample_model_names=%s)",
                                video.id,
                                sorted(species_scope),
                                sample,
                            )
                            skipped += 1
                            precise_candidates.append(
                                {
                                    "video_id": video.id,
                                    "video_path": video.video_path,
                                    "reason": "no_detections_for_selected_species",
                                }
                            )
                            job_state._regenerate_tracks_status["progress"].update(
                                processed=generated + failed + skipped,
                                generated=generated,
                                failed=failed,
                                skipped=skipped,
                            )
                            continue

                    manual_vs = [vs for vs in video.video_species if vs.manually_corrected]
                    if manual_vs:
                        used_det_indices = set()
                        manual_frames_rows_updated = 0
                        manuals_ordered = sorted(
                            (
                                [vs for vs in manual_vs if vs.species_id in species_scope]
                                if species_scope
                                else manual_vs
                            ),
                            key=lambda x: x.start_time,
                        )
                        for vs in manuals_ordered:
                            best_idx = None
                            best_overlap = 0.0
                            vs_species_name = vs.species.name if vs.species else None
                            for i, d in enumerate(detections):
                                if i in used_det_indices:
                                    continue
                                if vs_species_name and not _tracks_same_species(
                                    vs_species_name, d.get("species_name") or ""
                                ):
                                    continue
                                overlap = min(vs.end_time, d["end_time"]) - max(
                                    vs.start_time,
                                    d["start_time"],
                                )
                                if overlap > best_overlap and overlap > 0.3:
                                    best_overlap = overlap
                                    best_idx = i
                            if best_idx is not None and detections[best_idx].get("frames"):
                                vs.frames = json.dumps(detections[best_idx]["frames"])
                                used_det_indices.add(best_idx)
                                manual_frames_rows_updated += 1
                        db.session.flush()
                        unmatched = [d for i, d in enumerate(detections) if i not in used_det_indices]
                        if not parallel_auto_with_manual:
                            unmatched = [
                                d
                                for d in unmatched
                                if not manual_conflict_with_detection(manuals_ordered, d, _tracks_same_species)
                            ]
                        if species_scope:
                            unmatched = [_remap_det_for_scope(d) for d in unmatched if _detection_in_species_scope(d)]
                        if species_scope:
                            ids_touched = {_resolved_species_id_for_det(d) for d in unmatched}
                            ids_touched &= species_scope
                            to_delete = [
                                vs
                                for vs in video.video_species
                                if not vs.manually_corrected and vs.species_id in ids_touched
                            ]
                        else:
                            to_delete = [vs for vs in video.video_species if not vs.manually_corrected]
                        for vs in to_delete:
                            db.session.delete(vs)
                        if unmatched:
                            visit_processor.process_detections(video, unmatched)
                        persisted_detections_for_trace = list(unmatched)
                        if manual_frames_rows_updated:
                            frames_updated += manual_frames_rows_updated
                        if len(target_video_ids) == 1 and video.id == target_video_ids[0]:
                            single_video_regen_summary = _summarize_track_regen_detections(
                                unmatched,
                            )
                            single_video_regen_summary.update(single_video_summary_extra)
                            single_video_regen_summary["manual_frames_rows_updated"] = int(manual_frames_rows_updated)
                            single_video_regen_summary["manual_tracks_overlay_expected"] = (
                                manual_frames_rows_updated > 0
                            )
                            single_video_regen_summary["tracks_overlay_expected"] = bool(
                                manual_frames_rows_updated > 0
                                or single_video_regen_summary.get("tracks_overlay_expected")
                            )
                        precise_candidates.append(
                            {
                                "video_id": video.id,
                                "video_path": video.video_path,
                                "reason": (
                                    "has_manual_corrections"
                                    if manual_frames_rows_updated
                                    else "has_manual_corrections_no_frame_match"
                                ),
                            }
                        )
                    elif species_scope:
                        ids_touched = {_resolved_species_id_for_det(d) for d in scoped_detections}
                        ids_touched &= species_scope
                        if ids_touched:
                            VideoSpecies.query.filter(
                                VideoSpecies.video_id == video.id,
                                VideoSpecies.species_id.in_(ids_touched),
                                VideoSpecies.manually_corrected.is_(False),
                            ).delete(synchronize_session=False)
                        visit_processor.process_detections(video, scoped_detections)
                        persisted_detections_for_trace = list(scoped_detections)
                        if len(target_video_ids) == 1 and video.id == target_video_ids[0]:
                            single_video_regen_summary = _summarize_track_regen_detections(
                                scoped_detections,
                            )
                            single_video_regen_summary.update(single_video_summary_extra)
                    else:
                        VideoSpecies.query.filter_by(video_id=video.id).delete()
                        visit_processor.process_detections(video, detections)
                        persisted_detections_for_trace = list(detections)
                        if len(target_video_ids) == 1 and video.id == target_video_ids[0]:
                            single_video_regen_summary = _summarize_track_regen_detections(
                                detections,
                            )
                            single_video_regen_summary.update(single_video_summary_extra)
                    generated += 1
                    decision_trace = build_decision_trace_payload(
                        app_config=app_config,
                        start_time=video.start_time,
                        end_time=video.end_time,
                        video_path=str(video.video_path or ""),
                        persisted_tracks=persisted_detections_for_trace,
                        rejected_tracks=[],
                        video_id=video.id,
                        recording_context={
                            "triggered_by": "track_regen",
                            "trigger_display": "Track regen",
                            "motion_source": "track_regen",
                            "active_triggers": [],
                            "video_source": "archive_mp4",
                            "regen_profile": profile,
                            "pipeline_policy": {
                                "fast": fast_policy,
                                "precise": precise_policy,
                                "regen": regen_policy,
                            },
                            "runtime_signals": {
                                "frames_seen": None,
                                "yolo_frames_ran": None,
                                "yolo_frames_with_tracks": len(track_detections),
                                "low_light_blocked_frames": 0,
                                "session_extended_by_frigate_only": 0,
                                "yolo_ran": True,
                                "yolo_track_found": bool(track_detections),
                                "session_extended_by_frigate": False,
                                "precise_fallback_used": bool(precise_used),
                            },
                        },
                    )
                    db.session.add(ActivityLog(type="decision_trace", data=json.dumps(decision_trace)))
                    db.session.commit()
                except Exception as e:
                    db.session.rollback()
                    flask_app.logger.exception("Track regen failed %s: %s", video.video_path, e)
                    failed += 1
                    precise_candidates.append(
                        {
                            "video_id": video.id,
                            "video_path": video.video_path,
                            "reason": "processing_failed",
                        }
                    )

                job_state._regenerate_tracks_status["progress"].update(
                    processed=generated + failed + skipped,
                    generated=generated,
                    failed=failed,
                    skipped=skipped,
                )

            flask_app.logger.info(
                "Tracks: generated=%s, frames_updated=%s, failed=%s, skipped=%s",
                generated,
                frames_updated,
                failed,
                skipped,
            )
            if generated or frames_updated or precise_candidates:
                bust_response_caches()
            result = {
                "generated": generated,
                "failed": failed,
                "skipped": skipped,
                "regen_params": regen_params,
            }
            if single_video_regen_summary is not None:
                result["single_video_regen"] = single_video_regen_summary
                result["tracks_overlay_expected"] = bool(single_video_regen_summary.get("tracks_overlay_expected"))
            if frames_updated:
                result["frames_updated"] = frames_updated
            if precise_candidates:
                dedup = {}
                for item in precise_candidates:
                    dedup[(item["video_id"], item["reason"])] = item
                result["precise_rerun_candidates"] = list(dedup.values())[:500]
                result["precise_rerun_candidate_count"] = len(dedup)
            if target_video_ids:
                result["target_video_ids"] = list(target_video_ids)
            job_state._regenerate_tracks_status = {
                "status": "done",
                "result": result,
                "error": None,
                "progress": None,
            }
    except Exception:
        db.session.rollback()
        flask_app.logger.exception("Regenerate tracks failed")
        job_state._regenerate_tracks_status = {
            "status": "done",
            "result": None,
            "error": "Track regeneration failed",
            "progress": None,
        }
