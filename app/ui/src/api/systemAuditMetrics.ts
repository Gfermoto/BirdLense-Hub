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
