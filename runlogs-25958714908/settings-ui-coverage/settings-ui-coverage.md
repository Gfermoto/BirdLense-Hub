## Settings UI Coverage Audit

- Config keys: **340**
- UI fields: **242**
- Allowlisted non-UI keys: **152**
- Missing keys: **0**

### Allowlist maturity categories

- `access-control`: **1**
- `advanced`: **42**
- `backend-managed`: **3**
- `derived`: **1**
- `legacy`: **5**
- `library-ui`: **26**
- `ops-only`: **21**
- `yaml-only`: **3**

| Key | Status | Category | Reason | Next step |
|---|---|---|---|---|
| `detection.absorb_generic_bird` | UI | `-` | - | - |
| `detection.absorb_generic_bird_min_classifier_confidence` | UI | `-` | - | - |
| `detection.absorb_generic_bird_overlap_min_sec` | UI | `-` | - | - |
| `detection.cross_source_confidence_bonus` | UI | `-` | - | - |
| `detection.dedup_window_seconds` | UI | `-` | - | - |
| `detection.frigate_standalone_excluded_min_score` | UI | `-` | - | - |
| `detection.frigate_standalone_excluded_missing_score_fallback` | UI | `-` | - | - |
| `detection.frigate_standalone_min_score` | UI | `-` | - | - |
| `detection.frigate_standalone_missing_score_fallback` | UI | `-` | - | - |
| `detection.frigate_standalone_notify` | UI | `-` | - | - |
| `detection.frigate_standalone_skip_labels` | UI | `-` | - | - |
| `detection.frigate_standalone_when_no_accepted_species` | UI | `-` | - | - |
| `detection.frigate_standalone_when_no_yolo` | UI | `-` | - | - |
| `detection.frigate_trigger_review_salvage_enabled` | Allowlisted | `advanced` | Frigate trigger review salvage is expert anti-regression tuning. | YAML-only until Frigate trigger advanced UX exists. |
| `detection.fusion_alpha` | UI | `-` | - | - |
| `detection.fusion_model_path` | Allowlisted | `ops-only` | Fusion model artifact is managed by product workflow or support tools, not typed as a path in Settings. | Expose only via recognition improvement workflow / service mode. |
| `detection.fusion_non_species_confidence_slack` | Allowlisted | `advanced` | Fusion confidence tolerance for non-species tracks; expert merge tuning. | Expose only with merge diagnostics presets. |
| `detection.merge_window_seconds` | UI | `-` | - | - |
| `detection.min_confidence_to_store` | UI | `-` | - | - |
| `detection.one_per_species` | UI | `-` | - | - |
| `detection.source_priority` | Allowlisted | `advanced` | Advanced merge tuning; kept config-level for now. | Keep config-level until merge strategy presets are designed. |
| `detection.species_mapping` | Allowlisted | `advanced` | Bulk mapping maintained as config dictionary. | Consider import/export UI when species tools are expanded. |
| `detection.track_fragment_merge_enabled` | Allowlisted | `advanced` | Track-fragment merge behavior is low-level tracking tuning. | Consider expert tracker panel with validation. |
| `detection.track_fragment_merge_gap_sec` | Allowlisted | `advanced` | Track-fragment merge gap is low-level tracking tuning. | Consider expert tracker panel with validation. |
| `detection.track_fragment_merge_max_center_dist` | Allowlisted | `advanced` | Track-fragment merge distance threshold is low-level tracking tuning. | Consider expert tracker panel with validation. |
| `detection.track_fragment_merge_min_iou` | Allowlisted | `advanced` | Track-fragment merge IoU threshold is low-level tracking tuning. | Consider expert tracker panel with validation. |
| `detection.use_learned_fusion` | UI | `-` | - | - |
| `detection.yolo_weak_track_salvage_enabled` | Allowlisted | `advanced` | Weak-track salvage is anti-regression fallback logic for hard scenes. | Expose only with clear safety notes and presets. |
| `detection.yolo_weak_track_salvage_min_confidence` | Allowlisted | `advanced` | Weak-track salvage confidence gate is expert-level tuning. | Expose only with clear safety notes and presets. |
| `ebird.country` | UI | `-` | - | - |
| `ebird.location_name` | UI | `-` | - | - |
| `ebird.protocol` | Allowlisted | `yaml-only` | eBird export protocol seldom changed from defaults; config-level. | Expose under eBird section if editors need toggles. |
| `ebird.species_mapping` | UI | `-` | - | - |
| `ebird.state` | UI | `-` | - | - |
| `feed.duration_seconds` | UI | `-` | - | - |
| `feed.esphome_switch_id` | UI | `-` | - | - |
| `feed.esphome_type` | UI | `-` | - | - |
| `feed.esphome_url` | UI | `-` | - | - |
| `feed.mqtt_topic` | UI | `-` | - | - |
| `feed.source` | UI | `-` | - | - |
| `general.birdnet_url` | UI | `-` | - | - |
| `general.contributor_password` | UI | `-` | - | - |
| `general.donate_url` | UI | `-` | - | - |
| `general.enable_notifications` | UI | `-` | - | - |
| `general.notification_excluded_species` | UI | `-` | - | - |
| `general.require_auth_for_video_stream` | Allowlisted | `access-control` | Video stream Viewer vs Contributor gate; keyed in typed Settings snapshot but toggled elsewhere / YAML-focused. | Wire to General accordion when UX revisits ACCESS_CONTROL knobs. |
| `general.session_idle_minutes` | UI | `-` | - | - |
| `general.settings_password` | UI | `-` | - | - |
| `homeassistant.token` | UI | `-` | - | - |
| `homeassistant.url` | UI | `-` | - | - |
| `integrations.birdnet.mqtt_topic` | UI | `-` | - | - |
| `integrations.scales.enabled` | UI | `-` | - | - |
| `integrations.scales.esphome_bird_present_sensor_id` | UI | `-` | - | - |
| `integrations.scales.esphome_tare_button_id` | UI | `-` | - | - |
| `integrations.scales.esphome_url` | UI | `-` | - | - |
| `integrations.scales.esphome_weight_sensor_id` | UI | `-` | - | - |
| `integrations.scales.estimate_require_consecutive_spike` | UI | `-` | - | - |
| `integrations.scales.history_max_lines` | UI | `-` | - | - |
| `integrations.scales.min_delta_kg_for_estimate` | UI | `-` | - | - |
| `integrations.scales.motion_trigger_debounce_seconds` | Allowlisted | `legacy` | Superseded by triggers.scales.motion_trigger_debounce_seconds with fallback in trigger_config. | YAML-only once old configs are rare. |
| `integrations.scales.motion_trigger_enabled` | Allowlisted | `legacy` | Superseded by triggers.scales.enabled; trigger_config still reads this for YAML migration. | Remove key after migration period or document YAML-only. |
| `integrations.scales.motion_trigger_min_delta_kg` | Allowlisted | `legacy` | Superseded by triggers.scales.motion_trigger_min_delta_kg with fallback in trigger_config. | YAML-only once old configs are rare. |
| `integrations.scales.mqtt_bird_present_topic` | UI | `-` | - | - |
| `integrations.scales.mqtt_command_topic` | UI | `-` | - | - |
| `integrations.scales.mqtt_tare_payload` | UI | `-` | - | - |
| `integrations.scales.mqtt_topic` | UI | `-` | - | - |
| `integrations.scales.mqtt_topic_prefix` | UI | `-` | - | - |
| `integrations.scales.source` | UI | `-` | - | - |
| `integrations.scales.unit` | UI | `-` | - | - |
| `integrations.scales.weight_estimate_enabled` | UI | `-` | - | - |
| `mcp.enabled` | UI | `-` | - | - |
| `mcp.token` | UI | `-` | - | - |
| `mqtt.birdnet_topic` | Allowlisted | `legacy` | Superseded by integrations.birdnet.mqtt_topic via migrate_legacy_trigger_topics. | Keep MQTT mirror for old configs. |
| `mqtt.broker` | UI | `-` | - | - |
| `mqtt.feeder_scale_queue_max` | Allowlisted | `advanced` | Outbound queue sizing for feeder-scale MQTT path; operator backpressure tuning. | YAML-only or optional advanced MQTT/Processor panel. |
| `mqtt.frigate_topic` | Allowlisted | `legacy` | Superseded by triggers.frigate.topic; migrate_legacy_trigger_topics copies into triggers on save/load. | Keep MQTT mirror for old configs. |
| `mqtt.ha_discovery` | UI | `-` | - | - |
| `mqtt.max_events` | Allowlisted | `advanced` | Inbound MQTT ring buffer cap for processor transport. | YAML-only or observability presets. |
| `mqtt.password` | UI | `-` | - | - |
| `mqtt.port` | UI | `-` | - | - |
| `mqtt.publish_queue_max` | Allowlisted | `advanced` | Publish-side MQTT queue cap (backpressure); operator tuning. | YAML-only; see processor performance docs. |
| `mqtt.publish_topic` | UI | `-` | - | - |
| `mqtt.reconnect_jitter_ratio` | Allowlisted | `advanced` | Reconnect backoff jitter ratio for MQTT client. | YAML-only. |
| `mqtt.reconnect_max_delay` | UI | `-` | - | - |
| `mqtt.reconnect_min_delay` | UI | `-` | - | - |
| `mqtt.username` | UI | `-` | - | - |
| `notifications.base_url` | UI | `-` | - | - |
| `notifications.compress_photo_over_kb` | UI | `-` | - | - |
| `notifications.custom_emoji_id_bird` | UI | `-` | - | - |
| `notifications.custom_emoji_id_chipmunk` | UI | `-` | - | - |
| `notifications.custom_emoji_id_open_live` | UI | `-` | - | - |
| `notifications.disable_notification` | UI | `-` | - | - |
| `notifications.link_preview_large` | UI | `-` | - | - |
| `notifications.message_thread_id` | UI | `-` | - | - |
| `notifications.paid_media_forward_star_count` | UI | `-` | - | - |
| `notifications.paid_media_view_star_count` | UI | `-` | - | - |
| `notifications.protect_content` | UI | `-` | - | - |
| `notifications.send_photo` | UI | `-` | - | - |
| `notifications.telegram_api_base` | UI | `-` | - | - |
| `notifications.telegram_api_hash` | UI | `-` | - | - |
| `notifications.telegram_api_id` | UI | `-` | - | - |
| `notifications.telegram_bot_token` | UI | `-` | - | - |
| `notifications.telegram_chat_id` | UI | `-` | - | - |
| `notifications.telegram_max_side_px` | UI | `-` | - | - |
| `notifications.telegram_mtproto_host` | UI | `-` | - | - |
| `notifications.telegram_mtproto_port` | UI | `-` | - | - |
| `notifications.telegram_mtproto_secret` | UI | `-` | - | - |
| `notifications.telegram_proxy_type` | UI | `-` | - | - |
| `notifications.telegram_proxy_url` | UI | `-` | - | - |
| `notifications.telegram_retries` | UI | `-` | - | - |
| `notifications.telegram_timeout` | UI | `-` | - | - |
| `notifications.use_custom_emoji` | UI | `-` | - | - |
| `performance.cache_redis_enabled` | UI | `-` | - | - |
| `performance.redis_url` | UI | `-` | - | - |
| `processor.adaptive_profiles.enabled` | UI | `-` | - | - |
| `processor.adaptive_profiles.night.max_brightness` | UI | `-` | - | - |
| `processor.adaptive_profiles.night.max_contrast` | UI | `-` | - | - |
| `processor.adaptive_profiles.night.overrides.binary_imgsz` | Allowlisted | `ops-only` | Night adaptive profile detector size override is deployment-specific performance tuning. | Keep YAML-only until adaptive profile UX exists. |
| `processor.adaptive_profiles.night.overrides.light_gate_min_brightness` | UI | `-` | - | - |
| `processor.adaptive_profiles.night.overrides.light_gate_min_contrast` | UI | `-` | - | - |
| `processor.adaptive_profiles.night.overrides.max_classifications_per_frame` | UI | `-` | - | - |
| `processor.adaptive_profiles.night.overrides.min_box_size_px` | UI | `-` | - | - |
| `processor.adaptive_profiles.night.overrides.min_center_dist` | UI | `-` | - | - |
| `processor.adaptive_profiles.night.overrides.min_confidence_binary` | UI | `-` | - | - |
| `processor.adaptive_profiles.night.overrides.min_confidence_binary_bird` | UI | `-` | - | - |
| `processor.adaptive_profiles.night.overrides.min_confidence_to_process` | UI | `-` | - | - |
| `processor.adaptive_profiles.night.overrides.min_track_duration` | UI | `-` | - | - |
| `processor.auto_small_object_relax_conf_delta` | Allowlisted | `advanced` | Auto-relax delta for small objects is low-level detector rescue tuning. | Expose in expert mode with diagnostics only. |
| `processor.auto_small_object_relax_enabled` | Allowlisted | `advanced` | Auto-relax for small objects is low-level detector rescue tuning. | Expose in expert mode with diagnostics only. |
| `processor.auto_small_object_relax_max_candidates` | Allowlisted | `advanced` | Auto-relax candidate cap for small objects is low-level tuning. | Expose in expert mode with diagnostics only. |
| `processor.auto_small_object_relax_min_box_size_px` | Allowlisted | `advanced` | Auto-relax min box size for small objects is low-level tuning. | Expose in expert mode with diagnostics only. |
| `processor.auto_small_object_relax_min_center_dist` | Allowlisted | `advanced` | Auto-relax center distance for small objects is low-level tuning. | Expose in expert mode with diagnostics only. |
| `processor.auto_unstick_enabled` | Allowlisted | `advanced` | Auto-unstick logic controls tracker recovery behavior. | Expose in expert mode with safeguards. |
| `processor.auto_unstick_min_box_size_px` | Allowlisted | `advanced` | Auto-unstick min box size is low-level tracker recovery tuning. | Expose in expert mode with safeguards. |
| `processor.auto_unstick_min_center_dist` | Allowlisted | `advanced` | Auto-unstick center distance is low-level tracker recovery tuning. | Expose in expert mode with safeguards. |
| `processor.auto_unstick_min_confidence_binary` | Allowlisted | `advanced` | Auto-unstick confidence gate is low-level detector recovery tuning. | Expose in expert mode with safeguards. |
| `processor.auto_unstick_min_confidence_binary_bird` | Allowlisted | `advanced` | Bird-specific auto-unstick confidence gate is low-level detector recovery tuning. | Expose in expert mode with safeguards. |
| `processor.auto_unstick_no_track_frames` | Allowlisted | `advanced` | Auto-unstick no-track frame threshold is low-level tracker recovery tuning. | Expose in expert mode with safeguards. |
| `processor.auto_unstick_tracker` | Allowlisted | `advanced` | Auto-unstick day tracker profile is low-level recovery policy. | Expose in expert mode with profile presets. |
| `processor.auto_unstick_tracker_night` | Allowlisted | `advanced` | Auto-unstick night tracker profile is low-level recovery policy. | Expose in expert mode with profile presets. |
| `processor.behavior_recognition.confidence_review_threshold` | UI | `-` | - | - |
| `processor.behavior_recognition.confidence_store_min` | UI | `-` | - | - |
| `processor.behavior_recognition.enabled` | UI | `-` | - | - |
| `processor.behavior_recognition.inference_backend` | UI | `-` | - | - |
| `processor.behavior_recognition.max_runtime_detections` | UI | `-` | - | - |
| `processor.behavior_recognition.openvino_fallback_logistic` | UI | `-` | - | - |
| `processor.behavior_recognition.weights_path` | UI | `-` | - | - |
| `processor.binary_imgsz` | UI | `-` | - | - |
| `processor.binary_track_iou` | Allowlisted | `advanced` | Binary detector tracker IoU threshold is low-level tracking parameter. | Expose in expert tracker section with validation. |
| `processor.binary_track_max_det` | Allowlisted | `advanced` | Binary detector max detections per frame is low-level performance/safety tuning. | Expose in expert tracker section with validation. |
| `processor.bird_skip_classifier_max_area_frac` | UI | `-` | - | - |
| `processor.birdnet_fifo_hearing_active_hours` | UI | `-` | - | - |
| `processor.birdnet_fifo_persist_enabled` | UI | `-` | - | - |
| `processor.birdnet_fifo_snapshot_enabled` | UI | `-` | - | - |
| `processor.birdnet_fifo_snapshot_interval_sec` | UI | `-` | - | - |
| `processor.birdnet_fifo_snapshot_recent_limit` | UI | `-` | - | - |
| `processor.birdnet_fifo_snapshot_stale_sec` | UI | `-` | - | - |
| `processor.birdnet_fifo_sqlite_busy_ms` | UI | `-` | - | - |
| `processor.birdnet_mqtt_auto_confidence` | UI | `-` | - | - |
| `processor.birdnet_mqtt_bias_delta` | UI | `-` | - | - |
| `processor.birdnet_mqtt_bias_floor` | UI | `-` | - | - |
| `processor.birdnet_mqtt_bias_window_seconds` | UI | `-` | - | - |
| `processor.birdnet_mqtt_observability_debug` | UI | `-` | - | - |
| `processor.birdnet_mqtt_observability_level` | UI | `-` | - | - |
| `processor.birdnet_mqtt_prior_half_life_hours` | UI | `-` | - | - |
| `processor.birdnet_mqtt_prior_min_confidence` | UI | `-` | - | - |
| `processor.birdnet_mqtt_prior_ttl_hours` | UI | `-` | - | - |
| `processor.birdnet_mqtt_prior_window_hours` | UI | `-` | - | - |
| `processor.blur_threshold` | UI | `-` | - | - |
| `processor.classification_scheduler` | UI | `-` | - | - |
| `processor.classifier_fallback_bird` | UI | `-` | - | - |
| `processor.classifier_inference_backend` | UI | `-` | - | - |
| `processor.classifier_inference_device` | UI | `-` | - | - |
| `processor.classifier_uncertainty_entropy_ge` | UI | `-` | - | - |
| `processor.classifier_uncertainty_margin_le` | UI | `-` | - | - |
| `processor.dataset_min_confidence` | UI | `-` | - | - |
| `processor.detection_strategy` | UI | `-` | - | - |
| `processor.detector_scope` | UI | `-` | - | - |
| `processor.detector_weight_contract` | UI | `-` | - | - |
| `processor.ebird_regional_top_auto_confidence` | UI | `-` | - | - |
| `processor.ebird_regional_top_confidence_delta` | UI | `-` | - | - |
| `processor.ebird_regional_top_confidence_floor` | UI | `-` | - | - |
| `processor.file_max_record_floor_seconds` | UI | `-` | - | - |
| `processor.frame_processing_warn_ms` | UI | `-` | - | - |
| `processor.frigate_activity_hold_seconds` | UI | `-` | - | - |
| `processor.generate_spectrogram_always` | UI | `-` | - | - |
| `processor.generic_bird_min_area_frac` | UI | `-` | - | - |
| `processor.generic_bird_min_best_frame_score` | UI | `-` | - | - |
| `processor.generic_bird_min_detector_conf` | UI | `-` | - | - |
| `processor.generic_bird_min_frames` | UI | `-` | - | - |
| `processor.generic_rodent_max_area_frac` | Allowlisted | `ops-only` | Reject rodent fallbacks that look like full-frame detector artifacts. | Consider expert UI once rollout baselines are collected. |
| `processor.generic_rodent_min_best_frame_score` | Allowlisted | `ops-only` | Rodent fallback visual-quality gate tied to best-frame sharpness. | Keep YAML-only pending multi-camera calibration. |
| `processor.generic_rodent_min_frames` | Allowlisted | `ops-only` | Rodent fallback quality gate; sensitive anti-noise tuning. | Keep YAML-only until rodent false-positive profile stabilizes. |
| `processor.included_bird_families` | UI | `-` | - | - |
| `processor.inference_backend` | UI | `-` | - | - |
| `processor.inference_device` | UI | `-` | - | - |
| `processor.inference_lores_px` | UI | `-` | - | - |
| `processor.iou_id_fallback_live_enabled` | Allowlisted | `advanced` | Live IoU ID fallback is low-level identity continuity logic. | Expose in expert mode with explanatory diagnostics. |
| `processor.iou_id_fallback_live_match_threshold` | Allowlisted | `advanced` | Live IoU ID fallback match threshold is low-level identity continuity tuning. | Expose in expert mode with explanatory diagnostics. |
| `processor.keep_recording_when_no_detections` | UI | `-` | - | - |
| `processor.key_frame_limit` | UI | `-` | - | - |
| `processor.letterbox_resize_interpolation` | Allowlisted | `ops-only` | Letterbox interpolation method affects inference image preprocessing internals. | Keep YAML-only unless benchmarking UI is introduced. |
| `processor.light_gate_enabled` | UI | `-` | - | - |
| `processor.light_gate_min_brightness` | UI | `-` | - | - |
| `processor.light_gate_min_contrast` | UI | `-` | - | - |
| `processor.max_blur_checks` | UI | `-` | - | - |
| `processor.max_box_area_norm` | Allowlisted | `ops-only` | Detector anti-collapse guardrail for near full-frame boxes. | Potential expert UI field with diagnostics preview after validation. |
| `processor.max_classifications_per_frame` | UI | `-` | - | - |
| `processor.max_inactive_seconds` | UI | `-` | - | - |
| `processor.max_record_seconds` | UI | `-` | - | - |
| `processor.min_box_size_px` | UI | `-` | - | - |
| `processor.min_center_dist` | UI | `-` | - | - |
| `processor.min_confidence_binary` | UI | `-` | - | - |
| `processor.min_confidence_binary_bird` | UI | `-` | - | - |
| `processor.min_confidence_binary_rodent` | UI | `-` | - | - |
| `processor.min_confidence_to_notify` | UI | `-` | - | - |
| `processor.min_confidence_to_process` | UI | `-` | - | - |
| `processor.min_seconds_between_recordings` | UI | `-` | - | - |
| `processor.min_track_duration` | UI | `-` | - | - |
| `processor.models.behavior_openvino` | Allowlisted | `ops-only` | Behavior OpenVINO bundle path is deployment-specific. | Same policy as binary_openvino; not in Settings form. |
| `processor.models.binary` | Allowlisted | `ops-only` | Model path is environment/deployment-specific. | Upload/reset via System → Processor weights (#276); not in Settings form. |
| `processor.models.binary_openvino` | Allowlisted | `ops-only` | OpenVINO detector bundle path is deployment-specific and managed server-side. | Keep hidden from Settings form; surface only backend selector in UI. |
| `processor.models.classifier` | Allowlisted | `ops-only` | Model path is environment/deployment-specific. | Upload/reset via System → Processor weights (#276); not in Settings form. |
| `processor.models.classifier_openvino` | Allowlisted | `ops-only` | OpenVINO classifier bundle path is deployment-specific and managed server-side. | Keep hidden from Settings form; surface only backend selector in UI. |
| `processor.multi_camera_confidence_boost` | UI | `-` | - | - |
| `processor.multi_camera_groups` | UI | `-` | - | - |
| `processor.post_record_seconds` | UI | `-` | - | - |
| `processor.readiness_heartbeat_max_age_seconds` | Allowlisted | `ops-only` | Readiness gate threshold for processor heartbeat freshness; deployment/ops tuning. | YAML-only; reflected in /api/ui/readiness payload. |
| `processor.regional_species` | UI | `-` | - | - |
| `processor.reid_cross_camera_threshold_boost` | Allowlisted | `ops-only` | Risk control for cross-folder/camera collisions using video_path heuristics. | Replace heuristic with explicit camera_id once available end-to-end. |
| `processor.reid_default_similarity_threshold` | Allowlisted | `ops-only` | Cosine gate depends on embedding contract + species; unsafe as casual slider. | Preset tables + per-site calibration workflow (#390). |
| `processor.reid_different_similarity_threshold` | Allowlisted | `ops-only` | Lower bound for inconclusive decisions; tightly coupled to embeddings noise. | Same as reid_default_similarity_threshold. |
| `processor.reid_embedding_pipeline_mode` | Allowlisted | `ops-only` | Embedding generation runs out-of-band; mode is informational + policy input. | Expose as read-only status + pilot toggle after nearline worker (#389). |
| `processor.reid_kill_switch` | Allowlisted | `ops-only` | Emergency disable for suggestions without dropping embeddings. | Same as reid_suggestions_enabled. |
| `processor.reid_max_embedding_age_hours` | Allowlisted | `ops-only` | Staleness gate for offline refresh cadence. | Automate refresh jobs + show stale age in System card (#389). |
| `processor.reid_shadow_mode` | Allowlisted | `ops-only` | Production shadow evaluation without user-facing hints. | Pair with metrics dashboard before UI surfacing. |
| `processor.reid_suggestions_enabled` | Allowlisted | `ops-only` | Safety switch for similarity hints; needs ops discipline. | Move to System → ML after UX review queue lands (#390). |
| `processor.save_dataset_crops` | UI | `-` | - | - |
| `processor.save_images` | UI | `-` | - | - |
| `processor.spectrogram_px_per_sec` | UI | `-` | - | - |
| `processor.track_regen_detection_strategy` | UI | `-` | - | - |
| `processor.track_regen_frame_step` | UI | `-` | - | - |
| `processor.track_regen_ignore_regional_species` | UI | `-` | - | - |
| `processor.track_regen_iou_id_fallback` | UI | `-` | - | - |
| `processor.track_regen_iou_match_threshold` | UI | `-` | - | - |
| `processor.track_regen_lores_px` | UI | `-` | - | - |
| `processor.track_regen_match_live_pipeline` | UI | `-` | - | - |
| `processor.track_regen_min_track_duration` | Allowlisted | `advanced` | Track regeneration minimum track duration is batch-regeneration tuning. | Expose under System track regeneration advanced controls. |
| `processor.track_regen_parallel_auto_with_manual` | UI | `-` | - | - |
| `processor.track_regen_precise_detection_strategy` | UI | `-` | - | - |
| `processor.track_regen_precise_min_center_dist` | UI | `-` | - | - |
| `processor.track_regen_precise_timeout_sec` | UI | `-` | - | - |
| `processor.track_regen_serialize_inference` | Allowlisted | `advanced` | Track regeneration inference serialization is batch performance tuning. | Expose under System track regeneration advanced controls. |
| `processor.track_regen_serialize_inference_interprocess` | Allowlisted | `advanced` | Interprocess serialization for regeneration inference is batch performance tuning. | Expose under System track regeneration advanced controls. |
| `processor.track_regen_video_timeout_sec` | UI | `-` | - | - |
| `processor.track_to_predict_fallback_confidence` | Allowlisted | `advanced` | Track-to-predict fallback confidence gate is low-level inference fallback tuning. | Expose in expert mode with diagnostics. |
| `processor.track_to_predict_fallback_enabled` | Allowlisted | `advanced` | Track-to-predict fallback switch is low-level inference fallback tuning. | Expose in expert mode with diagnostics. |
| `processor.tracker` | UI | `-` | - | - |
| `processor.tracker_profiles.night` | Allowlisted | `advanced` | Nested tracker profile object for low-light tuning is expert-level and high-risk for misconfiguration. | Expose through dedicated tracker profile editor with validation. |
| `processor.ultra_weak_box_salvage_enabled` | Allowlisted | `advanced` | Ultra-weak box salvage is emergency detector recovery logic. | Expose only in expert mode with warnings. |
| `processor.ultra_weak_box_salvage_max_candidates` | Allowlisted | `advanced` | Ultra-weak salvage candidate cap is low-level recovery tuning. | Expose only in expert mode with warnings. |
| `processor.ultra_weak_box_salvage_min_confidence` | Allowlisted | `advanced` | Ultra-weak salvage confidence gate is low-level recovery tuning. | Expose only in expert mode with warnings. |
| `retention.batch_size` | Allowlisted | `library-ui` | Batch size for retention API; YAML + read-only summary on Library retention card. | Keep Library card / YAML. |
| `retention.dataset_max_age_days` | Allowlisted | `library-ui` | Dataset TTL for retention; YAML + read-only summary on Library retention card. | Keep Library card / YAML. |
| `retention.days` | Allowlisted | `library-ui` | Retention knobs are shown and run from Library → Database maintenance (RetentionPolicy), not Settings forms. | Optional: mirror in Settings later; single UX entry is Library card. |
| `retention.migration_max_age_days` | Allowlisted | `library-ui` | Migration history TTL; YAML + read-only summary on Library retention card. | Keep Library card / YAML. |
| `retention.min_age_hours` | Allowlisted | `library-ui` | Grace period for retention; YAML + read-only summary on Library retention card. | Keep Library card / YAML. |
| `retention.mode` | Allowlisted | `library-ui` | Retention run mode override lives next to dry-run/apply on Library maintenance card. | Keep Library as single UX entry unless Settings parity is required. |
| `retention.protect_favorites` | Allowlisted | `library-ui` | Safety flag for retention; YAML + read-only summary on Library retention card. | Keep Library card / YAML. |
| `secrets.ebird_api_key` | UI | `-` | - | - |
| `secrets.latitude` | UI | `-` | - | - |
| `secrets.longitude` | UI | `-` | - | - |
| `secrets.openweather_api_key` | UI | `-` | - | - |
| `secrets.xeno_canto_api_key` | UI | `-` | - | - |
| `species.catalog_allowlist_file` | Allowlisted | `yaml-only` | Path to classifier class list is deployment/repo layout; not configured in Settings. | Keep in user_config.yaml or defaults. |
| `species.catalog_strict_ingest` | UI | `-` | - | - |
| `species.tuning_target_species_ids` | UI | `-` | - | - |
| `storage.recordings_mirror.delete_local_after_success` | Allowlisted | `library-ui` | Expert destructive option on NAS mirror card. | Keep expert-only on Library/System card. |
| `storage.recordings_mirror.enabled` | Allowlisted | `library-ui` | Edited in Library → Storage (NAS mirror card); processor reads after restart. | Keep Library/System as single UX entry. |
| `storage.recordings_mirror.host` | Allowlisted | `library-ui` | Mirror host on NAS mirror card. | Keep Library/System card. |
| `storage.recordings_mirror.known_hosts_path` | Allowlisted | `library-ui` | Optional known_hosts path on NAS mirror card. | Keep Library/System card. |
| `storage.recordings_mirror.max_concurrent_uploads` | Allowlisted | `library-ui` | Processor concurrency; advanced on NAS mirror card / YAML. | Optional Settings advanced later. |
| `storage.recordings_mirror.port` | Allowlisted | `library-ui` | SFTP port on NAS mirror card. | Keep Library/System card. |
| `storage.recordings_mirror.protocol` | Allowlisted | `library-ui` | SFTP-only today; exposed on NAS mirror card, not Settings. | Keep Library/System card. |
| `storage.recordings_mirror.remote_base_path` | Allowlisted | `library-ui` | Remote base path on NAS mirror card. | Keep Library/System card. |
| `storage.recordings_mirror.retry_backoff_seconds` | Allowlisted | `library-ui` | Backoff on NAS mirror card / YAML. | Keep Library/System card. |
| `storage.recordings_mirror.sftp_key_passphrase` | Allowlisted | `library-ui` | Key passphrase on NAS mirror card. | Keep Library/System card. |
| `storage.recordings_mirror.sftp_password` | Allowlisted | `library-ui` | Secret on NAS mirror card; masked in settings API like other hub secrets. | Keep Library/System card. |
| `storage.recordings_mirror.ssh_private_key_path` | Allowlisted | `library-ui` | Optional key path on NAS mirror card. | Keep Library/System card. |
| `storage.recordings_mirror.strict_host_key` | Allowlisted | `library-ui` | Host key policy toggle on NAS mirror card. | Keep Library/System card. |
| `storage.recordings_mirror.upload_retries` | Allowlisted | `library-ui` | Retry count on NAS mirror card / YAML. | Keep Library/System card. |
| `storage.recordings_mirror.username` | Allowlisted | `library-ui` | SFTP user on NAS mirror card. | Keep Library/System card. |
| `system_metrics.cpu_sample_interval_seconds` | Allowlisted | `advanced` | CPU sampler interval for system metrics; low-level observability knob. | YAML-only or future System diagnostics UI. |
| `triggers.frigate.camera_filter` | UI | `-` | - | - |
| `triggers.frigate.enabled` | UI | `-` | - | - |
| `triggers.frigate.geometry_fallback_cooldown_seconds` | Allowlisted | `advanced` | Cooldown for Frigate geometry fallback path; anti-flap operator tuning. | YAML-only until Frigate trigger advanced panel exists. |
| `triggers.frigate.geometry_fallback_enabled` | UI | `-` | - | - |
| `triggers.frigate.geometry_fallback_label_exclude` | UI | `-` | - | - |
| `triggers.frigate.label_exclude` | UI | `-` | - | - |
| `triggers.frigate.label_filter` | UI | `-` | - | - |
| `triggers.frigate.min_trigger_score` | UI | `-` | - | - |
| `triggers.frigate.topic` | UI | `-` | - | - |
| `triggers.frigate.trigger_on_tracked_object` | UI | `-` | - | - |
| `triggers.motion_sensor.enabled` | UI | `-` | - | - |
| `triggers.motion_sensor.esphome_sensor_id` | UI | `-` | - | - |
| `triggers.motion_sensor.esphome_url` | UI | `-` | - | - |
| `triggers.motion_sensor.mqtt_topic` | UI | `-` | - | - |
| `triggers.motion_sensor.source` | UI | `-` | - | - |
| `triggers.opencv.check_every_n_frames` | UI | `-` | - | - |
| `triggers.opencv.diff_threshold` | UI | `-` | - | - |
| `triggers.opencv.enabled` | UI | `-` | - | - |
| `triggers.opencv.min_contour_area` | UI | `-` | - | - |
| `triggers.scales.enabled` | UI | `-` | - | - |
| `triggers.scales.motion_trigger_debounce_seconds` | UI | `-` | - | - |
| `triggers.scales.motion_trigger_min_delta_kg` | UI | `-` | - | - |
| `triggers.scales.source` | Allowlisted | `derived` | Processor resolves scales trigger transport from integrations.scales.source when unset; duplicate source pickers were removed from Settings. | Re-expose only if product needs different MQTT/ESPHome paths for live weight vs weight-trigger sampling. |
| `ui.unknown_confidence_threshold` | UI | `-` | - | - |
| `video.auto_reconnect` | UI | `-` | - | - |
| `video.cameras` | UI | `-` | - | - |
| `video.capture_backend` | UI | `-` | - | - |
| `video.encoding` | UI | `-` | - | - |
| `video.file_dir` | Allowlisted | `library-ui` | Test clip folder; edited in Library file replay card. | Keep Library as single UX entry. |
| `video.file_loop` | Allowlisted | `library-ui` | Default playlist loop for file mode; set in Library when enabling replay. | Keep Library as single UX entry. |
| `video.file_path` | Allowlisted | `yaml-only` | Absolute path to test mp4 is deployment-specific; not edited in Settings (Library / YAML). | Keep out of Settings form. |
| `video.file_realtime_simulation` | UI | `-` | - | - |
| `video.file_test_max_upload_mb` | Allowlisted | `library-ui` | Hub upload size cap for Library file replay; tunable in YAML. | Optional expose in Library advanced later. |
| `video.go2rtc_password` | UI | `-` | - | - |
| `video.go2rtc_url` | UI | `-` | - | - |
| `video.go2rtc_username` | UI | `-` | - | - |
| `video.pre_record_seconds` | UI | `-` | - | - |
| `video.record_stream_codec` | UI | `-` | - | - |
| `video.source` | Allowlisted | `library-ui` | go2rtc vs file replay; toggled in Library (PATCH), not Settings form. | Single entry: Library → file replay. |
| `video.video_height` | UI | `-` | - | - |
| `video.video_width` | UI | `-` | - | - |
| `weather.ha_entity_id` | UI | `-` | - | - |
| `weather.source` | UI | `-` | - | - |
| `web_push.enabled` | Allowlisted | `backend-managed` | Derived by backend from subscriptions. | Keep backend-managed. |
| `web_push.vapid_private_key` | Allowlisted | `backend-managed` | Secret generated/managed by backend. | Keep backend-managed. |
| `web_push.vapid_public_key` | Allowlisted | `backend-managed` | Generated/managed by backend. | Keep backend-managed. |
| `webhook.url` | UI | `-` | - | - |
