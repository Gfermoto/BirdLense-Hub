"""
Общая сборка detection strategy + FrameProcessor + DecisionMaker (#223).

Единая точка для main.py и track_regenerator (раньше дублировалась логика).
Production: только two_stage (binary .pt + classifier .pt).
"""
from __future__ import annotations

import logging
import os
from typing import List, Optional

logger = logging.getLogger(__name__)


def _resolve_model_path(rel_or_abs: str, processor_root: str) -> str:
    if os.path.isabs(rel_or_abs):
        return rel_or_abs
    return os.path.join(processor_root, rel_or_abs)


def build_detection_stack(
    app_config,
    *,
    strategy_override: Optional[str] = None,
    for_track_regen: bool = False,
    regional_species_override: Optional[List[str]] = None,
    min_center_dist_override: Optional[float] = None,
    save_images: bool = False,
    warn_two_stage_fallback: bool = False,
):
    """Собрать ``FrameProcessor`` и ``DecisionMaker`` по конфигу процессора."""
    from detection_strategy import TwoStageStrategy
    from frame_processor import FrameProcessor
    from decision_maker import DecisionMaker
    from ebird_regional_confidence import (
        merge_species_confidence_overrides_with_ebird_top,
    )

    _ = warn_two_stage_fallback  # legacy param, no longer used

    processor_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    strategy_type = (strategy_override or app_config.get(
        'processor.detection_strategy',
        'two_stage',
    )).strip()
    if strategy_type != 'two_stage':
        logger.warning(
            'processor.detection_strategy=%s is ignored; only two_stage is supported. '
            'Remove single_stage from user_config.',
            strategy_type,
        )
    min_center_dist = (
        float(min_center_dist_override)
        if min_center_dist_override is not None
        else 0.1
    )
    binary_path = _resolve_model_path(
        app_config.get(
            'processor.models.binary', 'models/detection/weights/best.pt'),
        processor_root,
    )
    classifier_path = _resolve_model_path(
        app_config.get(
            'processor.models.classifier',
            'models/classification/weights/best.pt',
        ),
        processor_root,
    )

    if not os.path.isfile(binary_path):
        raise FileNotFoundError(
            f'YOLO binary detector weights missing: {binary_path}. '
            'Set processor.models.binary or run scripts/fetch-processor-weights.sh',
        )
    if not os.path.isfile(classifier_path):
        raise FileNotFoundError(
            f'YOLO classifier weights missing: {classifier_path}. '
            'Set processor.models.classifier or run scripts/fetch-processor-weights.sh',
        )

    regional_species = regional_species_override
    if regional_species is None:
        regional_species = app_config.get('processor.regional_species') or []
    if for_track_regen and app_config.get(
        'processor.track_regen_ignore_regional_species',
        True,
    ) and regional_species_override is None:
        regional_species = []
    detector_scope = app_config.get('processor.detector_scope') or ['Bird', 'Squirrel']
    max_classifications_per_frame = app_config.get(
        'processor.max_classifications_per_frame', 2,
    )
    max_blur_checks = app_config.get('processor.max_blur_checks', 3)
    blur_threshold = app_config.get('processor.blur_threshold', 100.0)
    min_box_size_px = app_config.get('processor.min_box_size_px', 64)
    classification_scheduler = app_config.get(
        'processor.classification_scheduler', 'priority',
    )

    detection_strategy = TwoStageStrategy(
        binary_model_path=binary_path,
        classifier_model_path=classifier_path,
        regional_species=regional_species,
        detector_scope=detector_scope,
        min_center_dist=min_center_dist,
        min_box_size_px=min_box_size_px,
        blur_threshold=blur_threshold,
        max_blur_checks=max_blur_checks,
        max_classifications_per_frame=max_classifications_per_frame,
        classification_scheduler=classification_scheduler,
    )

    tracker = app_config.get('processor.tracker') or 'bytetrack.yaml'
    frame_processor = FrameProcessor(
        detection_strategy=detection_strategy,
        tracker=tracker,
        save_images=save_images,
    )
    merged_overrides = merge_species_confidence_overrides_with_ebird_top(
        app_config)
    min_store = app_config.get('detection.min_confidence_to_store')
    try:
        min_confidence_to_store = float(min_store) if min_store is not None else 0.30
    except (TypeError, ValueError):
        min_confidence_to_store = 0.30
    fallback_bird = bool(
        app_config.get('processor.classifier_fallback_bird', True),
    )
    decision_maker = DecisionMaker(
        max_record_seconds=app_config.get('processor.max_record_seconds'),
        max_inactive_seconds=app_config.get('processor.max_inactive_seconds'),
        min_track_duration=app_config.get('processor.min_track_duration', 1.0),
        min_confidence_to_process=app_config.get(
            'processor.min_confidence_to_process'),
        species_confidence_overrides=merged_overrides,
        post_record_seconds=app_config.get('processor.post_record_seconds', 0),
        min_confidence_to_store=min_confidence_to_store,
        classifier_fallback_bird=fallback_bird,
    )
    return frame_processor, decision_maker, merged_overrides
