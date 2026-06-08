import type { components } from './generated/openapi-types';

export interface SpeciesVisit {
  id: number;
  start_time: string;
  end_time: string;
  max_simultaneous: number;
  /** visit — обычный визит; unlinked_video — ролик за день без SpeciesVisit (показывается на таймлайне). */
  timeline_kind?: 'visit' | 'unlinked_video';
  /** Сумма длительностей всех детекций (записей) в событии, секунды */
  total_recording_seconds?: number;
  /** Длительность файла записи (как на странице видео), секунды */
  video_duration_seconds?: number | null;
  weather?: {
    temp?: number;
    clouds?: number;
  };
  /** Дельта весов за ролик (как на странице видео); снимок с «основного» ролика визита (самый ранний по start_time). */
  scales?: {
    delta_kg: number;
    display_value: number;
    display_unit: 'kg' | 'g';
    weight_change_grams?: number;
    weight_trend?: 'up' | 'down' | 'stable';
  } | null;
  species: {
    id: number;
    name: string;
    /** Relative path (data/images/...) or full URL (Wikipedia) — use resolveImageUrl() */
    image_url?: string;
    parent_id?: number;
  };
  detections: {
    id?: number;
    video_id: number;
    start_time: string;
    end_time: string;
    confidence: number;
    source: 'video' | 'audio';
    detection_provider?: string;
    individual_nickname?: string | null;
    bird_profile_id?: number | null;
  }[];
  /** Re-ID nickname from backend visit payload when present (#390 UI). */
  individual_nickname?: string | null;
  bird_profile_id?: number | null;
  /** Model-derived behavior events for this visit. */
  behavior_events?: { label?: string }[];
  /** Trigger semantics for timeline filtering (opencv/frigate/motion_sensor/scales/unknown). */
  trigger_source?: string;
  /** Hub camera id (video.cameras[].id) when known. */
  camera_id?: string | null;
}

export interface TrackFrame {
  t: number; // Time in seconds from video start
  bbox: number[]; // Normalized [x1, y1, x2, y2]
}

export interface VideoSpecies {
  id?: number;
  species_id: number;
  species_name: string;
  track_id?: number;
  start_time: number;
  end_time: number;
  confidence: number;
  source: string;
  detection_provider?: string;
  individual_nickname?: string | null;
  bird_profile_id?: number | null;
  bird_profile_name?: string | null;
  bird_profile_avatar_url?: string | null;
  bird_profile_status?: string | null;
  classifier_needs_review?: boolean;
  review_reason?: string | null;
  classifier_entropy?: number | null;
  classifier_top1_top2_margin?: number | null;
  scoring_hint?: {
    primary_provider?: string;
    confidence?: number;
    source?: string;
    weighted_arbiter_enabled?: boolean;
    arbiter_weights?: Record<string, number>;
    needs_review?: boolean;
    review_reason?: string | null;
  };
  semantic_conflict?: boolean;
  semantic_review_history?: Array<{
    at?: string | null;
    source?: string | null;
    note?: string | null;
  }>;
  /** Relative path or full URL — use resolveImageUrl() */
  image_url?: string;
  frames?: TrackFrame[];
}

export interface Weather {
  main: string;
  description: string;
  temp: number;
  humidity: number;
  pressure: number;
  clouds: number;
  wind_speed: number;
  source?: 'openweather' | 'homeassistant' | string;
  fetched_at?: string;
}

export interface Video {
  id: string;
  processor_version: string;
  start_time: string;
  end_time: string;
  video_path: string;
  favorite: boolean;
  weather: Weather;
  species: VideoSpecies[];
  food: {
    id: string;
    name: string;
    /** Relative path (data/images/food/...) or null — use resolveImageUrl() */
    image_url: string | null;
  }[];
  /** Оценка дельты на весах за ролик (#167); null если нет данных */
  scales?: {
    delta_kg: number;
    display_value: number;
    display_unit: 'kg' | 'g';
    weight_change_grams?: number;
    weight_trend?: 'up' | 'down' | 'stable';
  } | null;
  behavior_label?: string | null;
  behavior_confidence?: number | null;
  behavior_model_kind?: string | null;
  behavior_model_version?: string | null;
  behavior_shadow_label?: string | null;
  behavior_shadow_confidence?: number | null;
  behavior_shadow_model_kind?: string | null;
  behavior_shadow_model_version?: string | null;
}

