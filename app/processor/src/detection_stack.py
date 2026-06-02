"""
Общая сборка detection strategy + FrameProcessor + DecisionMaker (#223).

Единая точка для main.py и track_regenerator (раньше дублировалась логика).
Production: только two_stage (binary .pt + classifier .pt).
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

from shared.ctor_kwarg_guard import assert_ctor_kwargs

logger = logging.getLogger(__name__)


def _inference_device_label(binary_model: Any) -> str:
    """Best-effort device label for startup log (#371)."""
    try:
        predictor = getattr(binary_model, "predictor", None)
        args = getattr(predictor, "args", None)
        device = getattr(args, "device", None)
        if device:
            return str(device)
    except Exception:
        logger.debug("inference device via predictor.args failed", exc_info=True)
    try:
        model = getattr(binary_model, "model", None)
        dev = getattr(model, "device", None)
        if dev:
            return str(dev)
    except Exception:
        logger.debug("inference device via model.device failed", exc_info=True)
    return "unknown"


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
        openvino_expected_input_size,
        resolve_binary_detector_weight_path,
        resolve_relative_to_processor_root,
    )
    from inference.classifier_paths import (
        classifier_engine,
        classifier_weights_available,
        resolve_classifier_weight_path,
    )
    from inference.selector import (
        assert_backend_supported,
        openvino_binary_enabled,
        resolve_classifier_inference_backend,
        resolve_classifier_inference_device,
        resolve_inference_backend,
        resolve_inference_device,
    )
    from ebird_regional_confidence import (
        merge_species_confidence_overrides_with_ebird_top,
    )

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

    _requested_backend = resolve_inference_backend(app_config)
    assert_backend_supported(_requested_backend)
    _requested_classifier_backend = resolve_classifier_inference_backend(app_config)
    assert_backend_supported(_requested_classifier_backend)

    binary_path, _inf_backend = resolve_binary_detector_weight_path(app_config, processor_root)
    if _requested_backend == "openvino" and openvino_binary_enabled(app_config) and not (binary_path or "").strip():
        raise FileNotFoundError(
            "OpenVINO binary detector path missing: set processor.models.binary_openvino "
            "or environment variable BIRDLENSE_BINARY_OPENVINO_PATH "
            "(export: yolo export ... format=openvino).",
        )

    classifier_path, _cls_backend = resolve_classifier_weight_path(
        app_config,
        processor_root,
    )
    if _requested_classifier_backend == "openvino" and not (classifier_path or "").strip():
        raise FileNotFoundError(
            "OpenVINO classifier path missing: set processor.models.classifier_openvino "
            "or environment variable BIRDLENSE_CLASSIFIER_OPENVINO_PATH "
            "(export: yolo export ... format=openvino).",
        )

    if _inf_backend == "openvino":
        expected_ov_imgsz = openvino_expected_input_size(binary_path)
        configured_imgsz_values: set[int] = set()
        for key in (
            "processor.binary_imgsz",
            "processor.adaptive_profiles.night.overrides.binary_imgsz",
        ):
            raw = app_config.get(key)
            if raw is None:
                continue
            try:
                configured_imgsz_values.add(int(raw))
            except (TypeError, ValueError):
                continue
        if not configured_imgsz_values:
            try:
                from pipeline_config import resolve_binary_model_imgsz

                configured_imgsz_values.add(resolve_binary_model_imgsz(app_config))
            except (TypeError, ValueError):
                from pipeline_config import DEFAULT_MODEL_IMGSZ

                configured_imgsz_values.add(DEFAULT_MODEL_IMGSZ)

        if expected_ov_imgsz and any(v != expected_ov_imgsz for v in configured_imgsz_values):
            mismatch = ",".join(str(v) for v in sorted(configured_imgsz_values))
            mismatch_msg = (
                "OpenVINO detector input-size mismatch: model expects "
                f"{expected_ov_imgsz}, configured binary_imgsz values={mismatch}. "
                "Align processor.binary_imgsz (+ adaptive profile overrides) with model export imgsz."
            )
            can_auto_fallback = _requested_backend == "auto"
            if can_auto_fallback:
                torch_binary_path = resolve_relative_to_processor_root(
                    str(
                        app_config.get(
                            "processor.models.binary",
                            "models/detection/weights/yolo11n.pt",
                        ),
                    ).strip(),
                    processor_root,
                )
                if detector_weights_available(torch_binary_path):
                    logger.error(
                        "%s Auto fallback detector backend: openvino -> torch (%s). "
                        "Runtime uses .pt, not IR — quality/latency differ; fix binary_imgsz to %s for OpenVINO.",
                        mismatch_msg,
                        torch_binary_path,
                        expected_ov_imgsz,
                    )
                    binary_path = torch_binary_path
                    _inf_backend = "torch"
                else:
                    raise RuntimeError(mismatch_msg)
            else:
                raise RuntimeError(mismatch_msg)

    if not detector_weights_available(binary_path):
        raise FileNotFoundError(
            f"YOLO binary detector weights missing or invalid path: {binary_path}. "
            "For torch set processor.models.binary (.pt); for OpenVINO provide a complete IR "
            "bundle (.xml + matching .bin) via processor.models.binary_openvino or "
            "BIRDLENSE_BINARY_OPENVINO_PATH. Fresh clone/deploy: run `make sync-models`.",
        )
    if not classifier_weights_available(classifier_path):
        _eng = classifier_engine(app_config)
        raise FileNotFoundError(
            f"Classifier weights missing for engine={_eng!r}: {classifier_path}. "
            "Birder EU: scripts/download_birder_classifier.py + "
            "scripts/export_birder_classifier_to_openvino.py. "
            "EfficientNetB2: scripts/download_birds_classifier_efficientnetb2.py. "
            "Legacy YOLO: processor.models.classifier (.pt).",
        )

    from detector_class_map import apply_class_map_to_config

    apply_class_map_to_config(app_config, processor_root, binary_path)

    from tracking_policy import (
        attach_tracking_policy_to_strategy,
        build_unified_tracking_policy,
    )

    tracking_mode = "regen" if for_track_regen else "live"
    tracking_policy = build_unified_tracking_policy(
        app_config.config if hasattr(app_config, "config") else app_config,
        mode=tracking_mode,
        regional_species_override=regional_species_override,
        strategy_override=strategy_override,
        min_center_dist_override=min_center_dist_override,
    )
    regional_species = regional_species_override
    if regional_species is None:
        regional_species = app_config.get("processor.regional_species") or []
    if tracking_policy.regional_species_override is not None:
        regional_species = list(tracking_policy.regional_species_override)
    elif (
        for_track_regen
        and app_config.get("processor.track_regen_ignore_regional_species", True)
        and regional_species_override is None
        and not tracking_policy.unified_with_live
    ):
        regional_species = []
    detector_scope = app_config.get("processor.detector_scope")
    if detector_scope is None:
        detector_scope = ["Bird"]
    max_classifications_per_frame = app_config.get(
        "processor.max_classifications_per_frame",
        2,
    )
    max_blur_checks = app_config.get("processor.max_blur_checks", 3)
    blur_threshold = app_config.get("processor.blur_threshold", 100.0)
    min_box_size_px = app_config.get("processor.min_box_size_px", 64)
    try:
        min_box_size_px = int(min_box_size_px)
    except (TypeError, ValueError):
        min_box_size_px = 64
    if for_track_regen and not tracking_policy.unified_with_live:
        raw_mb = app_config.get("processor.track_regen_min_box_size_px")
        if raw_mb is not None:
            try:
                min_box_size_px = max(8, int(raw_mb))
            except (TypeError, ValueError):
                pass
    classification_scheduler = app_config.get(
        "processor.classification_scheduler",
        "priority",
    )

    _weight_contract = (
        str(
            app_config.get("processor.detector_weight_contract") or "warn",
        )
        .strip()
        .lower()
    )
    _binary_inference_device = resolve_inference_device(app_config)
    _classifier_inference_device = resolve_classifier_inference_device(app_config)

    def _two_stage_kwargs() -> Dict[str, Any]:
        try:
            from pipeline_config import resolve_binary_model_imgsz

            _imgsz = resolve_binary_model_imgsz(app_config)
        except (TypeError, ValueError):
            from pipeline_config import DEFAULT_MODEL_IMGSZ

            _imgsz = DEFAULT_MODEL_IMGSZ
        return {
            "binary_model_path": binary_path,
            "classifier_model_path": classifier_path,
            "regional_species": regional_species,
            "detector_scope": detector_scope,
            "min_center_dist": min_center_dist,
            "min_box_size_px": min_box_size_px,
            "blur_threshold": blur_threshold,
            "max_blur_checks": max_blur_checks,
            "max_classifications_per_frame": max_classifications_per_frame,
            "classification_scheduler": classification_scheduler,
            "binary_imgsz": _imgsz,
            "weight_contract_mode": _weight_contract,
            "inference_backend": _inf_backend,
            "classifier_inference_backend": _cls_backend,
            "binary_inference_device": _binary_inference_device,
            "classifier_inference_device": _classifier_inference_device,
            "classifier_engine": classifier_engine(app_config),
        }

    try:
        _ts_kw = _two_stage_kwargs()
        assert_ctor_kwargs(TwoStageStrategy.__init__, _ts_kw, label="TwoStageStrategy")
        detection_strategy = TwoStageStrategy(**_ts_kw)
    except Exception:
        can_fallback_detector = _requested_backend == "auto" and _inf_backend == "openvino"
        can_fallback_classifier = _requested_classifier_backend == "auto" and _cls_backend == "openvino"
        if not (can_fallback_detector or can_fallback_classifier):
            raise

        if can_fallback_detector:
            torch_binary_path = resolve_relative_to_processor_root(
                str(
                    app_config.get(
                        "processor.models.binary",
                        "models/detection/weights/yolo11n.pt",
                    ),
                ).strip(),
                processor_root,
            )
            if not detector_weights_available(torch_binary_path):
                raise
            binary_path = torch_binary_path
            _inf_backend = "torch"
        if can_fallback_classifier:
            classifier_engine(app_config)
            torch_classifier_path, _ = resolve_classifier_weight_path(app_config, processor_root)
            if not classifier_weights_available(torch_classifier_path):
                raise
            classifier_path = torch_classifier_path
            _cls_backend = "torch"
        logger.exception(
            "Inference auto backend fallback: detector=(%s,%s)->%s classifier=(%s,%s)->%s",
            binary_path,
            _requested_backend,
            _inf_backend,
            classifier_path,
            _requested_classifier_backend,
            _cls_backend,
        )
        _ts_kw_fb = _two_stage_kwargs()
        assert_ctor_kwargs(TwoStageStrategy.__init__, _ts_kw_fb, label="TwoStageStrategy(fallback)")
        detection_strategy = TwoStageStrategy(**_ts_kw_fb)
    logger.info(
        "Inference startup: detector_backend=%s classifier_backend=%s ultralytics_device_label=%s "
        "binary_inference_device_kw=%s classifier_inference_device_kw=%s binary_path=%s classifier_path=%s "
        "binary_imgsz=%s",
        _inf_backend,
        _cls_backend,
        _inference_device_label(detection_strategy.binary_model),
        _binary_inference_device or "(default)",
        _classifier_inference_device or "(default)",
        binary_path,
        classifier_path,
        getattr(detection_strategy, "binary_imgsz", None),
    )
    if _requested_backend == "auto":
        logger.info("Inference backend auto resolved to %s", _inf_backend)

    extra_cache: Optional[Dict[str, Any]] = None
    raw_auto = (os.environ.get("BIRDLENSE_INFERENCE_AUTO_BENCHMARK") or "").strip().lower()
    if raw_auto in ("1", "true", "yes", "on"):
        from inference.auto_benchmark import measure_binary_detector_predict_ms

        from pipeline_config import resolve_binary_model_imgsz

        try:
            _isz = resolve_binary_model_imgsz(app_config)
        except (TypeError, ValueError):
            from pipeline_config import DEFAULT_MODEL_IMGSZ

            _isz = DEFAULT_MODEL_IMGSZ
        _ms = measure_binary_detector_predict_ms(
            detection_strategy.binary_model,
            imgsz=max(320, _isz),
            device=_binary_inference_device,
        )
        if _ms is not None:
            extra_cache = {"cold_start_predict_ms": round(float(_ms), 3)}

    write_inference_backend_cache(
        processor_root,
        backend=_inf_backend,
        binary_model_path=binary_path,
        classifier_backend=_cls_backend,
        classifier_model_path=classifier_path,
        extra=extra_cache,
    )

    tracker = app_config.get("processor.tracker") or "bytetrack.yaml"
    _fp_kw = {
        "detection_strategy": detection_strategy,
        "tracker": tracker,
        "save_images": save_images,
    }
    assert_ctor_kwargs(FrameProcessor.__init__, _fp_kw, label="FrameProcessor")
    frame_processor = FrameProcessor(**_fp_kw)
    frame_processor.tracking_policy = tracking_policy
    attach_tracking_policy_to_strategy(frame_processor.strategy, tracking_policy)
    policy_snapshot = dict(tracking_policy.pipeline_policy)
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
    min_track_duration_val = float(tracking_policy.min_track_duration)
    min_conf_proc_val = tracking_policy.min_confidence_to_process
    dm_detector_store_val = (
        float(tracking_policy.min_confidence_to_store)
        if tracking_policy.min_confidence_to_store is not None
        else min_confidence_to_store
    )
    if for_track_regen and not tracking_policy.unified_with_live:
        logger.info(
            "track_regen DecisionMaker thresholds (legacy regen policy): min_track_duration=%s "
            "min_confidence_to_process=%s detector_store_floor=%s unified_with_live=false",
            min_track_duration_val,
            min_conf_proc_val,
            dm_detector_store_val,
        )
    elif for_track_regen:
        logger.info(
            "track_regen DecisionMaker thresholds (unified with live): min_track_duration=%s "
            "min_confidence_to_process=%s detector_store_floor=%s",
            min_track_duration_val,
            min_conf_proc_val,
            dm_detector_store_val,
        )

    _dm_kw = {
        "max_record_seconds": max_record_seconds,
        "max_inactive_seconds": max_inactive_seconds,
        "min_track_duration": min_track_duration_val,
        "min_confidence_to_process": min_conf_proc_val,
        "species_confidence_overrides": merged_overrides,
        "post_record_seconds": app_config.get("processor.post_record_seconds", 0),
        "min_confidence_to_store": dm_detector_store_val,
        "classifier_fallback_bird": fallback_bird,
        "generic_bird_min_detector_conf": app_config.get("processor.generic_bird_min_detector_conf"),
        "generic_bird_min_frames": app_config.get("processor.generic_bird_min_frames", 3),
        "generic_bird_min_area_frac": app_config.get("processor.generic_bird_min_area_frac", 0.01),
        "generic_bird_min_best_frame_score": app_config.get("processor.generic_bird_min_best_frame_score", 6.5),
        "generic_rodent_min_frames": app_config.get("processor.generic_rodent_min_frames", 1),
        "generic_rodent_max_area_frac": app_config.get("processor.generic_rodent_max_area_frac", 1.0),
        "generic_rodent_min_best_frame_score": app_config.get("processor.generic_rodent_min_best_frame_score", 0.0),
    }
    assert_ctor_kwargs(DecisionMaker.__init__, _dm_kw, label="DecisionMaker")
    decision_maker = DecisionMaker(**_dm_kw)
    decision_maker.pipeline_policy = dict(policy_snapshot)
    return frame_processor, decision_maker, merged_overrides
