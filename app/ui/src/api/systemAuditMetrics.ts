import axios from 'axios';
import type { components } from '../generated/openapi-types';
import { BASE_API_URL } from './client';

/** Ответ `GET /system/config-audit` (см. OpenAPI `ConfigAuditResponse`). */
export type ConfigAudit = components['schemas']['ConfigAuditResponse'];

export const fetchConfigAudit = async (): Promise<ConfigAudit> => {
  const response = await axios.get(`${BASE_API_URL}/system/config-audit`, {
    withCredentials: true,
  });
  return response.data;
};

export type ObservabilityPayload = {
  notify_preview_generated_24h: Record<string, number>;
  notify_preview_24h: Record<string, number>;
  notify_fallback_24h: Record<string, number>;
  notify_delivery_24h: Record<string, number>;
  ml_health: {
    rolling_7d: {
      window_days: number;
      video_detections: number;
      corrections_logged: number;
      species_change_actions: number;
      correction_rate: number;
      manual_annotation_rate: number;
      unknown_rate: number;
      generic_rate: number;
    };
    rolling_30d: {
      window_days: number;
      video_detections: number;
      corrections_logged: number;
      species_change_actions: number;
      correction_rate: number;
      manual_annotation_rate: number;
      unknown_rate: number;
      generic_rate: number;
    };
  };
  model_lineage: {
    config_fingerprint: string;
    artifacts: Record<
      string,
      {
        configured_path: string | null;
        exists: boolean;
        sha256: string | null;
      }
    >;
  };
  hub_metrics: {
    prometheus_text: string;
    prometheus_text_alt: string;
    json_summary: string;
  };
};

export type ProcessorBackpressurePayload = {
  available?: boolean;
  generated_at?: string;
  gauges?: Record<string, number | boolean | string>;
  counters?: Record<string, number>;
  snapshot_stale?: boolean | null;
};

export const fetchProcessorBackpressure = async (): Promise<ProcessorBackpressurePayload> => {
  const response = await axios.get(`${BASE_API_URL}/system/diagnostics/backpressure`, {
    withCredentials: true,
  });
  return response.data;
};

export const fetchObservability = async (): Promise<ObservabilityPayload> => {
  const response = await axios.get(`${BASE_API_URL}/system/observability`, {
    withCredentials: true,
  });
  return response.data;
};

export type MlRuntimeStatus = {
  schema: string;
  video: {
    encoding?: string;
    record_with_vaapi?: boolean;
    capture_backend_config?: string;
  };
  processor: {
    inference_backend?: string;
    inference_device?: string;
    classifier_inference_backend?: string;
    classifier_inference_device?: string;
    detector_weight_contract?: string;
    binary_imgsz?: number;
    frame_processing_warn_ms?: number;
  };
};

export const fetchMlRuntimeStatus = async (): Promise<MlRuntimeStatus> => {
  const response = await axios.get(`${BASE_API_URL}/system/ml-runtime`, {
    withCredentials: true,
  });
  return response.data;
};

export type FeedbackLoopStatus = {
  schema: string;
  events_total: number;
  events_relabel: number;
  events_delete_as_background: number;
  latest_event_at: string | null;
  latest_export?: {
    status?: string;
    events_total?: number;
    exported_total?: number;
    missing_crop_events?: number;
    generated_at_utc?: string;
  } | null;
};

export const fetchFeedbackLoopStatus = async (): Promise<FeedbackLoopStatus> => {
  const response = await axios.get(`${BASE_API_URL}/system/feedback-loop/status`, {
    withCredentials: true,
  });
  return response.data;
};

export const trackSiteVisitor = async (browserId: string): Promise<void> => {
  await axios.post(`${BASE_API_URL}/system/visitors/track`, {
    browser_id: browserId,
  });
};

export type SystemMetricsLive = {
  cpu: { percent: number };
  memory: { total: number; used: number; percent: number };
  disk: { total: number; used: number; percent: number };
  encoding: string;
  gpu_percent: number | null;
};

export type SystemMetricsHistorySample = {
  t: string;
  cpu: number;
  memory: number;
  disk: number;
  gpu: number | null;
};

export type SystemMetricsHistoryResponse = {
  samples: SystemMetricsHistorySample[];
  sample_interval_seconds?: number;
  retention_hours?: number;
  hours_requested?: number;
};

export type SystemVisitorStats = {
  period_days: number;
  unique_visits: number;
  browser_count?: number;
  active_days: number;
  device_breakdown?: Record<string, number>;
  method: string;
};

export const fetchSystemMetricsLive = async (): Promise<SystemMetricsLive> => {
  const response = await axios.get(`${BASE_API_URL}/system/metrics`);
  return response.data;
};