/** См. OpenAPI `BirdFood`; для списка из API поля id/name/active приходят заполненными. */
export type BirdFood = components['schemas']['BirdFood'] & {
  id: number;
  name: string;
  active: boolean;
};

export interface BirdTaxonomy {
  id: string;
  commonName: string;
  scientificName: string;
  family: string;
  order: string;
  imageUrl: string;
  preferredFood: string[];
  description: string;
  isCommonVisitor: boolean;
}

/** Ночной / low-light: override полей процессора при срабатывании профиля. */
export type ProcessorNightProfileOverrides = {
  light_gate_min_brightness?: number;
  light_gate_min_contrast?: number;
  min_confidence_binary?: number;
  min_confidence_binary_bird?: number;
  min_confidence_binary_rodent?: number;
  /** Только OpenVINO: нижняя страховка для ``track(conf)`` (см. detection_strategy). */
  openvino_binary_track_ultralytics_conf?: number | null;
  /** Только OpenVINO: множитель conf Bird при сравнении с порогом; сырая conf в данных не меняется. */
  openvino_binary_bird_score_scale?: number | null;
  /** Только OpenVINO: подмена порога Bird (null = как min_confidence_binary_bird). */
  openvino_min_confidence_binary_bird?: number | null;
  /** @deprecated см. min_confidence_binary_rodent */
  min_confidence_binary_squirrel?: number;
  min_track_duration?: number;
  min_confidence_to_process?: number;
  min_box_size_px?: number;
  min_center_dist?: number;
  max_classifications_per_frame?: number;
};

export type ProcessorAdaptiveProfiles = {
  enabled?: boolean;
  night?: {
    max_brightness?: number;
    max_contrast?: number;
    overrides?: ProcessorNightProfileOverrides;
  };
};

