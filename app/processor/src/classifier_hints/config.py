"""Default hint weights (tier: advanced via detection.weighted_arbiter_* keys)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class HintWeights:
    base_confidence: float = 0.55
    detector_confidence: float = 0.15
    classifier_confidence: float = 0.12
    birdnet_prior: float = 0.08
    regional_prior: float = 0.05
    multicam_support: float = 0.05
    frigate_label: float = 0.06

    birdnet_max_delta: float = 0.15
    regional_max_delta: float = 0.10
    frigate_max_delta: float = 0.12
    multicam_max_delta: float = 0.10


def _cfg_float(app_config, key: str, default: float) -> float:
    try:
        return float(app_config.get(key))
    except (TypeError, ValueError):
        return default


def load_hint_weights(app_config) -> HintWeights:
    return HintWeights(
        base_confidence=_cfg_float(app_config, "detection.weighted_arbiter_conf_weight", 0.55),
        detector_confidence=_cfg_float(app_config, "detection.weighted_arbiter_detector_weight", 0.15),
        classifier_confidence=_cfg_float(app_config, "detection.weighted_arbiter_classifier_weight", 0.12),
        birdnet_prior=_cfg_float(app_config, "detection.weighted_arbiter_birdnet_weight", 0.08),
        regional_prior=_cfg_float(app_config, "detection.weighted_arbiter_regional_weight", 0.05),
        multicam_support=_cfg_float(app_config, "detection.weighted_arbiter_multicamera_weight", 0.05),
        frigate_label=_cfg_float(app_config, "detection.weighted_arbiter_frigate_weight", 0.06),
        birdnet_max_delta=_cfg_float(app_config, "detection.hint_birdnet_max_delta", 0.15),
        regional_max_delta=_cfg_float(app_config, "detection.hint_regional_max_delta", 0.10),
        frigate_max_delta=_cfg_float(app_config, "detection.hint_frigate_max_delta", 0.12),
        multicam_max_delta=_cfg_float(app_config, "detection.hint_multicam_max_delta", 0.10),
    )


def hints_enabled(app_config) -> bool:
    raw = app_config.get("detection.classifier_hints_enabled")
    if raw is None:
        return bool(app_config.get("detection.weighted_arbiter_enabled", True))
    return bool(raw)
