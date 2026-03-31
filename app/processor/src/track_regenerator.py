"""
Regenerate ByteTrack tracks for an existing video file.
Runs YOLO+ByteTrack on each frame and returns detections with frames.
"""
import logging
import os
import time
import cv2

logger = logging.getLogger(__name__)


def build_detection_pipeline(
    app_config,
    strategy_override: str | None = None,
    for_track_regen: bool = False,
):
    """Build detection_strategy, frame_processor, decision_maker from config."""
    from detection_strategy import SingleStageStrategy, TwoStageStrategy
    from frame_processor import FrameProcessor
    from decision_maker import DecisionMaker
    from ebird_regional_confidence import (
        merge_species_confidence_overrides_with_ebird_top,
    )

    processor_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    strategy_type = (strategy_override or app_config.get(
        'processor.detection_strategy',
        'single_stage',
    )).strip()
    binary_path = app_config.get('processor.models.binary', 'models/detection/weights/best.pt')
    classifier_path = app_config.get('processor.models.classifier', 'models/classification/weights/best.pt')
    if not os.path.isabs(binary_path):
        binary_path = os.path.join(processor_root, binary_path)
    if not os.path.isabs(classifier_path):
        classifier_path = os.path.join(processor_root, classifier_path)

    regional_species = app_config.get('processor.regional_species') or []
    if for_track_regen and app_config.get(
        'processor.track_regen_ignore_regional_species',
        True,
    ):
        # Иначе узкий regional_species (напр. US eBird) отрезает EU-виды и Rodent.
        regional_species = []

    if strategy_type == 'two_stage' and os.path.isfile(binary_path) and os.path.isfile(classifier_path):
        detection_strategy = TwoStageStrategy(
            binary_model_path=binary_path,
            classifier_model_path=classifier_path,
            regional_species=regional_species,
        )
    else:
        single_path = app_config.get('processor.models.single_stage', 'yolov8n.pt')
        if not os.path.isabs(single_path):
            single_path = os.path.join(processor_root, single_path)
        if not os.path.isfile(single_path):
            single_path = 'yolov8n.pt'
        _coco_anim = app_config.get('processor.single_stage_coco_animals_only_auto')
        if _coco_anim is None:
            _coco_anim = app_config.get('processor.single_stage_coco_bird_only_auto', True)
        detection_strategy = SingleStageStrategy(
            model_path=single_path,
            regional_species=regional_species,
            coco_animals_only_auto=bool(_coco_anim),
        )

    tracker = app_config.get('processor.tracker') or 'bytetrack.yaml'
    frame_processor = FrameProcessor(
        detection_strategy=detection_strategy,
        tracker=tracker,
        save_images=False,
    )
    merged_overrides = merge_species_confidence_overrides_with_ebird_top(
        app_config)
    decision_maker = DecisionMaker(
        max_record_seconds=app_config.get('processor.max_record_seconds'),
        max_inactive_seconds=app_config.get('processor.max_inactive_seconds'),
        min_track_duration=app_config.get('processor.min_track_duration', 1),
        min_confidence_to_process=app_config.get(
            'processor.min_confidence_to_process'),
        species_confidence_overrides=merged_overrides,
        post_record_seconds=app_config.get('processor.post_record_seconds', 0),
    )
    return frame_processor, decision_maker


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
                raise TimeoutError(
                    f'Track regeneration timeout ({max_runtime_sec}s) for {video_path}'
                )
            # Только decode+retrieve на обрабатываемых кадрах; между ними — grab()
            # без полного декодирования (иначе frame_step почти не ускоряет батч).
            if frame_count % frame_step == 0:
                ret, frame = cap.read()
                if not ret:
                    break
                frame_time_sec = frame_count / fps
                frame_resized = cv2.resize(frame, lores_size)
                has_detections = frame_processor.run(
                    frame_resized, frame_time=frame_time_sec
                )
                decision_maker.update_has_detections(has_detections)
            else:
                ret = cap.grab()
                if not ret:
                    break
            frame_count += 1
    finally:
        cap.release()

    results = decision_maker.get_results(frame_processor.tracks)
    species_mapping = app_config.get('detection.species_mapping') or {}

    detections = []
    for r in results:
        raw_name = r.get('species_name') or ''
        species_name = (
            normalize(raw_name, species_mapping) if raw_name else raw_name
        )
        detections.append({
            'species_name': species_name,
            'start_time': r['start_time'],
            'end_time': r['end_time'],
            'confidence': r['confidence'],
            'track_id': r['track_id'],
            'frames': r.get('frames', []),
            'source': 'video',
            'detection_provider': 'yolo',
        })
    logger.info(
        "Track regen: %s -> %s detections, %s frames, frame_step=%s",
        video_path,
        len(detections),
        frame_count,
        frame_step,
    )
    return detections
