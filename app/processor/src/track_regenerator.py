"""
Regenerate ByteTrack tracks for an existing video file.
Runs YOLO+ByteTrack on each frame and returns detections with frames.
"""

from __future__ import annotations

import logging
import os
import threading
from contextlib import contextmanager

from shared.ctor_kwarg_guard import assert_ctor_kwargs

logger = logging.getLogger(__name__)
_TRACK_REGEN_INFER_LOCK = threading.RLock()


@contextmanager
def _track_regen_interprocess_lock(enabled: bool):
    """Optional cross-process lock to prevent concurrent heavy regen OOM on small hosts."""
    if not enabled:
        yield
        return
    lock_path = "/tmp/birdlense_track_regen.lock"
    lock_fd = None
    try:
        import fcntl

        lock_fd = open(lock_path, "w", encoding="utf-8")
        fcntl.flock(lock_fd.fileno(), fcntl.LOCK_EX)
        yield
    finally:
        if lock_fd is not None:
            try:
                import fcntl

                fcntl.flock(lock_fd.fileno(), fcntl.LOCK_UN)
            except Exception:
                logger.debug("Track regen: interprocess unlock failed", exc_info=True)
            try:
                lock_fd.close()
            except Exception:
                logger.debug("Track regen: lock file close failed", exc_info=True)


def _track_detection_preference(detection: dict) -> tuple[int, int, float]:
    """Prefer specific species over Bird/Unknown for the same track."""
    name = str(detection.get("species_name") or "").strip().lower()
    if name == "unknown":
        species_rank = 0
    elif name in {"bird", "squirrel", "rodent"}:
        species_rank = 1
    else:
        species_rank = 2
    has_frames = 1 if detection.get("frames") else 0
    confidence = float(detection.get("confidence") or 0.0)
    return (species_rank, has_frames, confidence)


def _dedupe_track_detections(detections: list[dict]) -> list[dict]:
    """Collapse accidental duplicate outputs for the same track window."""
    deduped: dict[tuple, dict] = {}
    for detection in detections:
        track_id = detection.get("track_id")
        if track_id is None:
            key = None
        else:
            key = (
                track_id,
                str(detection.get("detection_provider") or ""),
                str(detection.get("species_name") or "").strip().lower(),
            )
        if key is None:
            deduped[(id(detection),)] = detection
            continue
        existing = deduped.get(key)
        if existing is None:
            deduped[key] = detection
            continue
        keep, drop = existing, detection
        if _track_detection_preference(detection) > _track_detection_preference(existing):
            keep, drop = detection, existing
        if not keep.get("frames") and drop.get("frames"):
            keep = {**keep, "frames": drop.get("frames")}
        deduped[key] = keep
        logger.warning(
            "Track regen: collapsed duplicate track_id=%s provider=%s -> kept %s, dropped %s",
            track_id,
            key[1],
            keep.get("species_name"),
            drop.get("species_name"),
        )
    return list(deduped.values())



