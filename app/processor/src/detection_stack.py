"""
Общая сборка detection strategy + FrameProcessor + DecisionMaker (#223).

Единая точка для main.py и track_regenerator (раньше дублировалась логика).
Production: только two_stage (binary .pt + classifier .pt).
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


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
    from inference.backend_cache import write_inference_backend_cache
    from inference.binary_paths import (
        detector_weights_available,
        resolve_binary_detector_weight_path,
        resolve_relative_to_processor_root,
    )
    from inference.selector import assert_backend_supported, resolve_inference_backend
    from ebird_regional_confidence import (
        merge_species_confidence_overrides_with_ebird_top,
    )
    from pipeline_policy import build_pipeline_policy_snapshot

    _ = warn_two_stage_fallback  # legacy param, no longer used

    processor_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    strategy_type = (
        strategy_override
        or app_config.get(
            "processor.detection_strategy",
            "two_stage",
        )
    ).strip()
    if strategy_type != "two_stage":
        logger.warning(
            "processor.detection_strategy=%s is ignored; only two_stage is supported. "
            "Remove single_stage from user_config.",
            strategy_type,
        )
    min_center_dist = (
        float(min_center_dist_override)
        if min_center_dist_override is not None
        else float(app_config.get("processor.min_center_dist", 0.1))
    )

    _inf_backend = resolve_inference_backend(app_config)
    assert_backend_supported(_inf_backend)

    binary_path, _ = resolve_binary_detector_weight_path(app_config, processor_root)
    if _inf_backend == "openvino" and not (binary_path or "").strip():
        raise FileNotFoundError(
            "OpenVINO binary detector path missing: set processor.models.binary_openvino "
            "or environment variable BIRDLENSE_BINARY_OPENVINO_PATH "
            "(export: yolo export ... format=openvino).",
        )

    classifier_path = resolve_relative_to_processor_root(
        app_config.get(
            "processor.models.classifier",
            "models/classification/weights/best.pt",
        ),
        processor_root,
    )

    if not detector_weights_available(binary_path):
        raise FileNotFoundError(
            f"YOLO binary detector weights missing or invalid path: {binary_path}. "
            "For torch set processor.models.binary (.pt); for OpenVINO use a directory or .xml "
            "from yolo export format=openvino (processor.models.binary_openvino or "
            "BIRDLENSE_BINARY_OPENVINO_PATH).",
        )
    if not os.path.isfile(classifier_path):
        raise FileNotFoundError(
            f"YOLO classifier weights missing: {classifier_path}. "
            "Set processor.models.classifier or run scripts/fetch-processor-weights.sh",
        )

    regional_species = regional_species_override
    if regional_species is None:
        regional_species = app_config.get("processor.regional_species") or []
    match_live_regen = bool(
        app_config.get("processor.track_regen_match_live_pipeline", False),
    )
    if (
        for_track_regen
        and app_config.get("processor.track_regen_ignore_regional_species", True)
        and regional_species_override is None
        and not match_live_regen
    ):
        regional_species = []
    detector_scope = app_config.get("processor.detector_scope") or ["Bird", "Rodent"]
    max_classifications_per_frame = app_config.get(
        "processor.max_classifications_per_frame",
        2,
    )
    max_blur_checks = app_config.get("processor.max_blur_checks", 3)
    blur_threshold = app_config.get("processor.blur_threshold", 100.0)
    min_box_size_px = app_config.get("processor.min_box_size_px", 64)
    classification_scheduler = app_config.get(
        "processor.classification_scheduler",
        "priority",
    )

    _weight_contract = str(
        app_config.get("processor.detector_weight_contract") or "warn",
    ).strip().lower()

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
        binary_imgsz=app_config.get("processor.binary_imgsz", 320),
        weight_contract_mode=_weight_contract,
        inference_backend=_inf_backend,
    )

    extra_cache: Optional[Dict[str, Any]] = None
    raw_auto = (os.environ.get("BIRDLENSE_INFERENCE_AUTO_BENCHMARK") or "").strip().lower()
    if raw_auto in ("1", "true", "yes", "on"):
        from inference.auto_benchmark import measure_binary_detector_predict_ms

        try:
            _isz = int(app_config.get("processor.binary_imgsz", 320) or 320)
        except (TypeError, ValueError):
            _isz = 320
        _ms = measure_binary_detector_predict_ms(
            detection_strategy.binary_model,
            imgsz=max(320, _isz),
        )
        if _ms is not None:
            extra_cache = {"cold_start_predict_ms": round(float(_ms), 3)}

    write_inference_backend_cache(
        processor_root,
        backend=_inf_backend,
        binary_model_path=binary_path,
        extra=extra_cache,
    )

    tracker = app_config.get("processor.tracker") or "bytetrack.yaml"
    frame_processor = FrameProcessor(
        detection_strategy=detection_strategy,
        tracker=tracker,
        save_images=save_images,
    )
    policy_snapshot = build_pipeline_policy_snapshot(
        app_config,
        for_track_regen=for_track_regen,
        strategy_override=strategy_override,
        regional_species_override=regional_species_override,
        min_center_dist_override=min_center_dist_override,
    )
    frame_processor.pipeline_policy = dict(policy_snapshot)
    merged_overrides = merge_species_confidence_overrides_with_ebird_top(app_config)
    min_store = app_config.get("detection.min_confidence_to_store")
    try:
        min_confidence_to_store = float(min_store) if min_store is not None else 0.30
    except (TypeError, ValueError):
        min_confidence_to_store = 0.30
    fallback_bird = bool(
        app_config.get("processor.classifier_fallback_bird", True),
    )
    # Live camera: short max_record_seconds saves disk. File/playlist: merge uses camera defaults (60s)
    # if we don't raise the floor, but a 7200s floor meant no finalize for hours while YOLO stays active —
    # empty UI. Floor is configurable (processor.file_max_record_floor_seconds); playlist position is kept
    # when segments end (media_runtime advance_on_start=False + VideoPlaylistSource.start_recording).
    max_record_seconds = app_config.get("processor.max_record_seconds")
    max_inactive_seconds = app_config.get("processor.max_inactive_seconds")
    if (app_config.get("video.source") or "").strip().lower() == "file":
        try:
            mrs = float(max_record_seconds) if max_record_seconds is not None else 60.0
        except (TypeError, ValueError):
            mrs = 60.0
        try:
            floor = float(
                app_config.get("processor.file_max_record_floor_seconds", 86400.0),
            )
        except (TypeError, ValueError):
            floor = 86400.0
        max_record_seconds = max(mrs, max(60.0, floor))
        try:
            mis = float(max_inactive_seconds) if max_inactive_seconds is not None else 10.0
        except (TypeError, ValueError):
            mis = 10.0
        max_inactive_seconds = max(mis, 120.0)
        logger.info(
            "video.source=file: session limits (wall clock) — max_record_seconds=%s, max_inactive_seconds=%s",
            max_record_seconds,
            max_inactive_seconds,
        )
    decision_maker = DecisionMaker(
        max_record_seconds=max_record_seconds,
        max_inactive_seconds=max_inactive_seconds,
        min_track_duration=app_config.get("processor.min_track_duration", 1.0),
        min_confidence_to_process=app_config.get("processor.min_confidence_to_process"),
        species_confidence_overrides=merged_overrides,
        post_record_seconds=app_config.get("processor.post_record_seconds", 0),
        min_confidence_to_store=min_confidence_to_store,
        classifier_fallback_bird=fallback_bird,
        generic_bird_min_detector_conf=app_config.get("processor.generic_bird_min_detector_conf"),
        generic_bird_min_frames=app_config.get("processor.generic_bird_min_frames", 3),
        generic_bird_min_area_frac=app_config.get("processor.generic_bird_min_area_frac", 0.01),
        generic_bird_min_best_frame_score=app_config.get("processor.generic_bird_min_best_frame_score", 6.5),
    )
    decision_maker.pipeline_policy = dict(policy_snapshot)
    return frame_processor, decision_maker, merged_overrides