export interface Settings {
  general: {
    enable_notifications: boolean;
    notification_excluded_species: string[];
    /** Требовать сессию для прямого MJPEG/потока (см. конфиг). */
    require_auth_for_video_stream?: boolean;
    settings_password?: string;
    contributor_password?: string;
    /** Minutes without /api/* before login session clears; 0 = off. Default 30. */
    session_idle_minutes?: number;
    birdnet_url?: string; // URL to BirdNET installation; empty = no icon in UI
    /** URL донатов: одна иконка в шапке; поле задаётся здесь же в «Общие» */
    donate_url?: string;
  };
  performance?: {
    cache_redis_enabled?: boolean;
    redis_url?: string;
    /** Только ответ GET /settings: фактический URL кэша (пароль замаскирован), не сохранять */
    redis_url_effective_masked?: string;
  };
  /** Home Assistant REST API: общий URL и токен для погоды, весов (HA entity) и др. */
  homeassistant?: {
    url?: string;
    token?: string;
  };
  integrations?: {
    birdnet?: {
      mqtt_topic?: string;
    };
    scales?: {
      enabled?: boolean;
      source?: 'mqtt' | 'esphome' | 'homeassistant';
      mqtt_topic?: string;
      mqtt_bird_present_topic?: string;
      mqtt_topic_prefix?: string;
      mqtt_command_topic?: string;
      mqtt_tare_payload?: string;
      esphome_url?: string;
      esphome_weight_sensor_id?: string;
      esphome_bird_present_sensor_id?: string;
      esphome_tare_button_id?: string;
      homeassistant_entity_id?: string;
      unit?: 'kg' | 'g';
      weight_estimate_enabled?: boolean;
      estimate_require_consecutive_spike?: boolean;
      motion_trigger_enabled?: boolean;
      motion_trigger_min_delta_kg?: number;
      motion_trigger_debounce_seconds?: number;
      min_delta_kg_for_estimate?: number;
      history_max_lines?: number;
    };
  };
  processor: {
    tracker: string; // Path to tracker config, e.g., "bytetrack.yaml"
    max_record_seconds: number; // Max recording duration in seconds
    /** Post-roll seconds added to inactivity gap before stop (#157). */
    post_record_seconds?: number;
    max_inactive_seconds: number; // Max inactivity before stopping recording
    /** Пауза после конца записи до следующего старта (сек). */
    min_seconds_between_recordings?: number;
    /** Нижняя граница max_record_seconds в режиме file + плейлист. */
    file_max_record_floor_seconds?: number;
    /** Удержание сессии при свежих событиях Frigate без YOLO на паре кадров. */
    frigate_activity_hold_seconds?: number;
    min_track_duration?: number; // Min track duration (sec) for ByteTrack; shorter tracks discarded
    min_confidence_binary?: number; // Binary detector threshold (bird vs no-bird); 0.25 = stricter
    /** Строже только для боксов Bird. null / пусто в UI → как min_confidence_binary. */
    min_confidence_binary_bird?: number | null;
    openvino_binary_track_ultralytics_conf?: number | null;
    openvino_binary_bird_score_scale?: number | null;
    openvino_min_confidence_binary_bird?: number | null;
    /** Мягче для Rodent (грызуны). null → как min_confidence_binary. */
    min_confidence_binary_rodent?: number | null;
    /** @deprecated Используйте min_confidence_binary_rodent; читается из YAML для совместимости */
    min_confidence_binary_squirrel?: number | null;
    /** Bird с площадью bbox ≤ доли кадра — без species classifier; null/0 = выкл. */
    bird_skip_classifier_max_area_frac?: number | null;
    min_confidence_to_process?: number; // Min combined confidence (voting × classifier); 0.15 = stricter
    /** Min confidence to send Telegram photo notification (defaults to min_confidence_to_process if unset). */
    min_confidence_to_notify?: number;
    min_box_size_px?: number; // Minimum bbox width/height in pixels for detector candidates
    detector_scope?: string[]; // First-stage detector targets, e.g. ["Bird", "Rodent"]
    /** If false, run YOLO on every frame (ignore brightness/contrast gate). */
    light_gate_enabled?: boolean;
    light_gate_min_brightness?: number;
    light_gate_min_contrast?: number;
    species_confidence_overrides?: Record<string, number>; // Per-species thresholds (rare species — lower)
    /** Lower classifier threshold for eBird regional top species (#128); manual overrides win */
    ebird_regional_top_auto_confidence?: boolean;
    ebird_regional_top_confidence_delta?: number;
    ebird_regional_top_confidence_floor?: number;
    /** BirdNET affects classifier confidence only; does not create video labels directly. */
    birdnet_mqtt_auto_confidence?: boolean;
    birdnet_mqtt_bias_delta?: number;
    birdnet_mqtt_bias_floor?: number;
    /** Frigate camera id groups at one location (IDs match Video → Cameras). */
    multi_camera_groups?: string[][];
    multi_camera_confidence_boost?: number;
    save_dataset_crops?: boolean;
    dataset_min_confidence?: number;
    classifier_fallback_bird?: boolean; // Keep generic detector label when classifier stays uncertain
    included_bird_families: string[]; // List of bird families to use in detections
    adaptive_profiles?: ProcessorAdaptiveProfiles;
    frame_processing_warn_ms?: number;
    inference_lores_px?: number;
    inference_lores_wh?: [number, number];
    detect_use_native_resolution?: boolean;
    detection_quality_assumed_fps?: number;
    binary_imgsz?: number;
    background_subtraction_enabled?: boolean;
    background_subtraction_history?: number;
    background_subtraction_var_threshold?: number;
    background_subtraction_min_fg_ratio?: number;
    background_subtraction_warmup_frames?: number;
    background_subtraction_detect_shadows?: boolean;
    static_object_suppression_enabled?: boolean;
    static_scene_bird_min_confidence?: number;
    static_temporal_max_jitter_px?: number;
    classification_scheduler?: string;
    max_classifications_per_frame?: number;
    max_blur_checks?: number;
    blur_threshold?: number;
    min_center_dist?: number;
    regional_species?: string[];
    generic_bird_min_detector_conf?: number;
    generic_bird_min_frames?: number;
    generic_bird_min_area_frac?: number;
    generic_bird_min_best_frame_score?: number;
    key_frame_limit?: number;
    keep_recording_when_no_detections?: boolean;
    detection_strategy?: string;
    inference_backend?: 'auto' | 'torch' | 'openvino' | 'onnxruntime' | string;
    classifier_inference_backend?:
      | 'auto'
      | 'torch'
      | 'openvino'
      | 'onnxruntime'
      | string;
    inference_device?: string;
    classifier_inference_device?: string;
    detector_weight_contract?: 'off' | 'warn' | 'enforce' | string;
    models?: {
      binary?: string;
      binary_openvino?: string;
      classifier?: string;
      classifier_openvino?: string;
      behavior_openvino?: string;
    };
    classifier_uncertainty_entropy_ge?: number | null;
    classifier_uncertainty_margin_le?: number | null;
    save_images?: boolean;
    birdnet_mqtt_prior_window_hours?: number;
    birdnet_mqtt_bias_window_seconds?: number;
    birdnet_mqtt_prior_ttl_hours?: number;
    birdnet_mqtt_prior_half_life_hours?: number;
    birdnet_mqtt_prior_min_confidence?: number;
    birdnet_mqtt_observability_level?: string;
    birdnet_mqtt_observability_debug?: boolean;
    birdnet_fifo_snapshot_enabled?: boolean;
    birdnet_fifo_snapshot_interval_sec?: number;
    birdnet_fifo_snapshot_recent_limit?: number;
    birdnet_fifo_snapshot_stale_sec?: number;
    birdnet_fifo_hearing_active_hours?: number;
    birdnet_fifo_persist_enabled?: boolean;
    birdnet_fifo_sqlite_busy_ms?: number;
    track_regen_frame_step?: number;
    track_regen_detection_strategy?: string;
    track_regen_lores_px?: number;
    track_regen_lores_wh?: [number, number];
    track_regen_binary_only?: boolean;
    track_regen_iou_id_fallback?: boolean;
    track_regen_iou_match_threshold?: number | null;
    track_regen_video_timeout_sec?: number;
    track_regen_precise_timeout_sec?: number;
    track_regen_precise_detection_strategy?: string;
    track_regen_precise_min_center_dist?: number;
    track_regen_ignore_regional_species?: boolean;
    track_regen_match_live_pipeline?: boolean;
    track_regen_parallel_auto_with_manual?: boolean;
    /** Lores YOLO gate before main-stream record (go2rtc). */
    detect_first_enabled?: boolean;
    detect_first_window_seconds?: number;
    detect_first_max_frames?: number;
    detect_first_confirm_min_hits?: number;
    detect_first_confirm_min_track_seconds?: number;
    /** Per-camera id → processor field overrides (win over tuning_role preset). */
    camera_overrides?: Record<string, Record<string, unknown>>;
    /** Role presets referenced by video.cameras[].tuning_role. */
    camera_tuning_by_role?: Record<string, Record<string, unknown>>;
    max_box_area_norm?: number;
    scoring_giant_box_area_frac?: number;
    detect_record_time_offset_sec?: number;
    notify_preview_source?: 'auto' | 'record_hires' | 'best_frame_lores' | string;
    notify_preview_crop_pad_frac?: number;
    track_static_reject_enabled?: boolean;
    track_static_reject_min_duration_sec?: number;
    track_static_reject_min_frames?: number;
    scoring_moving_roi_review_enabled?: boolean;
    scoring_moving_roi_min_motion_score?: number;
    linear_live_scoring_engine_enabled?: boolean;
    behavior_recognition?: {
      enabled?: boolean;
      weights_path?: string;
      inference_backend?: 'auto' | 'logistic_json' | 'openvino' | string;
      openvino_fallback_logistic?: boolean;
      max_runtime_detections?: number;
      confidence_store_min?: number;
      confidence_review_threshold?: number;
    };
  };
  secrets: {
    openweather_api_key: string; // API key for OpenWeather
    xeno_canto_api_key?: string; // API key for Xeno-canto bird song playback
    ebird_api_key?: string; // API key for eBird regional comparison
    latitude: string; // Latitude as a string, e.g., "YOUR_LATITUDE_HERE"
    longitude: string; // Longitude as a string, e.g., "YOUR_LONGITUDE_HERE"
    zip?: string;
  };
  video?: {
    source?: 'go2rtc' | 'file' | string;
    pre_record_seconds?: number;
    auto_reconnect?: boolean;
    file_path?: string;
    file_dir?: string;
    file_loop?: boolean;
    file_realtime_simulation?: boolean;
    go2rtc_url?: string;
    stream_name?: string;
    cameras?: Array<{
      id?: string;
      stream_name?: string;
      /** Required when video.source=go2rtc: lores motion/YOLO; stream_name is main record. */
      detect_stream_name?: string;
      name?: string;
      /** Maps to processor.camera_tuning_by_role preset (feeder_close / feeder_far). */
      tuning_role?: string;
    }>;
    go2rtc_username?: string;
    go2rtc_password?: string;
    /** cpu | intel — VA-API vs CPU для записи (intel = уже H.264). */
    encoding?: string;
    /** При encoding=intel: true — h264_vaapi для файла записи; false — libx264 (стабильнее на части iGPU). */
    record_with_vaapi?: boolean;
    /** auto | opencv | ffmpeg_vaapi — live capture path for motion/detection. */
    capture_backend?: 'auto' | 'opencv' | 'ffmpeg_vaapi' | string;
    /** h264 | copy — перекодировать RTSP в H.264 для браузера или копировать веб-кодек как есть. */
    record_stream_codec?: 'h264' | 'copy' | string;
    video_width?: number;
    video_height?: number;
    /** 0 = auto/probe from stream (SOTA-02). */
    detect_fps?: number;
  };
  mqtt?: {
    broker?: string;
    port?: number;
    username?: string;
    password?: string;
    frigate_topic?: string;
    birdnet_topic?: string;
    publish_topic?: string;
    reconnect_min_delay?: number;
    reconnect_max_delay?: number;
    ha_discovery?: boolean;
  };
  notifications?: {
    telegram_bot_token?: string;
    telegram_chat_id?: string;
    base_url?: string;
    /** none | socks_http | mtproto */
    telegram_proxy_type?: string;
    telegram_proxy_url?: string;
    telegram_mtproto_host?: string;
    telegram_mtproto_port?: number;
    telegram_mtproto_secret?: string;
    telegram_api_id?: number;
    telegram_api_hash?: string;
    telegram_api_base?: string;
    telegram_timeout?: number;
    telegram_retries?: number;
    compress_photo_over_kb?: number;
    telegram_max_side_px?: number;
    message_thread_id?: string;
    disable_notification?: boolean;
    protect_content?: boolean;
    link_preview_large?: boolean;
    send_photo?: boolean;
    use_custom_emoji?: boolean;
    custom_emoji_id_bird?: string;
    custom_emoji_id_chipmunk?: string;
    custom_emoji_id_open_live?: string;
    paid_media_view_star_count?: number;
    paid_media_forward_star_count?: number;
  };
  weather?: {
    source?: 'openweather' | 'homeassistant';
    ha_entity_id?: string;
  };
  ebird?: {
    country?: string;
    state?: string;
    location_name?: string;
    protocol?: string;
    species_mapping?: Record<string, string>; // eBird name -> BirdLense name
  };
  species?: {
    catalog_allowlist_file?: string;
    catalog_strict_ingest?: boolean;
    tuning_target_species_ids?: number[];
  };
  feed?: {
    source?: string;
    duration_seconds?: number;
    mqtt_topic?: string;
    esphome_url?: string;
    esphome_switch_id?: string;
    esphome_type?: 'switch' | 'button';
  };
  motion?: {
    source?: 'opencv' | 'frigate' | 'mqtt' | 'esphome';
    check_every_n_frames?: number;
    opencv_diff_threshold?: number;
    opencv_min_contour_area?: number;
    frigate_min_trigger_score?: number;
    frigate_camera_filter?: string[];
    frigate_label_filter?: string[];
    frigate_label_exclude?: string[];
    /** Если метка не в фильтре, но у объекта в MQTT есть box — всё равно старт записи */
    frigate_trigger_on_tracked_object?: boolean;
    mqtt_topic?: string;
    esphome_url?: string;
    esphome_sensor_id?: string;
  };
  triggers?: {
    opencv?: {
      enabled?: boolean;
      detection_method?: 'frame_diff' | 'mog2' | 'hybrid' | string;
      mog2_var_threshold?: number;
      mog2_min_contour_area?: number;
      mog2_detect_shadows?: boolean;
      check_every_n_frames?: number;
      diff_threshold?: number;
      min_contour_area?: number;
    };
    frigate?: {
      enabled?: boolean;
      topic?: string;
      /** Мин. score события MQTT до старта записи (внешний детектор). */
      min_trigger_score?: number;
      camera_filter?: string[];
      label_filter?: string[];
      label_exclude?: string[];
      trigger_on_tracked_object?: boolean;
      geometry_fallback_enabled?: boolean;
      geometry_fallback_label_exclude?: string[];
      geometry_fallback_cooldown_seconds?: number;
    };
    motion_sensor?: {
      enabled?: boolean;
      source?: 'mqtt' | 'esphome';
      mqtt_topic?: string;
      esphome_url?: string;
      esphome_sensor_id?: string;
    };
    scales?: {
      enabled?: boolean;
      source?: 'mqtt' | 'esphome';
      motion_trigger_min_delta_kg?: number;
      motion_trigger_debounce_seconds?: number;
    };
  };
  detection?: {
    min_confidence_to_store?: number; // 0–1; детекции ниже не сохраняются (6% → 0.20)
    /** YOLO без треков, но Frigate прислал событие — сохранить визит по Frigate */
    frigate_standalone_when_no_yolo?: boolean;
    frigate_standalone_when_no_accepted_species?: boolean;
    frigate_standalone_min_score?: number;
    frigate_standalone_missing_score_fallback?: number;
    frigate_standalone_excluded_min_score?: number;
    frigate_standalone_excluded_missing_score_fallback?: number;
    frigate_standalone_notify?: boolean;
    /** Не создавать standalone/review-only строки из MQTT по этим лейблам (person, car, …). */
    frigate_standalone_skip_labels?: string[];
    frigate_trigger_review_salvage_enabled?: boolean;
    frigate_trigger_review_salvage_allow_without_yolo_tracks?: boolean;
    merge_window_seconds?: number;
    dedup_window_seconds?: number;
    one_per_species?: boolean;
    cross_source_confidence_bonus?: number;
    /** Доп. калибровка confidence после rule-based fusion (FusionScorer). */
    use_learned_fusion?: boolean;
    fusion_model_path?: string;
    fusion_alpha?: number;
    absorb_generic_bird?: boolean;
    absorb_generic_bird_overlap_min_sec?: number;
    absorb_generic_bird_min_classifier_confidence?: number;
  };
  mcp?: {
    enabled?: boolean;
    token?: string;
    api_url?: string;
  };
  webhook?: {
    url?: string; // POST при детекции (IFTTT, Zapier)
  };
  ui?: {
    unknown_confidence_threshold?: number; // 0–1; детекции ниже попадают в «Неизвестные»
  };
}

