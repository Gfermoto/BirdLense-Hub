"""Снимок конфига детекции и путей к весам/allowlist (#265)."""
from __future__ import annotations

import os

from app_config.app_config import app_config

from services.artifact_paths_service import (
    config_fingerprint,
    resolve_artifact_path,
    sha256_file,
)


def current_model_lineage_snapshot() -> dict:
    relevant_config = {
        'detection': {
            'strategy': app_config.get('processor.detection_strategy'),
            'use_learned_fusion': bool(app_config.get('detection.use_learned_fusion') or False),
            'fusion_alpha': app_config.get('detection.fusion_alpha'),
            'cross_source_confidence_bonus': app_config.get(
                'detection.cross_source_confidence_bonus',
            ),
            'min_confidence_to_store': app_config.get('detection.min_confidence_to_store'),
        },
        'processor': {
            'min_confidence_to_process': app_config.get('processor.min_confidence_to_process'),
            'min_confidence_to_notify': app_config.get('processor.min_confidence_to_notify'),
            'min_track_duration': app_config.get('processor.min_track_duration'),
            'classification_scheduler': app_config.get('processor.classification_scheduler'),
            'species_confidence_overrides': app_config.get(
                'processor.species_confidence_overrides',
            ) or {},
        },
        'ebird': {
            'enabled_region': app_config.get('ebird.region_code'),
        },
    }
    artifacts = {
        'detector': resolve_artifact_path(
            app_config.get('processor.detector_model_path')
            or app_config.get('detection.detector_model_path')
            or 'app/yolo11n.pt'
        ),
        'classifier': resolve_artifact_path(
            app_config.get('processor.classifier_model_path')
            or app_config.get('classification.model_path')
        ),
        'fusion': resolve_artifact_path(app_config.get('detection.fusion_model_path')),
        'allowlist': resolve_artifact_path(
            app_config.get('species.catalog_allowlist_file')
            or app_config.get('species.allowlist_file')
        ),
    }
    resolved = {}
    for name, path in artifacts.items():
        resolved[name] = {
            'configured_path': path,
            'exists': bool(path and os.path.exists(path)),
            'sha256': sha256_file(path),
        }
    return {
        'config_fingerprint': config_fingerprint(relevant_config),
        'artifacts': resolved,
        'relevant_config': relevant_config,
    }
