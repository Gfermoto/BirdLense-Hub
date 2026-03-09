"""
Regenerate ByteTrack tracks for an existing video file.
Runs YOLO+ByteTrack on each frame and returns detections with frames.
"""
import logging
import os
import cv2

logger = logging.getLogger(__name__)


def _build_detection_pipeline(app_config):
    """Build detection_strategy, frame_processor, decision_maker from config."""
    from detection_strategy import SingleStageStrategy, TwoStageStrategy
    from frame_processor import FrameProcessor
    from decision_maker import DecisionMaker

    processor_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    strategy_type = app_config.get('processor.detection_strategy', 'single_stage')
    binary_path = app_config.get('processor.models.binary', 'models/detection/weights/best.pt')
    classifier_path = app_config.get('processor.models.classifier', 'models/classification/weights/best.pt')
    if not os.path.isabs(binary_path):
        binary_path = os.path.join(processor_root, binary_path)
    if not os.path.isabs(classifier_path):
        classifier_path = os.path.join(processor_root, classifier_path)

    regional_species = app_config.get('processor.regional_species') or []

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
        detection_strategy = SingleStageStrategy(
            model_path=single_path,
            regional_species=regional_species,
        )

    tracker = app_config.get('processor.tracker') or 'bytetrack.yaml'
    frame_processor = FrameProcessor(
        detection_strategy=detection_strategy,
        tracker=tracker,
        save_images=False,
    )
    decision_maker = DecisionMaker(
        max_record_seconds=app_config.get('processor.max_record_seconds'),
        max_inactive_seconds=app_config.get('processor.max_inactive_seconds'),
        min_track_duration=app_config.get('processor.min_track_duration', 1),
    )
    return frame_processor, decision_maker


def process_video_for_tracks(video_path: str, lores_size=(640, 640)):
    """
    Run YOLO+ByteTrack on video file. Returns list of detections with frames.
    Each detection: {species_name, start_time, end_time, confidence, track_id, frames, ...}
    """
    from app_config.app_config import app_config

    if not os.path.isfile(video_path):
        logger.warning(f"Video not found: {video_path}")
        return []

    frame_processor, decision_maker = _build_detection_pipeline(app_config)
    frame_processor.reset()
    decision_maker.reset()

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        logger.warning(f"Cannot open video: {video_path}")
        return []

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    frame_count = 0
    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            frame_time_sec = frame_count / fps
            frame_resized = cv2.resize(frame, lores_size)
            has_detections = frame_processor.run(frame_resized, frame_time=frame_time_sec)
            decision_maker.update_has_detections(has_detections)
            frame_count += 1
    finally:
        cap.release()

    results = decision_maker.get_results(frame_processor.tracks)
    detections = []
    for r in results:
        detections.append({
            'species_name': r['species_name'],
            'start_time': r['start_time'],
            'end_time': r['end_time'],
            'confidence': r['confidence'],
            'track_id': r['track_id'],
            'frames': r.get('frames', []),
            'source': 'video',
            'detection_provider': 'yolo',
        })
    logger.info(f"Track regen: {video_path} -> {len(detections)} detections, {frame_count} frames")
    return detections