export const fetchSystemMetricsHistory = async (
  hours: number,
  maxPoints = 500,
): Promise<SystemMetricsHistoryResponse> => {
  const response = await axios.get(`${BASE_API_URL}/system/metrics/history`, {
    params: { hours, max_points: maxPoints },
  });
  return response.data;
};

export const fetchSystemVisitors = async (
  days: number,
): Promise<SystemVisitorStats> => {
  const response = await axios.get(`${BASE_API_URL}/system/visitors`, {
    params: { days },
  });
  return response.data;
};

export type ProcessorLogsResponse = {
  lines?: string[];
  path?: string;
};

export const fetchProcessorLogs = async (
  lines: number,
): Promise<ProcessorLogsResponse> => {
  const response = await axios.get(`${BASE_API_URL}/system/logs`, {
    params: { lines },
    withCredentials: true,
  });
  return response.data;
};

export type QualityTimeseriesBucket = {
  bucket: string;
  detections: number;
  yolo_rows: number;
  frigate_rows: number;
  avg_confidence: number;
  frigate_ratio: number;
};

export type QualityTimeseriesResponse = {
  bucket: 'hour' | 'day';
  items: QualityTimeseriesBucket[];
  count: number;
};

export type QualityHealthResponse = {
  window_hours: number;
  health_kpis: {
    blind_score_current: number;
    blind_score_avg: number;
    fallback_ratio: number;
    self_heal_action_counts: {
      soft_clear: number;
      reinit: number;
      restart: number;
      alert: number;
    };
    inference_latency_p95_ms_avg: number | null;
  };
  recent_events: Array<{
    created_at: string;
    event_type: string;
    severity: string;
    action: string | null;
    dump_refs?: {
      diagnostics_json?: string;
      stack_dump?: string;
    } | null;
  }>;
};

export const fetchQualityTimeseries = async (
  bucket: 'hour' | 'day' = 'hour',
): Promise<QualityTimeseriesResponse> => {
  const response = await axios.get(`${BASE_API_URL}/analytics/visits-timeseries`, {
    params: { bucket },
    withCredentials: true,
  });
  return response.data;
};

export const fetchQualityHealth = async (
  hours = 24,
): Promise<QualityHealthResponse> => {
  const response = await axios.get(`${BASE_API_URL}/analytics/quality-health`, {
    params: { hours },
    withCredentials: true,
  });
  return response.data;
};

export type YoloDetectorHealthStatus = 'healthy' | 'degraded' | 'blind';

export interface YoloDetectorHealthResponse {
  window_hours: number;
  updated_at?: string | null;
  processor_snapshot_present: boolean;
  health: {
    status: YoloDetectorHealthStatus;
    yolo_blind_alert: boolean;
    yolo_blind_phase: string;
    yolo_frames_with_tracks_session: number;
    session_extended_by_frigate_only: number;
    stream_probe_width?: number | null;
    stream_probe_height?: number | null;
    stream_probe_fps?: number | null;
    reasons: string[];
  };
  gauges: Record<string, unknown>;
  config_hints: Record<string, unknown>;
  runbook_path?: string;
}

export interface TriggerSourceMetricsBlock {
  recordings_initiated?: number;
  session_extensions?: number;
  species_persisted?: number;
  candidates_rejected?: number;
  mqtt_events?: number;
  fp_empty_recording?: number;
  fp_rejected_noise?: number;
  fn_detector_silent?: number;
  fn_no_persisted_species?: number;
}

export interface TriggerGraphResponse {
  window_hours: number;
  camera_filter?: string | null;
  session_count: number;
  nodes: string[];
  recordings_initiated_by_source: Record<string, number>;
  metrics_by_source: Record<string, TriggerSourceMetricsBlock>;
  decision_reason_counts: Record<string, number>;
  by_camera: Record<string, Record<string, TriggerSourceMetricsBlock>>;
  recent_sessions: Array<{
    created_at?: string;
    camera_id?: string;
    init_source?: string;
    trigger_display?: string;
    post_fusion_persisted?: number;
    fp_empty_recording?: number;
    fn_detector_silent?: number;
    species_persisted?: number;
  }>;
}

export const fetchTriggerGraph = async (hours = 24): Promise<TriggerGraphResponse> => {
  const response = await axios.get(`${BASE_API_URL}/analytics/trigger-graph`, {
    params: { hours },
    withCredentials: true,
  });
  return response.data;
};

export const fetchYoloDetectorHealth = async (
  hours = 24,
): Promise<YoloDetectorHealthResponse> => {
  const response = await axios.get(`${BASE_API_URL}/system/yolo-detector-health`, {
    params: { hours },
    withCredentials: true,
  });
  return response.data;
};
