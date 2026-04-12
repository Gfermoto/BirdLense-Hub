"""
Regenerate ByteTrack tracks for an existing video file.
Runs YOLO+ByteTrack on each frame and returns detections with frames.
"""

import logging
import os
import time
import cv2

logger = logging.getLogger(__name__)


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

    fp, dm, _ = build_detection_stack(
        app_config,
        strategy_override=strategy_override,
        for_track_regen=for_track_regen,
        regional_species_override=regional_species_override,
        min_center_dist_override=min_center_dist_override,
        save_images=False,
        warn_two_stage_fallback=False,
    )
    return fp, dm


def process_video_for_tracks(
    video_path: str,
    lores_size=(640, 640),
    frame_processor=None,
    decision_maker=None,
    frame_step: int = 1,
    max_runtime_sec: int | None = None,
):
    """
    Run YOLO+ByteTrack on video file. Returns list of detections with frames.
    Each detection: {species_name, start_time, end_time, confidence, track_id, frames, ...}
    """
    from app_config.app_config import app_config
    from species_normalizer import normalize

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

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        logger.warning(f"Cannot open video: {video_path}")
        return []

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    frame_count = 0
    started = time.monotonic()
    try:
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
                frame_resized = cv2.resize(frame, lores_size)
                has_detections = frame_processor.run(frame_resized, frame_time=frame_time_sec)
                decision_maker.update_has_detections(has_detections)
            else:
                ret = cap.grab()
                if not ret:
                    break
            frame_count += 1
    finally:
        cap.release()

    results = decision_maker.get_results(frame_processor.tracks)
    species_mapping = app_config.get("detection.species_mapping") or {}

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
    return detections
