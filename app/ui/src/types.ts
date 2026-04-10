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
  }[];
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
  spectrogram_path: string;
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
  } | null;
}

export interface BirdFood {
  id: number;
  name: string;
  active: boolean;
  description?: string;
  /** Relative path (data/images/food/...) — use resolveImageUrl() */
  image_url?: string;
}

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

export interface Settings {
  general: {
    enable_notifications: boolean;
    notification_excluded_species: string[];
    settings_password?: string;
    contributor_password?: string;
    birdnet_url?: string; // URL to BirdNET installation; empty = no icon in UI
    heimdall_url?: string; // URL to Heimdall dashboard; empty = no link in UI
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
    scales?: {
      enabled?: boolean;
      source?: 'mqtt' | 'homeassistant';
      mqtt_topic?: string;
      homeassistant_entity_id?: string;
      unit?: 'kg' | 'g';
    };
  };
  processor: {
    tracker: string; // Path to tracker config, e.g., "bytetrack.yaml"
    max_record_seconds: number; // Max recording duration in seconds
    max_inactive_seconds: number; // Max inactivity before stopping recording
    min_track_duration?: number; // Min track duration (sec) for ByteTrack; shorter tracks discarded
    min_confidence_binary?: number; // Binary detector threshold (bird vs no-bird); 0.25 = stricter
    min_confidence_to_process?: number; // Min combined confidence (voting × classifier); 0.15 = stricter
    /** Min confidence to send Telegram photo notification (defaults to min_confidence_to_process if unset). */
    min_confidence_to_notify?: number;
    min_box_size_px?: number; // Minimum bbox width/height in pixels for detector candidates
    detector_scope?: string[]; // First-stage detector targets, e.g. ["Bird", "Squirrel"]
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
    classifier_fallback_bird?: boolean; // Keep generic detector label when classifier stays uncertain
    spectrogram_px_per_sec: number; // Spectrogram pixels per second
    /** If true, generate spectrogram for every recording; if false, only when BirdNET MQTT in window */
    generate_spectrogram_always?: boolean;
    included_bird_families: string[]; // List of bird families to use in detections
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
    file_path?: string;
    file_dir?: string;
    file_loop?: boolean;
    file_realtime_simulation?: boolean;
    go2rtc_url?: string;
    stream_name?: string;
    cameras?: Array<{ id?: string; stream_name?: string; name?: string }>;
    go2rtc_username?: string;
    go2rtc_password?: string;
    /** cpu | intel — VA-API vs CPU для записи (intel = уже H.264). */
    encoding?: string;
    /** h264 | copy — перекодировать RTSP в H.264 для браузера или копировать веб-кодек как есть. */
    record_stream_codec?: 'h264' | 'copy' | string;
    video_width?: number;
    video_height?: number;
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
    species_mapping?: Record<string, string>;  // eBird name -> BirdLense name
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
    frigate_camera_filter?: string[];
    frigate_label_filter?: string[];
    frigate_label_exclude?: string[];
    /** Если метка не в фильтре, но у объекта в MQTT есть box — всё равно старт записи */
    frigate_trigger_on_tracked_object?: boolean;
    mqtt_topic?: string;
    esphome_url?: string;
    esphome_sensor_id?: string;
  };
  detection?: {
    min_confidence_to_store?: number;  // 0–1; детекции ниже не сохраняются (6% → 0.20)
    /** YOLO без треков, но Frigate прислал событие — сохранить визит по Frigate */
    frigate_standalone_when_no_yolo?: boolean;
    frigate_standalone_min_score?: number;
    frigate_standalone_missing_score_fallback?: number;
    frigate_standalone_excluded_min_score?: number;
    frigate_standalone_excluded_missing_score_fallback?: number;
    frigate_standalone_notify?: boolean;
    merge_window_seconds?: number;
    dedup_window_seconds?: number;
    one_per_species?: boolean;
    cross_source_confidence_bonus?: number;
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
    url?: string;  // POST при детекции (IFTTT, Zapier)
  };
  gallery?: {
    enabled?: boolean;
    upload_url?: string;
    min_confidence?: number;
    only_manually_corrected?: boolean;
  };
  ui?: {
    unknown_confidence_threshold?: number;  // 0–1; детекции ниже попадают в «Неизвестные»
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
}

export interface OverviewTopSpecies {
  id: number;
  name: string;
  detections: number[]; // hourly visit counts (24), legacy field name
}

export interface OverviewStats {
  uniqueSpecies: number;
  /** Visit count for the day (SpeciesVisit rows), not recognition segments */
  totalDetections: number;
  /** Visits overlapping the last hour */
  lastHourDetections: number;
  videoDuration: number;
  audioDuration: number;
  busiestHour: number;
  avgVisitDuration: number;
  detectionByProvider?: Record<string, number>;
}

export interface OverviewLastDetection {
  species_name: string;
  start_time: string; // ISO datetime
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
