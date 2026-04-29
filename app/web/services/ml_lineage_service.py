"""Снимок конфига детекции и путей к весам/allowlist (#265)."""

from __future__ import annotations

import os

from app_config.app_config import app_config

from inference.binary_paths import (
    openvino_bundle_fingerprint,
    resolve_binary_detector_weight_path,
)
from inference.selector import resolve_inference_backend

from services.artifact_paths_service import (
    config_fingerprint,
    repo_root_path,
    resolve_artifact_path,
    sha256_file,
)


def current_model_lineage_snapshot() -> dict:
    relevant_config = {
        "detection": {
            "strategy": app_config.get("processor.detection_strategy"),
            "use_learned_fusion": bool(app_config.get("detection.use_learned_fusion") or False),
            "fusion_alpha": app_config.get("detection.fusion_alpha"),
            "cross_source_confidence_bonus": app_config.get(
                "detection.cross_source_confidence_bonus",
            ),
            "min_confidence_to_store": app_config.get("detection.min_confidence_to_store"),
        },
        "processor": {
            "inference_backend": app_config.get("processor.inference_backend"),
            "models_binary_openvino": app_config.get("processor.models.binary_openvino"),
            "min_confidence_to_process": app_config.get("processor.min_confidence_to_process"),
            "min_confidence_to_notify": app_config.get("processor.min_confidence_to_notify"),
            "min_track_duration": app_config.get("processor.min_track_duration"),
            "classification_scheduler": app_config.get("processor.classification_scheduler"),
            "species_confidence_overrides": app_config.get(
                "processor.species_confidence_overrides",
            )
            or {},
        },
        "ebird": {
            "enabled_region": app_config.get("ebird.region_code"),
        },
    }
    processor_root = os.path.join(repo_root_path(), "app", "processor")
    backend = resolve_inference_backend(app_config)
    if backend in ("openvino", "auto"):
        det_path, resolved_backend = resolve_binary_detector_weight_path(app_config, processor_root)
    else:
        resolved_backend = "torch"
        binary_rel = (
            app_config.get("processor.models.binary")
            or app_config.get("processor.detector_model_path")
            or app_config.get("detection.detector_model_path")
            or "models/detection/weights/best.pt"
        )
        det_path = resolve_artifact_path(binary_rel)
    classifier_rel = (
        app_config.get("processor.models.classifier")
        or app_config.get("processor.classifier_model_path")
        or app_config.get("classification.model_path")
        or "models/classification/weights/best.pt"
    )
    artifacts = {
        "detector": det_path,
        "classifier": resolve_artifact_path(classifier_rel),
        "fusion": resolve_artifact_path(app_config.get("detection.fusion_model_path")),
        "allowlist": resolve_artifact_path(
            app_config.get("species.catalog_allowlist_file") or app_config.get("species.allowlist_file")
        ),
    }
    resolved = {}
    for name, path in artifacts.items():
        digest = None
        if name == "detector" and resolved_backend == "openvino":
            digest = openvino_bundle_fingerprint(path)
        else:
            digest = sha256_file(path)
        resolved[name] = {
            "configured_path": path,
            "exists": bool(path and os.path.exists(path)),
            "sha256": digest,
            **({"detector_backend": resolved_backend} if name == "detector" else {}),
        }
    return {
        "config_fingerprint": config_fingerprint(relevant_config),
        "artifacts": resolved,
        "relevant_config": relevant_config,
    }
