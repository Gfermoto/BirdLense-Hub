"""
Regenerate ByteTrack tracks for an existing video file.
Runs YOLO+ByteTrack on each frame and returns detections with frames.
"""

from __future__ import annotations

import logging
import math
import os
import time
import threading
from contextlib import contextmanager
import cv2

from shared.ctor_kwarg_guard import assert_ctor_kwargs
from frame_geometry import prepare_detector_pipeline_frame

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
):
    """
    Run YOLO+ByteTrack on video file. Returns list of detections with frames.
    Each detection: {species_name, start_time, end_time, confidence, track_id, frames, ...}

    progress_hook: вызывается из UI-воркера; meta: phase, yolo_frames_done, yolo_frames_total (оценка).
    """
    from app_config.app_config import app_config
    from pipeline_config import resolve_stream_fps
    from species_mapping_config import build_species_mapping
    from species_normalizer import normalize
    from stream_probe import attach_stream_capabilities, probe_video_file, publish_probe_gauges

    if not os.path.isfile(video_path):
        logger.warning(f"Video not found: {video_path}")
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

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        logger.warning(f"Cannot open video: {video_path}")
        return []

    probe_caps = probe_video_file(video_path)
    publish_probe_gauges(probe_caps)
    fps = float(probe_caps.fps) if probe_caps and probe_caps.fps > 0.5 else 0.0
    if fps <= 0.5:
        raw_fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
        fps = raw_fps if raw_fps > 0.5 else resolve_stream_fps(None, app_config)
    # Canvas geometry resolved per-frame via prepare_detector_pipeline_frame (mode=regen).
    frame_total_guess = cap.get(cv2.CAP_PROP_FRAME_COUNT)
    try:
        fcg = float(frame_total_guess)
        yolo_runs_est = int(math.ceil(fcg / float(frame_step))) if fcg > 1.5 else None
    except (TypeError, ValueError):
        yolo_runs_est = None
    if yolo_runs_est is not None:
        yolo_runs_est = max(1, yolo_runs_est)
    frame_count = 0
    runs_done = 0
    try:
        _hi = max(1, int(progress_hook_interval or 20))
    except (TypeError, ValueError):
        _hi = 20
    started = time.monotonic()
    try:
        with _track_regen_interprocess_lock(interprocess_serialize):
            while True:
                if max_runtime_sec and (time.monotonic() - started) > max_runtime_sec:
                    raise TimeoutError(f"Track regeneration timeout ({max_runtime_sec}s) for {video_path}")
                # Только decode+retrieve на обрабатываемых кадрах; между ними — grab()
                # без полного декодирования (иначе frame_step почти не ускоряет батч).
                if frame_count % frame_step == 0:
                    ret, frame = cap.read()
                    if not ret:
                        break
                    frame_time_sec = frame_count / fps
                    frame_resized, _det_hw, _overlay_hw, _lb_meta = prepare_detector_pipeline_frame(
                        frame,
                        app_config,
                        mode="regen",
                    )
                    if serialize_infer:
                        with _TRACK_REGEN_INFER_LOCK:
                            has_detections = frame_processor.run(
                                frame_resized,
                                frame_time=frame_time_sec,
                                skip_light_gate=True,
                                classification_frame=frame,
                            )
                    else:
                        has_detections = frame_processor.run(
                            frame_resized,
                            frame_time=frame_time_sec,
                            skip_light_gate=True,
                            classification_frame=frame,
                        )
                    decision_maker.update_has_detections(has_detections)
                    runs_done += 1
                    if progress_hook is not None and (
                        runs_done == 1
                        or runs_done % _hi == 0
                        or (yolo_runs_est is not None and runs_done >= yolo_runs_est)
                    ):
                        try:
                            progress_hook(
                                {
                                    "phase": "yolo_infer",
                                    "yolo_frames_done": runs_done,
                                    "yolo_frames_total": yolo_runs_est,
                                }
                            )
                        except Exception:
                            logger.debug("Track regen progress_hook failed", exc_info=True)
                else:
                    ret = cap.grab()
                    if not ret:
                        break
                frame_count += 1
    finally:
        cap.release()

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
    detections = _dedupe_track_detections(detections)
    logger.info(
        "Track regen: %s -> %s detections, %s frames, frame_step=%s",
        video_path,
        len(detections),
        frame_count,
        frame_step,
    )
    if not detections and frame_count > 0:
        logger.info(
            "Track regen: 0 accepted tracks after %s frames — если кадры есть, но пусто: "
            "снизить processor.min_confidence_binary_bird / min_confidence_to_process, "
            "увеличить track_regen_lores_px (single-video уже подтягивает inference_lores_px), "
            "или проверить веса детектора/классификатора.",
            frame_count,
        )
    return detections