def _soft_near_miss_detections(tracks, app_config, species_mapping) -> list[dict]:
    """Emit review-only rows for prior-backed soft near-miss (e.g. dove under pigeon)."""
    from species_normalizer import normalize
    from processor_config_defaults import CLASSIFIER_BEST_GUESS_MIN_CONFIDENCE

    try:
        min_guess = float(
            app_config.get("processor.classifier_best_guess_min_confidence")
            or CLASSIFIER_BEST_GUESS_MIN_CONFIDENCE
        )
    except (TypeError, ValueError):
        min_guess = float(CLASSIFIER_BEST_GUESS_MIN_CONFIDENCE)

    unknown = {"bird", "unknown", "unknown bird"}
    try:
        u = str(app_config.get("processor.birder_eu_unknown_label") or "Unknown Bird").strip().lower()
        unknown.add(u)
    except Exception:
        pass

    soft_reasons = {"topk_prior", "unknown_topk_prior", "prior_open_set_guess"}
    adjust_fn = None
    data_dir = None
    try:
        from processor_support import get_data_dir
        from site_adapter import adjust_confidence_with_site_adapter

        adjust_fn = adjust_confidence_with_site_adapter
        data_dir = get_data_dir()
    except Exception:
        pass

    extras: list[dict] = []
    seen: set[tuple] = set()
    for tid, track in (tracks or {}).items():
        if not isinstance(track, dict):
            continue
        frames = track.get("frames") or []
        try:
            start_time = float(track.get("start_time") or 0.0)
            end_time = float(track.get("end_time") or start_time)
        except (TypeError, ValueError):
            start_time, end_time = 0.0, 0.0
        for ev in track.get("classifier_events") or []:
            if not isinstance(ev, dict) or not ev.get("soft"):
                continue
            if str(ev.get("soft_reason") or "") not in soft_reasons:
                continue
            raw = str(ev.get("species_name") or "").strip()
            if not raw or raw.lower() in unknown:
                continue
            try:
                conf = float(ev.get("confidence") or 0.0)
            except (TypeError, ValueError):
                conf = 0.0
            adj = conf
            if adjust_fn is not None and data_dir is not None:
                try:
                    adj, info = adjust_fn(
                        data_dir=data_dir,
                        species=raw,
                        confidence=conf,
                        track_id=tid,
                    )
                    if not info.get("applied"):
                        adj = conf
                except Exception:
                    adj = conf
            if adj < min_guess:
                continue
            species_name = normalize(raw, species_mapping) if raw else raw
            key = (tid, str(species_name or "").strip().lower())
            if key in seen:
                continue
            seen.add(key)
            extras.append(
                {
                    "species_name": species_name,
                    "start_time": start_time,
                    "end_time": end_time,
                    "confidence": float(adj),
                    "track_id": tid,
                    "frames": frames,
                    "source": "video",
                    "detection_provider": "yolo_soft_near_miss",
                    "decision_reason": "soft_classifier_near_miss",
                    "decision_kind": "review_only_uncertain_species",
                    "visit_eligible": False,
                    "notification_eligible": False,
                    "classifier_needs_review": True,
                    "evidence_state": "weak_classifier",
                }
            )
    return extras


def _companion_hard_named_detections(tracks, app_config, species_mapping) -> list[dict]:
    """If soft near-miss fired on a track, also emit hard named parent (e.g. pigeon)."""
    from species_normalizer import normalize
    from processor_config_defaults import CLASSIFIER_BEST_GUESS_MIN_CONFIDENCE

    try:
        min_guess = float(
            app_config.get("processor.classifier_best_guess_min_confidence")
            or CLASSIFIER_BEST_GUESS_MIN_CONFIDENCE
        )
    except (TypeError, ValueError):
        min_guess = float(CLASSIFIER_BEST_GUESS_MIN_CONFIDENCE)

    unknown = {"bird", "unknown", "unknown bird"}
    try:
        unknown.add(str(app_config.get("processor.birder_eu_unknown_label") or "Unknown Bird").strip().lower())
    except Exception:
        pass

    soft_reasons = {"topk_prior", "unknown_topk_prior", "prior_open_set_guess"}
    adjust_fn = None
    data_dir = None
    try:
        from processor_support import get_data_dir
        from site_adapter import adjust_confidence_with_site_adapter

        adjust_fn = adjust_confidence_with_site_adapter
        data_dir = get_data_dir()
    except Exception:
        pass

    extras: list[dict] = []
    seen: set[tuple] = set()
    for tid, track in (tracks or {}).items():
        if not isinstance(track, dict):
            continue
        events = [e for e in (track.get("classifier_events") or []) if isinstance(e, dict)]
        if not any(e.get("soft") and str(e.get("soft_reason") or "") in soft_reasons for e in events):
            continue
        frames = track.get("frames") or []
        try:
            start_time = float(track.get("start_time") or 0.0)
            end_time = float(track.get("end_time") or start_time)
        except (TypeError, ValueError):
            start_time, end_time = 0.0, 0.0
        for ev in events:
            if ev.get("soft"):
                continue
            raw = str(ev.get("species_name") or "").strip()
            if not raw or raw.lower() in unknown:
                continue
            try:
                conf = float(ev.get("confidence") or 0.0)
            except (TypeError, ValueError):
                conf = 0.0
            adj = conf
            if adjust_fn is not None and data_dir is not None:
                try:
                    adj, info = adjust_fn(
                        data_dir=data_dir, species=raw, confidence=conf, track_id=tid
                    )
                    if not info.get("applied"):
                        adj = conf
                except Exception:
                    adj = conf
            if adj < min_guess:
                continue
            species_name = normalize(raw, species_mapping) if raw else raw
            key = (tid, str(species_name or "").strip().lower())
            if key in seen:
                continue
            seen.add(key)
            extras.append(
                {
                    "species_name": species_name,
                    "start_time": start_time,
                    "end_time": end_time,
                    "confidence": float(adj),
                    "track_id": tid,
                    "frames": frames,
                    "source": "video",
                    "detection_provider": "yolo_hard_companion",
                    "decision_reason": "hard_companion_of_soft_near_miss",
                    "decision_kind": "review_only_uncertain_species",
                    "visit_eligible": False,
                    "notification_eligible": False,
                    "classifier_needs_review": True,
                    "evidence_state": "weak_classifier",
                }
            )
    return extras



