"""Explicit detection policy snapshots for live and regenerate-tracks."""

from __future__ import annotations

from pipeline_config import resolve_binary_model_imgsz


def build_pipeline_policy_snapshot(
    app_config,
    *,
    for_track_regen: bool = False,
    strategy_override: str | None = None,
    regional_species_override: list[str] | None = None,
    min_center_dist_override: float | None = None,
) -> dict:
    strategy_type = strategy_override or app_config.get("processor.detection_strategy", "two_stage") or "two_stage"
    regional_species = regional_species_override
    if regional_species is None:
        regional_species = list(app_config.get("processor.regional_species") or [])
    from tracking_policy import unified_with_live_pipeline

    match_live_regen = unified_with_live_pipeline(app_config.config if hasattr(app_config, "config") else app_config)
    ignore_regional = bool(
        app_config.get("processor.track_regen_ignore_regional_species", True),
    )
    scope_mode = "config_regional_species"
    if for_track_regen and match_live_regen:
        scope_mode = "match_live_pipeline"
    elif regional_species_override is not None:
        scope_mode = "explicit_regional_override"
    elif for_track_regen and ignore_regional:
        scope_mode = "global_classifier_scope"
        regional_species = []
    elif not regional_species:
        scope_mode = "global_classifier_scope"
    min_center_dist = (
        float(min_center_dist_override)
        if min_center_dist_override is not None
        else float(app_config.get("processor.min_center_dist", 0.1))
    )
    return {
        "mode": "track_regen" if for_track_regen else "live",
        "detection_strategy": str(strategy_type).strip() or "two_stage",
        "regional_scope_mode": scope_mode,
        "regional_species_count": len(regional_species),
        "track_regen_match_live_pipeline": bool(for_track_regen and match_live_regen),
        "track_regen_ignore_regional_species": bool(for_track_regen and ignore_regional),
        "min_center_dist": min_center_dist,
        "binary_imgsz": resolve_binary_model_imgsz(app_config),
        "detector_scope": list(app_config.get("processor.detector_scope") or ["Bird"]),
        "max_classifications_per_frame": int(
            app_config.get("processor.max_classifications_per_frame", 2) or 2,
        ),
        "classification_scheduler": str(
            app_config.get("processor.classification_scheduler", "priority") or "priority",
        ),
    }