export interface Species {
  id: number;
  name: string;
  parent_id: number | null;
  parent?: {
    name: string;
    id: string;
  };
  created_at: string;
  /** Relative path or full URL (Wikipedia) — use resolveImageUrl() */
  image_url: string | null;
  description: string | null;
  metadata_source?: string | null;
  metadata_source_url?: string | null;
  active: boolean;
  /** eBird regional top ∪ BirdNET-heard (Bird Directory filter). */
  regional_scope?: boolean;
  count?: number;
  /** Allowlist card missing photo/description (species-directory API). */
  catalog_card_incomplete?: boolean;
}

export interface OverviewTopSpecies {
  id: number;
  name: string;
  detections: number[]; // hourly visit counts (24), legacy field name
  /** Generic Bird/Rodent from detector — not a named SpeciesVisit */
  unidentified?: boolean;
}

export interface OverviewStats {
  uniqueSpecies: number;
  /** Named-species visit count (SpeciesVisit rows) */
  totalDetections: number;
  /** Visits overlapping the last hour (named + unidentified segments) */
  lastHourDetections: number;
  /** YOLO/MQTT segments labeled generic Bird */
  unidentifiedBirdDetections?: number;
  /** Detector segments labeled Rodent */
  rodentDetections?: number;
  /** Named visits + unidentified bird + rodent segments */
  totalActivity?: number;
  videoDuration: number;
  audioDuration: number;
  busiestHour: number;
  avgVisitDuration: number;
  detectionByProvider?: Record<string, number>;
  triggerBySource?: Record<string, number>;
}

export interface OverviewLastDetection {
  species_name: string;
  start_time: string; // ISO datetime
  unidentified?: boolean;
}

export interface OverviewData {
  topSpecies: OverviewTopSpecies[];
  stats: OverviewStats;
  hourlyTemperature: (number | null)[]; // 24 values, avg temp per hour (°C)
  lastDetection?: OverviewLastDetection | null;
  observer_timezone?: string;
}

export interface DetectionCounts {
  detections_24h: number;
  detections_7d: number;
  detections_30d: number;
}

export interface TimestampRange {
  first_sighting: string | null;
  last_sighting: string | null;
}

export interface SpeciesSummary {
  species: Partial<Species>;

  // Aggregate stats
  stats: {
    detections: DetectionCounts;
    timeRange: TimestampRange;
    hourlyActivity: number[];
    observer_timezone?: string;
    weather: Array<{
      temp: number;
      clouds: number;
      count: number;
    }>;
    food: Array<{
      name: string;
      count: number;
    }>;
  };

  // Child species summaries
  subspecies: Array<{
    species: Partial<Species>;
    stats: {
      detections: DetectionCounts;
      hourlyActivity: number[];
    };
  }>;

  recentVisits: SpeciesVisit[];
}