def build_detection_pipeline(
    app_config,
    strategy_override: str | None = None,
    for_track_regen: bool = False,
    regional_species_override: list[str] | None = None,
    min_center_dist_override: float | None = None,
):
    """Собрать frame_processor и decision_maker (см. ``build_detection_stack``)."""
    from detection_stack import build_detection_stack

    interprocess_serialize = bool(app_config.get("processor.track_regen_serialize_inference_interprocess", True))

    stack_kw = {
        "strategy_override": strategy_override,
        "for_track_regen": for_track_regen,
        "regional_species_override": regional_species_override,
        "min_center_dist_override": min_center_dist_override,
        "save_images": False,
        "warn_two_stage_fallback": False,
    }
    assert_ctor_kwargs(
        build_detection_stack,
        stack_kw,
        label="build_detection_pipeline→build_detection_stack",
    )
    with _track_regen_interprocess_lock(interprocess_serialize):
        fp, dm, _ = build_detection_stack(app_config, **stack_kw)
    return fp, dm


def process_video_for_tracks(
    video_path: str,
    lores_size: tuple[int, int] | None = None,
    frame_processor=None,
    decision_maker=None,
    frame_step: int = 1,
    max_runtime_sec: int | None = None,
    progress_hook=None,
    progress_hook_interval: int = 20,
    metrics_out: dict | None = None,
    camera_id: str | None = None,
):
    """
    Run YOLO+ByteTrack on video file. Returns list of detections with frames.
    Each detection: {species_name, start_time, end_time, confidence, track_id, frames, ...}

    progress_hook: вызывается из UI-воркера; meta: phase, yolo_frames_done, yolo_frames_total (оценка).
    """
    from app_config.app_config import app_config
    from species_mapping_config import build_species_mapping
    from species_normalizer import normalize
    from stream_probe import probe_video_file, publish_probe_gauges
    from tracking_service import TrackingService

    if not os.path.isfile(video_path):
        logger.warning("Video not found: %s", video_path)
        return []

    if frame_processor is None or decision_maker is None:
        frame_processor, decision_maker = build_detection_pipeline(
            app_config,
            for_track_regen=True,
        )
    frame_processor.reset()
    decision_maker.reset()
    frame_step = max(1, int(frame_step or 1))
    serialize_infer = bool(app_config.get("processor.track_regen_serialize_inference", True))
    interprocess_serialize = bool(app_config.get("processor.track_regen_serialize_inference_interprocess", True))

    probe_caps = probe_video_file(video_path)
    publish_probe_gauges(probe_caps)
    source_fps = float(probe_caps.fps) if probe_caps and probe_caps.fps > 0.5 else 0.0

    service = TrackingService.from_regen_pipeline(
        frame_processor,
        decision_maker,
        runtime_cfg=app_config.config,
        source_fps=source_fps,
        frame_step=frame_step,
    )
    infer_lock = _TRACK_REGEN_INFER_LOCK if serialize_infer else None

    with _track_regen_interprocess_lock(interprocess_serialize):
        service.process_video(
            video_path,
            camera_id=camera_id,
            frame_step=frame_step,
            max_runtime_sec=max_runtime_sec,
            progress_hook=progress_hook,
            progress_hook_interval=progress_hook_interval,
            metrics_out=metrics_out,
            infer_lock=infer_lock,
        )

    # Match live finalize: deferred Birder enrich before decisions (RC6 live gate).
    try:
        from finalize_classification import (
            defer_classifier_to_finalize,
            enrich_tracks_classifier_at_finalize,
        )

        if defer_classifier_to_finalize(app_config):
            clf_outcome = enrich_tracks_classifier_at_finalize(
                frame_processor.tracks,
                getattr(frame_processor, "strategy", None),
                app_config,
                video_path=video_path,
                camera_id=camera_id,
            )
            if metrics_out is not None and isinstance(clf_outcome, dict):
                metrics_out["classifier_finalize_outcome"] = clf_outcome
    except Exception:
        logger.debug("track_regen classifier enrich failed", exc_info=True)

    results = decision_maker.get_results(frame_processor.tracks)
    species_mapping = build_species_mapping(app_config)

    detections = []
    for r in results:
        raw_name = r.get("species_name") or ""
        species_name = normalize(raw_name, species_mapping) if raw_name else raw_name
        row = {
            "species_name": species_name,
            "start_time": r["start_time"],
            "end_time": r["end_time"],
            "confidence": r["confidence"],
            "track_id": r["track_id"],
            "frames": r.get("frames", []),
            "source": "video",
            "detection_provider": "yolo",
        }
        if r.get("decision_reason"):
            row["decision_reason"] = r["decision_reason"]
        for copy_key in (
            "visit_eligible",
            "notification_eligible",
            "decision_kind",
            "detector_label",
            "detector_confidence",
            "classifier_confidence",
            "classifier_species_name",
            "classifier_entropy",
            "classifier_top1_top2_margin",
            "classifier_needs_review",
            "evidence_state",
            "reject_reason_code",
        ):
            if copy_key in r:
                row[copy_key] = r[copy_key]
        detections.append(row)
    existing = {
        (d.get("track_id"), str(d.get("species_name") or "").strip().lower())
        for d in detections
    }
    for extra in (
        _soft_near_miss_detections(frame_processor.tracks, app_config, species_mapping)
        + _companion_hard_named_detections(frame_processor.tracks, app_config, species_mapping)
    ):
        key = (extra.get("track_id"), str(extra.get("species_name") or "").strip().lower())
        if key in existing:
            continue
        detections.append(extra)
        existing.add(key)
    detections = _dedupe_track_detections(detections)
    if metrics_out is not None:
        species = sorted(
            {str(d.get("species_name") or "").strip() for d in detections if str(d.get("species_name") or "").strip()}
        )
        metrics_out["fused_track_count"] = len(detections)
        metrics_out["species_detected"] = species
        metrics_out["species_detected_count"] = len(species)
        metrics_out.update(frame_processor.get_tracking_stability_stats())
    logger.info(
        "Track regen: %s -> %s detections, frame_step=%s unified_with_live=%s",
        video_path,
        len(detections),
        frame_step,
        bool(service.policy.unified_with_live),
    )
    if not detections and metrics_out and int(metrics_out.get("total_frames") or 0) > 0:
        logger.info(
            "Track regen: 0 accepted tracks after %s frames — если кадры есть, но пусто: "
            "снизить processor.min_confidence_binary_bird / min_confidence_to_process, "
            "проверить track_regen_match_live_pipeline и веса детектора/классификатора.",
            metrics_out.get("total_frames"),
        )
    return detections
