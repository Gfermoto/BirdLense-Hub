"""
Общая сборка detection strategy + FrameProcessor + DecisionMaker (#223).

Единая точка для main.py и track_regenerator (раньше дублировалась логика).
"""
from __future__ import annotations

import logging
import os
from typing import List, Optional

logger = logging.getLogger(__name__)


def resolve_single_stage_model_path(config, processor_root: str) -> str:
    """Путь к single-stage модели из конфига или fallback ``yolov8n.pt``."""
    single_path = config.get('processor.models.single_stage', 'yolov8n.pt')
    if not os.path.isabs(single_path):
        single_path = os.path.join(processor_root, single_path)
    if os.path.isfile(single_path) or os.path.isdir(single_path):
        return single_path
    return 'yolov8n.pt'


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
    min_center_dist = (
        float(min_center_dist_override)
        if min_center_dist_override is not None
        else 0.1
    )
    binary_path = app_config.get(
        'processor.models.binary', 'models/detection/weights/best.pt')
    classifier_path = app_config.get(
        'processor.models.classifier', 'models/classification/weights/best.pt')
    if not os.path.isabs(binary_path):
        binary_path = os.path.join(processor_root, binary_path)
    if not os.path.isabs(classifier_path):
        classifier_path = os.path.join(processor_root, classifier_path)

    regional_species = regional_species_override
    if regional_species is None:
        regional_species = app_config.get('processor.regional_species') or []
    if for_track_regen and app_config.get(
        'processor.track_regen_ignore_regional_species',
        True,
    ) and regional_species_override is None:
        regional_species = []

    if (
        strategy_type == 'two_stage'
        and os.path.isfile(binary_path)
        and os.path.isfile(classifier_path)
    ):
        detection_strategy = TwoStageStrategy(
            binary_model_path=binary_path,
            classifier_model_path=classifier_path,
            regional_species=regional_species,
            min_center_dist=min_center_dist,
        )
    else:
        if warn_two_stage_fallback and strategy_type == 'two_stage':
            logger.warning(
                'YOLO two_stage: модели не найдены (%s, %s). '
                'Используем single_stage с yolov8n.pt. Добавьте best.pt в '
                'processor/models/ для полной детекции.',
                binary_path,
                classifier_path,
            )
        single_path = resolve_single_stage_model_path(
            app_config, processor_root)
        _coco_anim = app_config.get(
            'processor.single_stage_coco_animals_only_auto')
        if _coco_anim is None:
            _coco_anim = app_config.get(
                'processor.single_stage_coco_bird_only_auto', True)
        detection_strategy = SingleStageStrategy(
            model_path=single_path,
            regional_species=regional_species,
            min_center_dist=min_center_dist,
            coco_animals_only_auto=bool(_coco_anim),
        )

    tracker = app_config.get('processor.tracker') or 'bytetrack.yaml'
    frame_processor = FrameProcessor(
        detection_strategy=detection_strategy,
        tracker=tracker,
        save_images=save_images,
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
    return frame_processor, decision_maker, merged_overrides
