export interface SpeciesVisit {
  id: number;
  start_time: string;
  end_time: string;
  max_simultaneous: number;
  weather?: {
    temp?: number;
    clouds?: number;
  };
  species: {
    id: number;
    name: string;
    image_url?: string;
    parent_id?: number;
  };
  detections: {
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
  species_id: number;
  species_name: string;
  track_id?: number;
  start_time: number;
  end_time: number;
  confidence: number;
  source: string;
  detection_provider?: string;
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
    image_url: string;
  }[];
}

export interface BirdFood {
  id: number;
  name: string;
  active: boolean;
  description?: string;
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
    enable_notifications: boolean; // Whether to enable notifications or not
    notification_excluded_species: string[]; // list of species to exclude from notifications
    settings_password?: string; // Password to access settings; empty = no password
  };
  processor: {
    tracker: string; // Path to tracker config, e.g., "bytetrack.yaml"
    max_record_seconds: number; // Max recording duration in seconds
    max_inactive_seconds: number; // Max inactivity before stopping recording
    min_track_duration?: number; // Min track duration (sec) for ByteTrack; shorter tracks discarded
    spectrogram_px_per_sec: number; // Spectrogram pixels per second
    included_bird_families: string[]; // List of bird families to use in detections
  };
  camera: {
    video_width: number; // Video width in pixels, e.g., 1280
    video_height: number; // Video height in pixels, e.g., 720
    hdr_mode: boolean; // Enable HDR if available (Pi Camera v3)
    focus_mode: 'auto' | 'manual'; // Focus mode: auto (continuous) or manual (fixed)
    lens_position: number; // Diopters for manual focus (higher = closer). 7 ≈ 14cm
  };
  secrets: {
    openweather_api_key: string; // API key for OpenWeather
    latitude: string; // Latitude as a string, e.g., "YOUR_LATITUDE_HERE"
    longitude: string; // Longitude as a string, e.g., "YOUR_LONGITUDE_HERE"
    zip?: string;
  };
  video?: {
    source?: string;
    go2rtc_url?: string;
    stream_name?: string;
    cameras?: Array<{ id?: string; stream_name?: string; name?: string }>;
    go2rtc_username?: string;
    go2rtc_password?: string;
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
  };
  weather?: {
    source?: string;
    ha_url?: string;
    ha_entity_id?: string;
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
    mqtt_topic?: string;
    esphome_url?: string;
    esphome_sensor_id?: string;
  };
  mcp?: {
    enabled?: boolean;
    token?: string;
    api_url?: string;
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
  image_url: string | null;
  description: string | null;
  active: boolean;
  count?: number;
}

export interface OverviewTopSpecies {
  id: number;
  name: string;
  detections: number[]; // hourly count of detections, 24 values
}

export interface OverviewStats {
  uniqueSpecies: number;
  totalDetections: number;
  lastHourDetections: number;
  videoDuration: number;
  audioDuration: number;
  busiestHour: number;
  avgVisitDuration: number;
  detectionByProvider?: Record<string, number>;
}

export interface OverviewData {
  topSpecies: OverviewTopSpecies[];
  stats: OverviewStats;
  hourlyTemperature: (number | null)[]; // 24 values, avg temp per hour (°C)
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
