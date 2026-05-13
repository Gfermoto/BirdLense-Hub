#!/usr/bin/env python3
"""Fail CI when new config keys are not wired into Settings UI.

Policy:
- Every terminal key from app/app_config/default_config.yaml must be either:
  1) mapped to a <form.Field name="..."> under app/ui/src/pages/Settings/ (tsx), or
  2) explicitly listed in ALLOWED_NON_UI_KEYS with a reason.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = ROOT / "app" / "app_config" / "default_config.yaml"
SETTINGS_UI_DIR = ROOT / "app" / "ui" / "src" / "pages" / "Settings"

LIBRARY_UI_EVIDENCE = {
    "storage.recordings_mirror.": {
        "ui_file": ROOT / "app" / "ui" / "src" / "pages" / "System" / "RecordingsNasMirrorCard.tsx",
        "api_file": ROOT / "app" / "web" / "routes" / "ui_system_storage_routes.py",
        "api_required": ["/api/ui/storage/recordings-mirror/test"],
    },
    "retention.": {
        "ui_file": ROOT / "app" / "ui" / "src" / "pages" / "System" / "Retention" / "RetentionPolicy.tsx",
        "api_file": ROOT / "app" / "web" / "routes" / "ui_system_db_routes.py",
        "api_required": ["/api/ui/system/retention"],
    },
    "video.": {
        "ui_file": ROOT / "app" / "ui" / "src" / "pages" / "Library" / "FileReplayCard.tsx",
        "api_file": ROOT / "app" / "web" / "routes" / "ui_system_file_test_routes.py",
        "api_required": ["/api/ui/system/file-test/status", "video.source"],
    },
}


# Intentionally hidden from Settings UI.
# Keep this list short and explicit; every key must have
# - category: why it's non-UI today
# - reason: current rationale
# - next_step: when/how to revisit
ALLOWED_NON_UI_KEYS: dict[str, dict[str, str]] = {
    # Trigger transport mirrors integrations.scales.source; UI exposes a single source selector.
    "triggers.scales.source": {
        "category": "derived",
        "reason": "Processor resolves scales trigger transport from integrations.scales.source when unset; duplicate source pickers were removed from Settings.",
        "next_step": "Re-expose only if product needs different MQTT/ESPHome paths for live weight vs weight-trigger sampling.",
    },
    "integrations.scales.motion_trigger_enabled": {
        "category": "legacy",
        "reason": "Superseded by triggers.scales.enabled; trigger_config still reads this for YAML migration.",
        "next_step": "Remove key after migration period or document YAML-only.",
    },
    "integrations.scales.motion_trigger_min_delta_kg": {
        "category": "legacy",
        "reason": "Superseded by triggers.scales.motion_trigger_min_delta_kg with fallback in trigger_config.",
        "next_step": "YAML-only once old configs are rare.",
    },
    "integrations.scales.motion_trigger_debounce_seconds": {
        "category": "legacy",
        "reason": "Superseded by triggers.scales.motion_trigger_debounce_seconds with fallback in trigger_config.",
        "next_step": "YAML-only once old configs are rare.",
    },
    "motion.source": {
        "category": "legacy",
        "reason": "Legacy mirror of grouped triggers.* selectors; modern UI edits triggers.* fields directly.",
        "next_step": "Keep YAML-only until old motion.* configs are phased out.",
    },
    "motion.check_every_n_frames": {
        "category": "legacy",
        "reason": "Legacy mirror of triggers.opencv.check_every_n_frames.",
        "next_step": "Keep YAML-only until old motion.* configs are phased out.",
    },
    "motion.opencv_diff_threshold": {
        "category": "legacy",
        "reason": "Legacy mirror of triggers.opencv.diff_threshold.",
        "next_step": "Keep YAML-only until old motion.* configs are phased out.",
    },
    "motion.opencv_min_contour_area": {
        "category": "legacy",
        "reason": "Legacy mirror of triggers.opencv.min_contour_area.",
        "next_step": "Keep YAML-only until old motion.* configs are phased out.",
    },
    "motion.frigate_min_trigger_score": {
        "category": "legacy",
        "reason": "Legacy Frigate motion key retained for backward compatibility.",
        "next_step": "Keep YAML-only until old motion.* configs are phased out.",
    },
    "motion.mqtt_topic": {
        "category": "legacy",
        "reason": "Legacy mirror of triggers.motion_sensor.mqtt_topic.",
        "next_step": "Keep YAML-only until old motion.* configs are phased out.",
    },
    "motion.esphome_url": {
        "category": "legacy",
        "reason": "Legacy mirror of triggers.motion_sensor.esphome_url.",
        "next_step": "Keep YAML-only until old motion.* configs are phased out.",
    },
    "motion.esphome_sensor_id": {
        "category": "legacy",
        "reason": "Legacy mirror of triggers.motion_sensor.esphome_sensor_id.",
        "next_step": "Keep YAML-only until old motion.* configs are phased out.",
    },
    # Processor internals.
    "processor.detection_strategy": {
        "category": "advanced",
        "reason": "Deployment-level model strategy; unsafe for casual UI edits.",
        "next_step": "Expose behind Advanced/Expert mode after UX spec.",
    },
    "processor.models.binary": {
        "category": "ops-only",
        "reason": "Model path is environment/deployment-specific.",
        "next_step": "Upload/reset via System → Processor weights (#276); not in Settings form.",
    },
    "processor.models.classifier": {
        "category": "ops-only",
        "reason": "Model path is environment/deployment-specific.",
        "next_step": "Upload/reset via System → Processor weights (#276); not in Settings form.",
    },
    "processor.models.binary_openvino": {
        "category": "ops-only",
        "reason": "OpenVINO detector bundle path is deployment-specific and managed server-side.",
        "next_step": "Keep hidden from Settings form; surface only backend selector in UI.",
    },
    "processor.models.classifier_openvino": {
        "category": "ops-only",
        "reason": "OpenVINO classifier bundle path is deployment-specific and managed server-side.",
        "next_step": "Keep hidden from Settings form; surface only backend selector in UI.",
    },
    "processor.regional_species": {
        "category": "planned-ui",
        "reason": "Advanced ML tuning; currently config-level only.",
        "next_step": "Evaluate after #52 (i18n) and settings information architecture pass.",
    },
    "processor.included_bird_families": {
        "category": "planned-ui",
        "reason": "Advanced ML tuning; currently config-level only.",
        "next_step": "Evaluate after #52 (i18n) and settings information architecture pass.",
    },
    "processor.save_images": {
        "category": "advanced",
        "reason": "Storage/performance-sensitive low-level switch.",
        "next_step": "Consider exposing with explicit storage warning in UI.",
    },
    "processor.file_max_record_floor_seconds": {
        "category": "advanced",
        "reason": "video.source=file only: min wall-clock segment before session finalize.",
        "next_step": "Optional Processor advanced if users need tuning without YAML.",
    },
    "processor.keep_recording_when_no_detections": {
        "category": "advanced",
        "reason": "video.source=file: keep session mp4 when 0 detections; for offline crops, not main UI.",
        "next_step": "Optional Processor advanced toggle if file-test users grow.",
    },
    "processor.birdnet_fifo_snapshot_enabled": {
        "category": "ops-only",
        "reason": "Processor writes BirdNET FIFO snapshot JSON for System diagnostics; not end-user Settings.",
        "next_step": "Keep config-level or tie to a single Diagnostics toggle if productized.",
    },
    "processor.birdnet_fifo_snapshot_interval_sec": {
        "category": "ops-only",
        "reason": "Snapshot write interval; tuning for diagnostics load only.",
        "next_step": "Same as birdnet_fifo_snapshot_enabled.",
    },
    "processor.birdnet_fifo_snapshot_recent_limit": {
        "category": "ops-only",
        "reason": "Max recent FIFO rows in snapshot payload.",
        "next_step": "Same as birdnet_fifo_snapshot_enabled.",
    },
    "processor.birdnet_fifo_snapshot_stale_sec": {
        "category": "ops-only",
        "reason": "Web UI stale threshold when reading snapshot from disk.",
        "next_step": "Same as birdnet_fifo_snapshot_enabled.",
    },
    "processor.birdnet_fifo_persist_enabled": {
        "category": "ops-only",
        "reason": "Processor writes BirdNET FIFO rows to hub SQLite (#269); not Settings UI.",
        "next_step": "Same as birdnet_fifo_snapshot_enabled.",
    },
    "processor.birdnet_fifo_sqlite_busy_ms": {
        "category": "ops-only",
        "reason": "SQLite busy_timeout for BirdNET FIFO writer thread.",
        "next_step": "Same as birdnet_fifo_persist_enabled.",
    },
    "processor.birdnet_fifo_hearing_active_hours": {
        "category": "ops-only",
        "reason": "Hearing active window for BirdNET FIFO diagnostics UI (species active 1/0); not Settings.",
        "next_step": "Same as birdnet_fifo_snapshot_enabled.",
    },
    "processor.birdnet_mqtt_observability_level": {
        "category": "ops-only",
        "reason": "Log verbosity for BirdNET MQTT path; operator tuning.",
        "next_step": "Optional advanced Processor logging block.",
    },
    "processor.birdnet_mqtt_observability_debug": {
        "category": "ops-only",
        "reason": "Extra BirdNET MQTT debug logging; not for general UI.",
        "next_step": "Same as birdnet_mqtt_observability_level.",
    },
    "processor.track_regen_parallel_auto_with_manual": {
        "category": "advanced",
        "reason": "Track regeneration parallelism when mixing auto and manual scope; heavy ops.",
        "next_step": "Expose under System/track regen advanced if users need it without YAML.",
    },
    # Re-ID / DINOv2 sidecar policy (#389/#390) — operator YAML until review UX ships.
    "processor.reid_embedding_pipeline_mode": {
        "category": "ops-only",
        "reason": "Embedding generation runs out-of-band; mode is informational + policy input.",
        "next_step": "Expose as read-only status + pilot toggle after nearline worker (#389).",
    },
    "processor.reid_suggestions_enabled": {
        "category": "ops-only",
        "reason": "Safety switch for similarity hints; needs ops discipline.",
        "next_step": "Move to System → ML after UX review queue lands (#390).",
    },
    "processor.reid_kill_switch": {
        "category": "ops-only",
        "reason": "Emergency disable for suggestions without dropping embeddings.",
        "next_step": "Same as reid_suggestions_enabled.",
    },
    "processor.reid_shadow_mode": {
        "category": "ops-only",
        "reason": "Production shadow evaluation without user-facing hints.",
        "next_step": "Pair with metrics dashboard before UI surfacing.",
    },
    "processor.reid_default_similarity_threshold": {
        "category": "ops-only",
        "reason": "Cosine gate depends on embedding contract + species; unsafe as casual slider.",
        "next_step": "Preset tables + per-site calibration workflow (#390).",
    },
    "processor.reid_different_similarity_threshold": {
        "category": "ops-only",
        "reason": "Lower bound for inconclusive decisions; tightly coupled to embeddings noise.",
        "next_step": "Same as reid_default_similarity_threshold.",
    },
    "processor.reid_cross_camera_threshold_boost": {
        "category": "ops-only",
        "reason": "Risk control for cross-folder/camera collisions using video_path heuristics.",
        "next_step": "Replace heuristic with explicit camera_id once available end-to-end.",
    },
    "processor.reid_max_embedding_age_hours": {
        "category": "ops-only",
        "reason": "Staleness gate for offline refresh cadence.",
        "next_step": "Automate refresh jobs + show stale age in System card (#389).",
    },
    "processor.reid_species_similarity_thresholds": {
        "category": "ops-only",
        "reason": "Per-species thresholds are expert tuning; YAML map is the current mechanism.",
        "next_step": "Import/export UI once evaluation harness exists (#390).",
    },
    "processor.max_box_area_norm": {
        "category": "ops-only",
        "reason": "Detector anti-collapse guardrail for near full-frame boxes.",
        "next_step": "Potential expert UI field with diagnostics preview after validation.",
    },
    "processor.generic_rodent_min_frames": {
        "category": "ops-only",
        "reason": "Rodent fallback quality gate; sensitive anti-noise tuning.",
        "next_step": "Keep YAML-only until rodent false-positive profile stabilizes.",
    },
    "processor.generic_rodent_max_area_frac": {
        "category": "ops-only",
        "reason": "Reject rodent fallbacks that look like full-frame detector artifacts.",
        "next_step": "Consider expert UI once rollout baselines are collected.",
    },
    "processor.generic_rodent_min_best_frame_score": {
        "category": "ops-only",
        "reason": "Rodent fallback visual-quality gate tied to best-frame sharpness.",
        "next_step": "Keep YAML-only pending multi-camera calibration.",
    },
    # Merge internals (partially in UI: see Processor → Frigate fusion).
    "detection.source_priority": {
        "category": "advanced",
        "reason": "Advanced merge tuning; kept config-level for now.",
        "next_step": "Keep config-level until merge strategy presets are designed.",
    },
    "detection.species_mapping": {
        "category": "advanced",
        "reason": "Bulk mapping maintained as config dictionary.",
        "next_step": "Consider import/export UI when species tools are expanded.",
    },
    "detection.fusion_model_path": {
        "category": "ops-only",
        "reason": "Fusion model artifact is managed by product workflow or support tools, not typed as a path in Settings.",
        "next_step": "Expose only via recognition improvement workflow / service mode.",
    },
    "detection.fusion_ab_min_yolo_share": {
        "category": "advanced",
        "reason": "Quality-gate KPI threshold for fusion diagnostics; tuned by operators during validation waves.",
        "next_step": "Optional Advanced diagnostics panel once KPI presets UX is designed.",
    },
    "detection.fusion_ab_min_yolo_share_bird_only": {
        "category": "advanced",
        "reason": "Bird-only KPI threshold for fusion diagnostics; not a day-to-day user setting.",
        "next_step": "Keep config-level until fusion diagnostics moves to dedicated ops UI.",
    },
    "detection.fusion_ab_min_yolo_share_bird_only_warn": {
        "category": "advanced",
        "reason": "Soft warning threshold for bird-only fusion KPI in synthetic hub checks.",
        "next_step": "Keep with CI/ops thresholds or expose as preset in diagnostics tooling.",
    },
    "detection.fusion_ab_min_yolo_track_found_rate_warn": {
        "category": "advanced",
        "reason": "Warning floor for YOLO track-found rate in fusion A/B reports; used for ops monitoring.",
        "next_step": "Expose only with full diagnostics context and metric explanation.",
    },
    "detection.fusion_ab_min_decision_trace_rows_warn": {
        "category": "advanced",
        "reason": "Minimum decision-trace sample size for statistically meaningful fusion KPI warnings.",
        "next_step": "Keep config-level while report remains ops-facing.",
    },
    "detection.fusion_non_species_confidence_slack": {
        "category": "advanced",
        "reason": "Fusion confidence tolerance for non-species tracks; expert merge tuning.",
        "next_step": "Expose only with merge diagnostics presets.",
    },
    "detection.track_fragment_merge_enabled": {
        "category": "advanced",
        "reason": "Track-fragment merge behavior is low-level tracking tuning.",
        "next_step": "Consider expert tracker panel with validation.",
    },
    "detection.track_fragment_merge_gap_sec": {
        "category": "advanced",
        "reason": "Track-fragment merge gap is low-level tracking tuning.",
        "next_step": "Consider expert tracker panel with validation.",
    },
    "detection.track_fragment_merge_max_center_dist": {
        "category": "advanced",
        "reason": "Track-fragment merge distance threshold is low-level tracking tuning.",
        "next_step": "Consider expert tracker panel with validation.",
    },
    "detection.track_fragment_merge_min_iou": {
        "category": "advanced",
        "reason": "Track-fragment merge IoU threshold is low-level tracking tuning.",
        "next_step": "Consider expert tracker panel with validation.",
    },
    "detection.yolo_weak_track_salvage_enabled": {
        "category": "advanced",
        "reason": "Weak-track salvage is anti-regression fallback logic for hard scenes.",
        "next_step": "Expose only with clear safety notes and presets.",
    },
    "detection.yolo_weak_track_salvage_min_confidence": {
        "category": "advanced",
        "reason": "Weak-track salvage confidence gate is expert-level tuning.",
        "next_step": "Expose only with clear safety notes and presets.",
    },
    "processor.classifier_vote_share_power": {
        "category": "advanced",
        "reason": "Vote-share exponent controlling classifier arbitration sensitivity in ML pipeline internals.",
        "next_step": "Expose only after calibrated presets and guardrails are defined.",
    },
    "processor.adaptive_profiles.night.overrides.binary_imgsz": {
        "category": "ops-only",
        "reason": "Night adaptive profile detector size override is deployment-specific performance tuning.",
        "next_step": "Keep YAML-only until adaptive profile UX exists.",
    },
    "processor.auto_small_object_relax_conf_delta": {
        "category": "advanced",
        "reason": "Auto-relax delta for small objects is low-level detector rescue tuning.",
        "next_step": "Expose in expert mode with diagnostics only.",
    },
    "processor.auto_small_object_relax_enabled": {
        "category": "advanced",
        "reason": "Auto-relax for small objects is low-level detector rescue tuning.",
        "next_step": "Expose in expert mode with diagnostics only.",
    },
    "processor.auto_small_object_relax_max_candidates": {
        "category": "advanced",
        "reason": "Auto-relax candidate cap for small objects is low-level tuning.",
        "next_step": "Expose in expert mode with diagnostics only.",
    },
    "processor.auto_small_object_relax_min_box_size_px": {
        "category": "advanced",
        "reason": "Auto-relax min box size for small objects is low-level tuning.",
        "next_step": "Expose in expert mode with diagnostics only.",
    },
    "processor.auto_small_object_relax_min_center_dist": {
        "category": "advanced",
        "reason": "Auto-relax center distance for small objects is low-level tuning.",
        "next_step": "Expose in expert mode with diagnostics only.",
    },
    "processor.auto_unstick_enabled": {
        "category": "advanced",
        "reason": "Auto-unstick logic controls tracker recovery behavior.",
        "next_step": "Expose in expert mode with safeguards.",
    },
    "processor.auto_unstick_min_box_size_px": {
        "category": "advanced",
        "reason": "Auto-unstick min box size is low-level tracker recovery tuning.",
        "next_step": "Expose in expert mode with safeguards.",
    },
    "processor.auto_unstick_min_center_dist": {
        "category": "advanced",
        "reason": "Auto-unstick center distance is low-level tracker recovery tuning.",
        "next_step": "Expose in expert mode with safeguards.",
    },
    "processor.auto_unstick_min_confidence_binary": {
        "category": "advanced",
        "reason": "Auto-unstick confidence gate is low-level detector recovery tuning.",
        "next_step": "Expose in expert mode with safeguards.",
    },
    "processor.auto_unstick_min_confidence_binary_bird": {
        "category": "advanced",
        "reason": "Bird-specific auto-unstick confidence gate is low-level detector recovery tuning.",
        "next_step": "Expose in expert mode with safeguards.",
    },
    "processor.auto_unstick_no_track_frames": {
        "category": "advanced",
        "reason": "Auto-unstick no-track frame threshold is low-level tracker recovery tuning.",
        "next_step": "Expose in expert mode with safeguards.",
    },
    "processor.auto_unstick_tracker": {
        "category": "advanced",
        "reason": "Auto-unstick day tracker profile is low-level recovery policy.",
        "next_step": "Expose in expert mode with profile presets.",
    },
    "processor.auto_unstick_tracker_night": {
        "category": "advanced",
        "reason": "Auto-unstick night tracker profile is low-level recovery policy.",
        "next_step": "Expose in expert mode with profile presets.",
    },
    # Behavior recognition baseline (#416) — YAML until UI pilot.
    "processor.behavior_recognition.confidence_review_threshold": {
        "category": "ops-only",
        "reason": "Weak-label review gate for behavior baseline logits; ops tuning.",
        "next_step": "Optional System → ML when behavior controls leave YAML-only.",
    },
    "processor.behavior_recognition.confidence_store_min": {
        "category": "ops-only",
        "reason": "Minimum probability to persist behavior_label on finalize; avoids noisy writes.",
        "next_step": "Same as processor.behavior_recognition.enabled.",
    },
    "processor.behavior_recognition.enabled": {
        "category": "ops-only",
        "reason": "Master switch for optional logistic behavior head on recording finalize.",
        "next_step": "Expose pilot toggle + status after operator UX review.",
    },
    "processor.behavior_recognition.weights_path": {
        "category": "ops-only",
        "reason": "Path to behavior_logistic_export@v1 JSON; deployment-specific like detector weights.",
        "next_step": "Optional upload alongside processor weights when artifact workflow matures.",
    },
    "processor.binary_track_iou": {
        "category": "advanced",
        "reason": "Binary detector tracker IoU threshold is low-level tracking parameter.",
        "next_step": "Expose in expert tracker section with validation.",
    },
    "processor.binary_track_max_det": {
        "category": "advanced",
        "reason": "Binary detector max detections per frame is low-level performance/safety tuning.",
        "next_step": "Expose in expert tracker section with validation.",
    },
    "processor.iou_id_fallback_live_enabled": {
        "category": "advanced",
        "reason": "Live IoU ID fallback is low-level identity continuity logic.",
        "next_step": "Expose in expert mode with explanatory diagnostics.",
    },
    "processor.iou_id_fallback_live_match_threshold": {
        "category": "advanced",
        "reason": "Live IoU ID fallback match threshold is low-level identity continuity tuning.",
        "next_step": "Expose in expert mode with explanatory diagnostics.",
    },
    "processor.letterbox_resize_interpolation": {
        "category": "ops-only",
        "reason": "Letterbox interpolation method affects inference image preprocessing internals.",
        "next_step": "Keep YAML-only unless benchmarking UI is introduced.",
    },
    "processor.track_regen_min_track_duration": {
        "category": "advanced",
        "reason": "Track regeneration minimum track duration is batch-regeneration tuning.",
        "next_step": "Expose under System track regeneration advanced controls.",
    },
    "processor.track_regen_serialize_inference": {
        "category": "advanced",
        "reason": "Track regeneration inference serialization is batch performance tuning.",
        "next_step": "Expose under System track regeneration advanced controls.",
    },
    "processor.track_regen_serialize_inference_interprocess": {
        "category": "advanced",
        "reason": "Interprocess serialization for regeneration inference is batch performance tuning.",
        "next_step": "Expose under System track regeneration advanced controls.",
    },
    "processor.track_to_predict_fallback_confidence": {
        "category": "advanced",
        "reason": "Track-to-predict fallback confidence gate is low-level inference fallback tuning.",
        "next_step": "Expose in expert mode with diagnostics.",
    },
    "processor.track_to_predict_fallback_enabled": {
        "category": "advanced",
        "reason": "Track-to-predict fallback switch is low-level inference fallback tuning.",
        "next_step": "Expose in expert mode with diagnostics.",
    },
    "processor.ultra_weak_box_salvage_enabled": {
        "category": "advanced",
        "reason": "Ultra-weak box salvage is emergency detector recovery logic.",
        "next_step": "Expose only in expert mode with warnings.",
    },
    "processor.ultra_weak_box_salvage_max_candidates": {
        "category": "advanced",
        "reason": "Ultra-weak salvage candidate cap is low-level recovery tuning.",
        "next_step": "Expose only in expert mode with warnings.",
    },
    "processor.ultra_weak_box_salvage_min_confidence": {
        "category": "advanced",
        "reason": "Ultra-weak salvage confidence gate is low-level recovery tuning.",
        "next_step": "Expose only in expert mode with warnings.",
    },
    "processor.openvino.model_cache_enabled": {
        "category": "ops-only",
        "reason": "OpenVINO runtime cache behavior is host/runtime optimization, not end-user settings.",
        "next_step": "Expose only in expert diagnostics mode with restart guidance.",
    },
    "processor.openvino.num_requests": {
        "category": "ops-only",
        "reason": "OpenVINO parallel inference requests are hardware/performance tuning knobs.",
        "next_step": "Keep config-level until benchmark-backed presets exist.",
    },
    "processor.openvino.profile": {
        "category": "ops-only",
        "reason": "OpenVINO profile switch is an optimization preset for deployment engineers.",
        "next_step": "Potentially map to simplified performance profiles later.",
    },
    "processor.reid.device": {
        "category": "ops-only",
        "reason": "ReID execution device is hardware-specific and deployment-tuned.",
        "next_step": "Expose only via System diagnostics if needed.",
    },
    "processor.reid.flag_low_similarity_for_review": {
        "category": "advanced",
        "reason": "Review workflow sensitivity setting for low-similarity ReID matches.",
        "next_step": "Add when ReID reviewer UX includes explicit confidence controls.",
    },
    "processor.reid.hub_cache_dir": {
        "category": "ops-only",
        "reason": "Filesystem path for model cache is environment-specific.",
        "next_step": "Keep YAML-only.",
    },
    "processor.reid.hub_repo_local_path": {
        "category": "ops-only",
        "reason": "Optional local HF repo mirror path is deployment-specific.",
        "next_step": "Keep YAML-only.",
    },
    "processor.reid.max_detections_per_recording": {
        "category": "advanced",
        "reason": "ReID compute cap per recording for performance control; not needed in basic Settings UI.",
        "next_step": "Consider exposing in expert mode with compute-cost warning.",
    },
    "processor.reid.min_best_frame_score": {
        "category": "advanced",
        "reason": "Frame-quality threshold for ReID embedding extraction is ML internals tuning.",
        "next_step": "Expose only with visual guidance in ReID diagnostics UX.",
    },
    "processor.reid.model": {
        "category": "ops-only",
        "reason": "ReID model selection ties to deployment artifacts and compatibility.",
        "next_step": "Manage via system model tooling, not general settings.",
    },
    "processor.reid.nickname_similarity_threshold": {
        "category": "advanced",
        "reason": "Similarity threshold affecting nickname assignment confidence in ReID workflow.",
        "next_step": "Expose when nickname assignment UX adds threshold preview/help.",
    },
    "processor.reid.preload_on_start": {
        "category": "ops-only",
        "reason": "Startup preload impacts boot time/memory and is deployment-specific.",
        "next_step": "Keep config-level or map to performance profile presets.",
    },
    "processor.reid.runtime_enabled": {
        "category": "advanced",
        "reason": "Master switch for ReID runtime pipeline; advanced feature toggle.",
        "next_step": "Expose only with clear operator guidance once ReID UX matures.",
    },
    "processor.tracker_profiles.day": {
        "category": "advanced",
        "reason": "Nested tracker profile object for daytime tuning is expert-level and high-risk for misconfiguration.",
        "next_step": "Expose through dedicated tracker profile editor with validation.",
    },
    "processor.tracker_profiles.night": {
        "category": "advanced",
        "reason": "Nested tracker profile object for low-light tuning is expert-level and high-risk for misconfiguration.",
        "next_step": "Expose through dedicated tracker profile editor with validation.",
    },
    # Ops/security-sensitive/infra-generated values.
    "web_push.enabled": {
        "category": "backend-managed",
        "reason": "Derived by backend from subscriptions.",
        "next_step": "Keep backend-managed.",
    },
    "web_push.vapid_public_key": {
        "category": "backend-managed",
        "reason": "Generated/managed by backend.",
        "next_step": "Keep backend-managed.",
    },
    "web_push.vapid_private_key": {
        "category": "backend-managed",
        "reason": "Secret generated/managed by backend.",
        "next_step": "Keep backend-managed.",
    },
    # Runtime controls still config-level.
    "video.source": {
        "category": "library-ui",
        "reason": "go2rtc vs file replay; toggled in Library (PATCH), not Settings form.",
        "next_step": "Single entry: Library → file replay.",
    },
    "video.file_path": {
        "category": "yaml-only",
        "reason": "Absolute path to test mp4 is deployment-specific; not edited in Settings (Library / YAML).",
        "next_step": "Keep out of Settings form.",
    },
    "video.file_dir": {
        "category": "library-ui",
        "reason": "Test clip folder; edited in Library file replay card.",
        "next_step": "Keep Library as single UX entry.",
    },
    "video.file_loop": {
        "category": "library-ui",
        "reason": "Default playlist loop for file mode; set in Library when enabling replay.",
        "next_step": "Keep Library as single UX entry.",
    },
    "video.file_test_max_upload_mb": {
        "category": "library-ui",
        "reason": "Hub upload size cap for Library file replay; tunable in YAML.",
        "next_step": "Optional expose in Library advanced later.",
    },
    "retention.days": {
        "category": "library-ui",
        "reason": "Retention knobs are shown and run from Library → Database maintenance (RetentionPolicy), not Settings forms.",
        "next_step": "Optional: mirror in Settings later; single UX entry is Library card.",
    },
    "retention.mode": {
        "category": "library-ui",
        "reason": "Retention run mode override lives next to dry-run/apply on Library maintenance card.",
        "next_step": "Keep Library as single UX entry unless Settings parity is required.",
    },
    "retention.max_gb": {
        "category": "library-ui",
        "reason": "Optional size cap for retention; configured in YAML; surfaced read-only on Library retention card context.",
        "next_step": "Keep YAML + Library readout; optional Settings field later.",
    },
    "retention.dataset_max_age_days": {
        "category": "library-ui",
        "reason": "Dataset TTL for retention; YAML + read-only summary on Library retention card.",
        "next_step": "Keep Library card / YAML.",
    },
    "retention.migration_max_age_days": {
        "category": "library-ui",
        "reason": "Migration history TTL; YAML + read-only summary on Library retention card.",
        "next_step": "Keep Library card / YAML.",
    },
    "retention.protect_favorites": {
        "category": "library-ui",
        "reason": "Safety flag for retention; YAML + read-only summary on Library retention card.",
        "next_step": "Keep Library card / YAML.",
    },
    "retention.min_age_hours": {
        "category": "library-ui",
        "reason": "Grace period for retention; YAML + read-only summary on Library retention card.",
        "next_step": "Keep Library card / YAML.",
    },
    "retention.batch_size": {
        "category": "library-ui",
        "reason": "Batch size for retention API; YAML + read-only summary on Library retention card.",
        "next_step": "Keep Library card / YAML.",
    },
    # SFTP mirror for recordings (#350): Library → Storage / System storage card, not Settings forms.
    "storage.recordings_mirror.enabled": {
        "category": "library-ui",
        "reason": "Edited in Library → Storage (NAS mirror card); processor reads after restart.",
        "next_step": "Keep Library/System as single UX entry.",
    },
    "storage.recordings_mirror.protocol": {
        "category": "library-ui",
        "reason": "SFTP-only today; exposed on NAS mirror card, not Settings.",
        "next_step": "Keep Library/System card.",
    },
    "storage.recordings_mirror.host": {
        "category": "library-ui",
        "reason": "Mirror host on NAS mirror card.",
        "next_step": "Keep Library/System card.",
    },
    "storage.recordings_mirror.port": {
        "category": "library-ui",
        "reason": "SFTP port on NAS mirror card.",
        "next_step": "Keep Library/System card.",
    },
    "storage.recordings_mirror.username": {
        "category": "library-ui",
        "reason": "SFTP user on NAS mirror card.",
        "next_step": "Keep Library/System card.",
    },
    "storage.recordings_mirror.sftp_password": {
        "category": "library-ui",
        "reason": "Secret on NAS mirror card; masked in settings API like other hub secrets.",
        "next_step": "Keep Library/System card.",
    },
    "storage.recordings_mirror.sftp_key_passphrase": {
        "category": "library-ui",
        "reason": "Key passphrase on NAS mirror card.",
        "next_step": "Keep Library/System card.",
    },
    "storage.recordings_mirror.remote_base_path": {
        "category": "library-ui",
        "reason": "Remote base path on NAS mirror card.",
        "next_step": "Keep Library/System card.",
    },
    "storage.recordings_mirror.ssh_private_key_path": {
        "category": "library-ui",
        "reason": "Optional key path on NAS mirror card.",
        "next_step": "Keep Library/System card.",
    },
    "storage.recordings_mirror.max_concurrent_uploads": {
        "category": "library-ui",
        "reason": "Processor concurrency; advanced on NAS mirror card / YAML.",
        "next_step": "Optional Settings advanced later.",
    },
    "storage.recordings_mirror.upload_retries": {
        "category": "library-ui",
        "reason": "Retry count on NAS mirror card / YAML.",
        "next_step": "Keep Library/System card.",
    },
    "storage.recordings_mirror.retry_backoff_seconds": {
        "category": "library-ui",
        "reason": "Backoff on NAS mirror card / YAML.",
        "next_step": "Keep Library/System card.",
    },
    "storage.recordings_mirror.strict_host_key": {
        "category": "library-ui",
        "reason": "Host key policy toggle on NAS mirror card.",
        "next_step": "Keep Library/System card.",
    },
    "storage.recordings_mirror.known_hosts_path": {
        "category": "library-ui",
        "reason": "Optional known_hosts path on NAS mirror card.",
        "next_step": "Keep Library/System card.",
    },
    "storage.recordings_mirror.delete_local_after_success": {
        "category": "library-ui",
        "reason": "Expert destructive option on NAS mirror card.",
        "next_step": "Keep expert-only on Library/System card.",
    },
    "species.catalog_allowlist_file": {
        "category": "yaml-only",
        "reason": "Path to classifier class list is deployment/repo layout; not configured in Settings.",
        "next_step": "Keep in user_config.yaml or defaults.",
    },
    "mqtt.frigate_topic": {
        "category": "legacy",
        "reason": "Superseded by triggers.frigate.topic; migrate_legacy_trigger_topics copies into triggers on save/load.",
        "next_step": "Keep MQTT mirror for old configs.",
    },
    "mqtt.birdnet_topic": {
        "category": "legacy",
        "reason": "Superseded by integrations.birdnet.mqtt_topic via migrate_legacy_trigger_topics.",
        "next_step": "Keep MQTT mirror for old configs.",
    },
    "ebird.protocol": {
        "category": "yaml-only",
        "reason": "eBird export protocol seldom changed from defaults; config-level.",
        "next_step": "Expose under eBird section if editors need toggles.",
    },
    "general.require_auth_for_video_stream": {
        "category": "access-control",
        "reason": "Video stream Viewer vs Contributor gate; keyed in typed Settings snapshot but toggled elsewhere / YAML-focused.",
        "next_step": "Wire to General accordion when UX revisits ACCESS_CONTROL knobs.",
    },
}

# Legacy terminal keys that are still config-level (not yet exposed in Settings UI).
# Keep explicit list to avoid silent drift while unblocking CI on existing scope.
AUTO_ALLOWLIST_META = {
    "category": "planned-ui",
    "reason": "Config-level key is intentionally not exposed in current Settings UI.",
    "next_step": "Expose in Settings UI or move to strict allowlist section with dedicated rationale.",
}
AUTO_ALLOWLIST_KEYS: set[str] = set()

TERMINAL_MAP_KEYS = {
    # Mapping dictionaries are edited as one textarea in UI.
    "detection.species_mapping",
    "ebird.species_mapping",
}


def _collect_terminal_keys(obj: object, prefix: str = "") -> list[str]:
    """Collect dot-keys; treat scalar/list and selected map keys as terminal."""
    if isinstance(obj, dict):
        if prefix in TERMINAL_MAP_KEYS:
            return [prefix] if prefix else []
        keys: list[str] = []
        for k, v in obj.items():
            next_prefix = f"{prefix}.{k}" if prefix else str(k)
            keys.extend(_collect_terminal_keys(v, next_prefix))
        return keys
    if isinstance(obj, list):
        return [prefix] if prefix else []
    return [prefix] if prefix else []


def _load_form_fields() -> set[str]:
    names: set[str] = set()
    for path in sorted(SETTINGS_UI_DIR.rglob("*.tsx")):
        text = path.read_text(encoding="utf-8")
        names.update(re.findall(r'form\.Field name="([^"]+)"', text))
    return names


def _build_report(config_keys: set[str], form_fields: set[str]) -> dict:
    rows = []
    category_stats: dict[str, int] = {}
    for key in sorted(config_keys):
        if key in form_fields:
            status = "ui"
            reason = ""
            category = ""
            next_step = ""
        elif key in ALLOWED_NON_UI_KEYS or key in AUTO_ALLOWLIST_KEYS:
            status = "allowlisted_non_ui"
            meta = ALLOWED_NON_UI_KEYS.get(key, AUTO_ALLOWLIST_META)
            reason = meta["reason"]
            category = meta["category"]
            next_step = meta["next_step"]
            category_stats[category] = category_stats.get(category, 0) + 1
        else:
            status = "missing"
            reason = "No UI field and not allowlisted."
            category = ""
            next_step = ""
        rows.append(
            {
                "key": key,
                "status": status,
                "category": category,
                "reason": reason,
                "next_step": next_step,
            }
        )
    missing = [r["key"] for r in rows if r["status"] == "missing"]
    return {
        "summary": {
            "config_keys": len(config_keys),
            "ui_fields": len(form_fields),
            "allowlisted_non_ui": len(ALLOWED_NON_UI_KEYS),
            "missing": len(missing),
            "allowlist_by_category": category_stats,
        },
        "missing_keys": missing,
        "rows": rows,
    }


def _to_markdown(report: dict) -> str:
    s = report["summary"]
    lines = [
        "## Settings UI Coverage Audit",
        "",
        f"- Config keys: **{s['config_keys']}**",
        f"- UI fields: **{s['ui_fields']}**",
        f"- Allowlisted non-UI keys: **{s['allowlisted_non_ui']}**",
        f"- Missing keys: **{s['missing']}**",
        "",
        "### Allowlist maturity categories",
        "",
    ]
    for category, count in sorted(s.get("allowlist_by_category", {}).items()):
        lines.append(f"- `{category}`: **{count}**")
    lines.extend([
        "",
        "| Key | Status | Category | Reason | Next step |",
        "|---|---|---|---|---|",
    ])
    for row in report["rows"]:
        status = {
            "ui": "UI",
            "allowlisted_non_ui": "Allowlisted",
            "missing": "Missing",
        }[row["status"]]
        reason = row["reason"] or "-"
        category = row.get("category") or "-"
        next_step = row.get("next_step") or "-"
        lines.append(
            f"| `{row['key']}` | {status} | `{category}` | {reason} | {next_step} |"
        )
    lines.append("")
    return "\n".join(lines)


def _validate_allowlist() -> list[str]:
    errors: list[str] = []
    for key, meta in ALLOWED_NON_UI_KEYS.items():
        if not isinstance(meta, dict):
            errors.append(f"{key}: metadata must be an object")
            continue
        for required in ("category", "reason", "next_step"):
            if not meta.get(required):
                errors.append(f"{key}: missing '{required}'")
    return errors


def _validate_library_ui_coverage() -> list[str]:
    errors: list[str] = []
    ui_cache: dict[Path, str] = {}
    api_cache: dict[Path, str] = {}
    for key, meta in ALLOWED_NON_UI_KEYS.items():
        if meta.get("category") != "library-ui":
            continue
        spec = None
        for prefix, candidate in LIBRARY_UI_EVIDENCE.items():
            if key.startswith(prefix):
                spec = (prefix, candidate)
                break
        if spec is None:
            errors.append(f"{key}: library-ui key has no evidence mapping by prefix")
            continue
        prefix, candidate = spec
        ui_file = candidate["ui_file"]
        api_file = candidate["api_file"]
        ui_text = ui_cache.setdefault(ui_file, ui_file.read_text(encoding="utf-8"))
        api_text = api_cache.setdefault(api_file, api_file.read_text(encoding="utf-8"))

        leaf = key[len(prefix) :]
        if leaf not in ui_text:
            errors.append(
                f"{key}: not found in UI evidence file {ui_file.relative_to(ROOT)}",
            )
        for token in candidate.get("api_required", []):
            if token not in api_text:
                errors.append(
                    f"{key}: API evidence token '{token}' not found in {api_file.relative_to(ROOT)}",
                )
    return errors


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--report-path",
        default="",
        help="Optional path to write JSON report.",
    )
    parser.add_argument(
        "--summary-path",
        default="",
        help="Optional path to write Markdown summary table.",
    )
    parser.add_argument(
        "--no-strict",
        action="store_true",
        help="Do not fail when missing keys exist.",
    )
    parser.add_argument(
        "--allow-planned-ui",
        action="store_true",
        help="Allow planned-ui entries in allowlist (default strict mode rejects them).",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    allowlist_errors = _validate_allowlist()
    if allowlist_errors:
        print("Settings UI coverage check FAILED: invalid allowlist metadata.")
        for err in allowlist_errors:
            print(f"  - {err}")
        if not args.no_strict:
            return 1

    library_ui_errors = _validate_library_ui_coverage()
    if library_ui_errors:
        print("Settings UI coverage check FAILED: library-ui evidence is incomplete.")
        for err in library_ui_errors:
            print(f"  - {err}")
        if not args.no_strict:
            return 1

    cfg = yaml.safe_load(DEFAULT_CONFIG_PATH.read_text(encoding="utf-8"))
    config_keys = {k for k in _collect_terminal_keys(cfg) if k}
    form_fields = _load_form_fields()
    report = _build_report(config_keys, form_fields)
    missing = report["missing_keys"]
    planned_ui_count = report["summary"].get("allowlist_by_category", {}).get(
        "planned-ui",
        0,
    )
    md = _to_markdown(report)

    if args.report_path:
        report_path = Path(args.report_path)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    if args.summary_path:
        summary_path = Path(args.summary_path)
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_path.write_text(md, encoding="utf-8")

    if missing:
        print("Settings UI coverage check FAILED.")
        print("These config keys are not in Settings UI and not allowlisted:")
        for key in missing:
            print(f"  - {key}")
        print("\nEither add form fields under app/ui/src/pages/Settings/ or add explicit allowlist entries.")
        if not args.no_strict:
            return 1

    if planned_ui_count:
        print(
            "Settings UI coverage check FAILED: "
            f"{planned_ui_count} allowlisted keys still marked as planned-ui.",
        )
        print("Move those keys to Settings UI or re-categorize with explicit rationale.")
        if not args.allow_planned_ui and not args.no_strict:
            return 1

    print(
        "Settings UI coverage OK: "
        f"{len(config_keys)} config keys, {len(form_fields)} UI fields, "
        f"{len(ALLOWED_NON_UI_KEYS)} allowlisted non-UI keys, "
        f"{len(missing)} missing."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
