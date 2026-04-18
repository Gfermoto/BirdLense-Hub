import { Dayjs } from 'dayjs';
import {
  BirdFood,
  SpeciesVisit,
  Settings,
  SpeciesSummary,
  OverviewData,
  Species,
  TrackFrame,
} from '../types';
import axios from 'axios';
import { formatLocalTime } from '../util';
import type { TimeOfDay } from '../utils/timeUtils';
import type { components } from '../generated/openapi-types';

// Relative path = same origin (works with any host/IP). При SSR/тестах — из env или дефолт.
export const BASE_URL =
  typeof window !== 'undefined'
    ? ''
    : (import.meta.env?.VITE_BASE_URL as string) || '';
export const BASE_API_URL = `${BASE_URL}/api/ui`;

axios.defaults.timeout = 30000;

/** Текст ошибки из JSON `{ error: string }` или fallback (для мутаций UI). */
export function getApiErrorMessage(err: unknown, fallback: string): string {
  if (axios.isAxiosError(err)) {
    const data = err.response?.data;
    if (data && typeof data === 'object' && data !== null && 'error' in data) {
      const msg = (data as { error?: unknown }).error;
      if (typeof msg === 'string' && msg.trim()) return msg;
    }
    if (err.message) return err.message;
  }
  if (err instanceof Error && err.message) return err.message;
  return fallback;
}

/** Длинный timeout для опроса фоновых job (spectrogram / tracks): дефолт 30s рвёт poll на медленном ответе. */
export const JOB_STATUS_POLL_TIMEOUT_MS = 120_000;

/**
 * Resolve image URL for display.
 * - Absolute (http/https) → as-is
 * - data:image/* only (block data:text/html etc. for XSS)
 * - Relative path (data/images/...) → BASE_URL + path
 * Species: Wikipedia returns full URLs. Bird food: relative paths from seed.
 */
export const resolveImageUrl = (url: string | null | undefined): string | undefined => {
  if (!url) return undefined;
  if (url.startsWith('http://') || url.startsWith('https://')) {
    // Do not proxy Wikimedia: server-side proxy can be rate-limited by shared IP.
    // Keep browser direct-load for Wikimedia and proxy only iNaturalist-hosted links.
    const lower = url.toLowerCase();
    const needsProxy = lower.includes('inaturalist');
    if (!needsProxy) return url;
    const base = BASE_URL || '';
    return `${base ? `${base}` : ''}/api/ui/species-image?url=${encodeURIComponent(url)}`;
  }
  if (url.startsWith('data:')) {
    const m = url.match(/^data:image\/(png|jpeg|jpg|gif|webp);base64,/i);
    return m ? url : undefined;
  }
  const base = BASE_URL || '';
  return base ? `${base}/${url}` : `/${url}`;
};

export const fetchTimeline = async (
  startTime: Dayjs,
  endTime: Dayjs,
): Promise<SpeciesVisit[]> => {
  const response = await axios.get(`${BASE_API_URL}/timeline`, {
    params: {
      start_time: startTime.unix(),
      end_time: endTime.unix(),
    },
  });
  return response.data;
};

export const fetchTimelineForObserverDate = async (
  date: string,
  options?: { timeOfDay?: TimeOfDay; hour?: number | null },
): Promise<SpeciesVisit[]> => {
  const response = await axios.get(`${BASE_API_URL}/timeline`, {
    params: {
      date,
      ...(options?.hour != null
        ? { hour: options.hour }
        : { time_of_day: options?.timeOfDay ?? 'all' }),
    },
  });
  return response.data;
};

/** Export timeline as CSV, JSON, or eBird format. Triggers download. */
export const exportTimeline = async (
  startTime: Dayjs,
  endTime: Dayjs,
  format: 'csv' | 'json' | 'ebird',
): Promise<void> => {
  const params = new URLSearchParams({
    start_time: String(startTime.unix()),
    end_time: String(endTime.unix()),
    format,
  });
  const url = `${BASE_API_URL}/timeline/export?${params}`;
  const res = await fetch(url);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: res.statusText }));
    throw new Error(err.error || res.statusText);
  }
  const blob = await res.blob();
  const ext = format === 'ebird' ? 'csv' : format === 'csv' ? 'csv' : 'json';
  const filename = format === 'ebird' ? 'birdlense_ebird.csv' : `birdlense_timeline.${ext}`;
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  a.click();
  URL.revokeObjectURL(a.href);
};

export const exportTimelineForObserverDate = async (
  date: string,
  format: 'csv' | 'json' | 'ebird',
  options?: { timeOfDay?: TimeOfDay; hour?: number | null },
): Promise<void> => {
  const params = new URLSearchParams({
    date,
    format,
    ...(options?.hour != null
      ? { hour: String(options.hour) }
      : { time_of_day: options?.timeOfDay ?? 'all' }),
  });
  const url = `${BASE_API_URL}/timeline/export?${params}`;
  const res = await fetch(url);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: res.statusText }));
    throw new Error(err.error || res.statusText);
  }
  const blob = await res.blob();
  const ext = format === 'ebird' ? 'csv' : format === 'csv' ? 'csv' : 'json';
  const filename = format === 'ebird' ? 'birdlense_ebird.csv' : `birdlense_timeline.${ext}`;
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  a.click();
  URL.revokeObjectURL(a.href);
};

export const fetchWeather = async () => {
  const response = await axios.get(`${BASE_API_URL}/weather`);
  return response.data;
};

/** Sunrise, sunset, dawn, dusk for date at configured location. date: YYYY-MM-DD. Returns ISO strings (UTC). */
export const fetchSunTimes = async (date: string): Promise<{
  dawn?: string;
  sunrise?: string;
  noon?: string;
  sunset?: string;
  dusk?: string;
} | null> => {
  try {
    const res = await axios.get(`${BASE_API_URL}/sun-times`, {
      params: { date },
    });
    const d = res.data;
    if (!d || typeof d !== 'object' || !('sunrise' in d)) return null;
    return d;
  } catch {
    return null;
  }
};

/** Format ISO UTC string to local HH:MM */
export const formatSunTimeLocal = (iso: string): string => {
  try {
    return formatLocalTime(iso);
  } catch {
    return '--:--';
  }
};

/** Region comparison with eBird. Returns null if API key not configured or error. */
export const fetchRegionComparison = async (): Promise<{
  regionCode: string;
  userCount: number;
  regionTopCount: number;
  matchCount: number;
  matchedSpecies: string[];
  regionTop: string[];
} | null> => {
  try {
    const res = await axios.get(`${BASE_API_URL}/region-comparison`);
    const d = res.data;
    if (!d || typeof d !== 'object' || !('regionCode' in d)) return null;
    return d;
  } catch {
    return null;
  }
};

export const fetchVideo = async (id: string) => {
  const response = await axios.get(`${BASE_API_URL}/videos/${id}`);
  return response.data;
};

/** Покадровые bbox — отдельно от GET /videos/:id (лёгкая первая отрисовка страницы). */
export const fetchVideoDetectionFrames = async (id: string) => {
  const response = await axios.get(`${BASE_API_URL}/videos/${id}/detection-frames`);
  return response.data as {
    tracks: Array<{
      id: number | null;
      species_id: number;
      start_time: number;
      end_time: number;
      frames: TrackFrame[];
    }>;
  };
};

/** Prev/next video IDs for the selected day scope. */
export type VideoNeighbors = {
  day_scope: 'utc' | 'local';
  day_label: string;
  timezone_offset_minutes: number;
  cross_day: boolean;
  previous_id: number | null;
  next_id: number | null;
  index: number;
  total: number;
};

export const fetchVideoNeighbors = async (id: string): Promise<VideoNeighbors> => {
  const tzOffset = new Date().getTimezoneOffset();
  const response = await axios.get(`${BASE_API_URL}/videos/${id}/neighbors`, {
    params: {
      day_scope: 'local',
      tz_offset_minutes: tzOffset,
      cross_day: 1,
    },
  });
  return response.data;
};

export type FusionTraceLine = { field: string; value: string };
export type FusionTraceStep = { stage: string; lines: FusionTraceLine[] };
export type FusionTraceTrack = {
  bucket: 'persisted' | 'rejected' | 'accepted';
  track_id?: number | null;
  species_name?: string | null;
  steps: FusionTraceStep[];
};

export type FusionTracePayload = {
  available: boolean;
  video_id?: number;
  video_path?: string;
  message?: string;
  log_created_at?: string | null;
  trace?: Record<string, unknown> | null;
  tracks?: FusionTraceTrack[];
};

export const fetchVideoFusionTrace = async (id: number): Promise<FusionTracePayload> => {
  const response = await axios.get(`${BASE_API_URL}/videos/${id}/fusion-trace`, {
    withCredentials: true,
  });
  return response.data;
};

export const fetchNearestRecordingDay = async (
  date: string,
  direction: 'prev' | 'next',
): Promise<{ date: string | null; direction: 'prev' | 'next'; found: boolean }> => {
  const response = await axios.get(`${BASE_API_URL}/storage/nearest-recording-day`, {
    params: { date, direction },
  });
  return response.data;
};

/** Delete video recording. Requires contributor or admin access. */
export const deleteVideo = async (id: number): Promise<void> => {
  const res = await fetch(`${BASE_API_URL}/videos/${id}`, {
    method: 'DELETE',
    credentials: 'include',
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: res.statusText }));
    throw new Error(err.error || res.statusText);
  }
};

/** Export dataset crops as ZIP. Requires settings access. */
export const exportDataset = async (params?: {
  start_date?: string;
  end_date?: string;
  only_manually_corrected?: boolean;
  ready_for_train?: boolean;
  test_ratio?: number;
  strict_quality?: boolean;
}): Promise<void> => {
  const q = new URLSearchParams();
  if (params?.start_date) q.set('start_date', params.start_date);
  if (params?.end_date) q.set('end_date', params.end_date);
  if (params?.only_manually_corrected) q.set('only_manually_corrected', '1');
  if (params?.ready_for_train) q.set('ready_for_train', '1');
  if (params?.test_ratio != null && params.test_ratio > 0) {
    q.set('test_ratio', String(params.test_ratio));
  }
  if (params?.strict_quality) q.set('strict_quality', '1');
  const url = `${BASE_API_URL}/dataset/export${q.toString() ? `?${q}` : ''}`;
  const res = await fetch(url, {
    credentials: 'include',
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: res.statusText }));
    throw new Error(err.error || res.statusText);
  }
  const blob = await res.blob();
  const cd = res.headers.get('Content-Disposition');
  const match = cd?.match(/filename="?([^";\n]+)"?/);
  const filename = match?.[1] || 'birdlense_dataset.zip';
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  a.click();
  URL.revokeObjectURL(a.href);
};

/** Retro-export: extract crops from all video detections into dataset. */
export const retroExportDataset = async (
  minConfidence = 0,
  period?: { start_date?: string; end_date?: string },
  onlyManuallyCorrected = false,
  rebuild = false,
): Promise<{
  saved: number;
  skipped: number;
  skipped_no_bbox?: number;
  deleted?: number;
  errors: string[];
}> => {
  const body: Record<string, unknown> = { min_confidence: minConfidence };
  if (period?.start_date) body.start_date = period.start_date;
  if (period?.end_date) body.end_date = period.end_date;
  if (onlyManuallyCorrected) body.only_manually_corrected = true;
  if (rebuild) body.rebuild = true;
  const res = await fetch(`${BASE_API_URL}/dataset/retro-export`, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: res.statusText }));
    throw new Error(err.error || res.statusText);
  }
  return res.json();
};

/** Clean dataset: remove suspected full-frame and/or orphaned files. */
export const cleanDataset = async (params?: {
  dry_run?: boolean;
  remove_fullframe?: boolean;
  remove_orphaned?: boolean;
}): Promise<{
  deleted_fullframe: number;
  deleted_orphaned: number;
  errors: string[];
  dry_run: boolean;
}> => {
  const res = await fetch(`${BASE_API_URL}/dataset/clean`, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params || {}),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: res.statusText }));
    throw new Error(err.error || res.statusText);
  }
  return res.json();
};

/** Download detection crop for iNaturalist. Opens iNaturalist upload in new tab. */
export const downloadDetectionCropForINaturalist = async (
  detectionId: number,
  speciesName: string,
): Promise<void> => {
  const res = await fetch(`${BASE_API_URL}/detections/${detectionId}/crop`);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: res.statusText }));
    throw new Error(err.error || res.statusText);
  }
  const blob = await res.blob();
  const disp = res.headers.get('Content-Disposition');
  const filename =
    disp?.match(/filename="?([^";\n]+)"?/)?.[1] ||
    `${speciesName.replace(/\s+/g, '_')}.jpg`;
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  a.click();
  URL.revokeObjectURL(a.href);
  window.open('https://www.inaturalist.org/observations/upload', '_blank', 'noopener');
};

export const fetchBirdFood = async (): Promise<BirdFood[]> => {
  const response = await axios.get(`${BASE_API_URL}/birdfood`);
  return response.data;
};

export const toggleBirdFood = async (id: number) => {
  const response = await axios.patch(`${BASE_API_URL}/birdfood/${id}/toggle`);
  return response.data;
};

export const addBirdFood = async (newFood: Partial<BirdFood>) => {
  const response = await axios.post(`${BASE_API_URL}/birdfood`, newFood);
  return response.data;
};

export const fetchCameras = async (): Promise<
  { id: string; name: string; stream_url: string; stream_url_mjpeg?: string }[]
> => {
  const response = await axios.get(`${BASE_API_URL}/cameras`);
  return response.data.cameras || [];
};

export const fetchStatus = async (): Promise<{
  web: string;
  processor: string;
  video: string;
  mqtt: string;
  esphome?: string;
  yolo: string;
  motion_source?: string;
  trigger_display?: string;
  active_triggers?: ('opencv' | 'frigate' | 'motion_sensor' | 'scales')[];
  birdnet_url?: string | null;
}> => {
  const response = await axios.get(`${BASE_API_URL}/status`);
  return response.data;
};

export type ReadinessPayload = {
  status: string;
  ready: boolean;
  checked_at: string;
  checks: {
    database: { status: string; error?: string };
    data_dir: {
      path: string;
      exists: boolean;
      is_dir: boolean;
      writable: boolean;
      status: string;
    };
    app_config_dir: {
      path: string;
      exists: boolean;
      is_dir: boolean;
      writable: boolean;
      status: string;
    };
  };
  components: {
    web: string;
    processor: string;
    video: string;
    mqtt: string;
    esphome?: string;
    yolo: string;
    motion_source?: string;
    trigger_display?: string;
    active_triggers?: ('opencv' | 'frigate' | 'motion_sensor' | 'scales')[];
    birdnet_url?: string | null;
  };
};

export const fetchReadiness = async (): Promise<ReadinessPayload> => {
  const response = await axios.get(`${BASE_API_URL}/readiness`, {
    validateStatus: (status) => status === 200 || status === 503,
  });
  return response.data;
};

export const fetchFeedInfo = async (): Promise<{
  last_dispense_at: string | null;
  donate_url: string | null;
  feed_source?: string;
  scales_enabled?: boolean;
  scales_source?: 'mqtt' | 'esphome' | 'homeassistant' | null;
  scale_tare_available?: boolean;
  scale?: {
    weight?: number;
    unit?: string;
    updated_at?: string;
    source?: string;
    bird_present?: boolean;
  } | null;
}> => {
  const response = await axios.get(`${BASE_API_URL}/feed/info`);
  return response.data;
};

export const postScaleTare = async (): Promise<{ success: boolean; message?: string }> => {
  try {
    const response = await axios.post(
      `${BASE_API_URL}/feed/scale-tare`,
      {},
      { withCredentials: true },
    );
    return { success: true, message: response.data?.message };
  } catch (e: unknown) {
    const err = e as { response?: { data?: { error?: string } } };
    return {
      success: false,
      message: err.response?.data?.error || 'Scale tare failed',
    };
  }
};

export const dispenseFeed = async (): Promise<{ success: boolean; message?: string }> => {
  try {
    const response = await axios.post(`${BASE_API_URL}/feed/dispense`, {}, {
      withCredentials: true,
    });
    return { success: true, message: response.data?.message };
  } catch (e: unknown) {
    const err = e as { response?: { data?: { error?: string } } };
    return {
      success: false,
      message: err.response?.data?.error || 'Failed to dispense feed',
    };
  }
};

export type RequiresPasswordResult = {
  requires: boolean;
  has_contributor_tier?: boolean;
};

export const fetchSettingsRequiresPassword = async (): Promise<RequiresPasswordResult> => {
  const response = await axios.get(`${BASE_API_URL}/settings/requires-password`, {
    withCredentials: true,
  });
  return {
    requires: response.data?.requires === true,
    has_contributor_tier: response.data?.has_contributor_tier === true,
  };
};

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

export const trackSiteVisitor = async (browserId: string): Promise<void> => {
  await axios.post(`${BASE_API_URL}/system/visitors/track`, {
    browser_id: browserId,
  });
};

export type CheckAccessResult =
  | { unlocked: true; role?: 'admin' | 'contributor' }
  | { unlocked: false; error?: 'network' };

export const checkSettingsAccess = async (): Promise<CheckAccessResult> => {
  try {
    const response = await axios.get(`${BASE_API_URL}/settings/check-access`, {
      withCredentials: true,
    });
    if (response.data?.unlocked === true) {
      return { unlocked: true, role: response.data?.role || 'admin' };
    }
    return { unlocked: false };
  } catch (e: unknown) {
    // Legacy servers returned 403 when locked; treat as locked.
    if (axios.isAxiosError(e) && e.response?.status === 403) {
      return { unlocked: false };
    }
    return { unlocked: false, error: 'network' };
  }
};

export type VerifyPasswordResult =
  | { ok: true; role?: 'admin' | 'contributor' }
  | { ok: false; error: 'wrong_password' | 'server_error' };

export const verifySettingsPassword = async (
  password: string,
): Promise<VerifyPasswordResult> => {
  try {
    const response = await axios.post(
      `${BASE_API_URL}/settings/verify-password`,
      { password },
      { withCredentials: true },
    );
    if (response.data?.ok === true) {
      return { ok: true, role: response.data?.role || 'admin' };
    }
    return { ok: false, error: 'wrong_password' };
  } catch (e: unknown) {
    return axios.isAxiosError(e) && e.response?.status === 401
      ? { ok: false, error: 'wrong_password' }
      : { ok: false, error: 'server_error' };
  }
};

export const logoutSettingsSession = async (): Promise<void> => {
  await axios.post(`${BASE_API_URL}/settings/logout`, {}, { withCredentials: true });
};

export const fetchSettings = async () => {
  const response = await axios.get(`${BASE_API_URL}/settings`, {
    withCredentials: true,
  });
  return response.data;
};

export type EbirdMappingSuggestion = {
  ebird_name: string;
  birdlense_name: string | null;
  kind: 'case_variant' | 'fuzzy' | 'unmatched';
  score: number | null;
};

export type EbirdMappingSuggestionsResponse = {
  region_code: string;
  ebird_api_configured: boolean;
  top_count: number;
  suggestions: EbirdMappingSuggestion[];
};

export const fetchEbirdMappingSuggestions =
  async (): Promise<EbirdMappingSuggestionsResponse> => {
    const response = await axios.get(
      `${BASE_API_URL}/settings/ebird-species-mapping-suggestions`,
      { withCredentials: true },
    );
    return response.data;
  };

export const updateSettings = async (settings: Settings) => {
  const payload = JSON.parse(JSON.stringify(settings)) as Record<string, unknown>;
  const perf = payload.performance as Record<string, unknown> | undefined;
  if (perf && typeof perf === 'object') {
    delete perf.redis_url_effective_masked;
  }
  const response = await axios.patch(`${BASE_API_URL}/settings`, payload, {
    withCredentials: true,
  });
  return response.data;
};

/** Deep-merge PATCH (same as full save); use for small updates e.g. Library file replay mode. */
export const patchSettings = async (partial: Record<string, unknown>) => {
  const response = await axios.patch(`${BASE_API_URL}/settings`, partial, {
    withCredentials: true,
  });
  return response.data;
};

// --- System monitor / processor logs (#296)
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

export const fetchSystemVisitors = async (days: number): Promise<SystemVisitorStats> => {
  const response = await axios.get(`${BASE_API_URL}/system/visitors`, {
    params: { days },
  });
  return response.data;
};

export type ProcessorLogsResponse = {
  lines?: string[];
  path?: string;
};

export const fetchProcessorLogs = async (lines: number): Promise<ProcessorLogsResponse> => {
  const response = await axios.get(`${BASE_API_URL}/system/logs`, {
    params: { lines },
    withCredentials: true,
  });
  return response.data;
};

// --- File replay test (video.source=file, #270)
export type FileTestFileRow = {
  name: string;
  size: number;
  duration_sec: number | null;
};

export type FileTestFilesResponse = {
  file_dir: string;
  files: FileTestFileRow[];
};

export type FileTestStatusPayload = {
  file_dir: string;
  desired: Record<string, unknown>;
  processor: Record<string, unknown> | null;
  config_loop_default: boolean;
  video_source: string;
  /** Effective upload cap (MiB) from video.file_test_max_upload_mb */
  file_test_max_upload_mb?: number;
};

export const fetchFileTestFiles = async (): Promise<FileTestFilesResponse> => {
  const response = await axios.get(`${BASE_API_URL}/system/file-test/files`, {
    withCredentials: true,
  });
  return response.data;
};

export const fetchFileTestStatus = async (): Promise<FileTestStatusPayload> => {
  const response = await axios.get(`${BASE_API_URL}/system/file-test/status`, {
    withCredentials: true,
  });
  return response.data;
};

export const fileTestRun = async (body: { armed?: boolean; loop?: boolean }) => {
  const response = await axios.post(`${BASE_API_URL}/system/file-test/run`, body, {
    withCredentials: true,
  });
  return response.data;
};

export const fileTestStop = async () => {
  const response = await axios.post(`${BASE_API_URL}/system/file-test/stop`, {}, { withCredentials: true });
  return response.data;
};

export const fileTestDeleteFile = async (name: string) => {
  await axios.delete(`${BASE_API_URL}/system/file-test/files/${encodeURIComponent(name)}`, {
    withCredentials: true,
  });
};

export const fileTestUpload = async (file: File) => {
  const fd = new FormData();
  fd.append('file', file);
  const response = await axios.post(`${BASE_API_URL}/system/file-test/upload`, fd, {
    withCredentials: true,
  });
  return response.data as { ok: boolean; name?: string };
};

/** Web Push: get VAPID public key for subscription. */
export const fetchVapidPublicKey = async (): Promise<string> => {
  const res = await fetch(`${BASE_API_URL}/push/vapid-public`, {
    credentials: 'include',
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: res.statusText }));
    throw new Error(err.error || 'Web Push not available');
  }
  const data = await res.json();
  return data.vapid_public_key;
};

/** Web Push: register subscription with server. */
export const subscribePush = async (subscription: globalThis.PushSubscription): Promise<void> => {
  const sub = subscription.toJSON();
  const keys = sub.keys;
  if (!keys) throw new Error('Invalid subscription');
  const res = await fetch(`${BASE_API_URL}/push/subscribe`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({
      subscription: {
        endpoint: sub.endpoint,
        keys: { p256dh: keys.p256dh, auth: keys.auth },
      },
    }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: res.statusText }));
    throw new Error(err.error || 'Subscribe failed');
  }
};

export const sendTestNotification = async (): Promise<{ success: boolean; message?: string }> => {
  try {
    const response = await axios.post(`${BASE_API_URL}/notify/test`, {}, {
      withCredentials: true,
    });
    return {
      success: true,
      message: response.data?.message || 'Sent',
    };
  } catch (e: unknown) {
    const err = e as { response?: { data?: { error?: string } } };
    return {
      success: false,
      message: err.response?.data?.error || 'Failed',
    };
  }
};

export const refreshTelegramProxy = async (): Promise<{ success: boolean; message?: string }> => {
  try {
    const response = await axios.post(`${BASE_API_URL}/system/telegram-proxy/refresh`, {}, {
      withCredentials: true,
    });
    return {
      success: true,
      message: response.data?.message || 'Started',
    };
  } catch (e: unknown) {
    const err = e as { response?: { data?: { error?: string } } };
    return {
      success: false,
      message: err.response?.data?.error || 'Failed',
    };
  }
};

export const restartProcessor = async (): Promise<{ success: boolean; message?: string }> => {
  try {
    const response = await axios.post(`${BASE_API_URL}/restart-processor`, {}, {
      withCredentials: true,
    });
    return { success: true, message: response.data?.message };
  } catch (e: unknown) {
    const err = e as { response?: { data?: { error?: string } } };
    return {
      success: false,
      message: err.response?.data?.error || 'Failed to restart',
    };
  }
};

export type ProcessorWeightsSlotStatus = {
  path: string | null;
  uses_custom_dir: boolean;
  default_path: string;
  bytes: number | null;
  mtime_unix: number | null;
};

export type ProcessorWeightsAllowlistStatus = {
  path: string | null;
  uses_custom_dir: boolean;
  bytes: number | null;
  mtime_unix: number | null;
};

export type ProcessorWeightsStatusResponse = {
  custom_weights_dir: string;
  binary: ProcessorWeightsSlotStatus;
  classifier: ProcessorWeightsSlotStatus;
  allowlist: ProcessorWeightsAllowlistStatus;
};

export const fetchProcessorWeightsStatus = async (): Promise<ProcessorWeightsStatusResponse> => {
  const response = await axios.get(`${BASE_API_URL}/system/processor-weights/status`, {
    withCredentials: true,
  });
  return response.data as ProcessorWeightsStatusResponse;
};

const _PROCESSOR_WEIGHTS_UPLOAD_TIMEOUT_MS = 3_600_000; // 1 h

export const uploadProcessorWeight = async (
  role: 'binary' | 'classifier' | 'class_names',
  file: File,
  options?: { acknowledgeClassifierOnly?: boolean },
): Promise<{ ok: boolean; error?: string; status?: ProcessorWeightsStatusResponse }> => {
  const form = new FormData();
  form.append('file', file);
  const params: Record<string, string> = { role };
  if (options?.acknowledgeClassifierOnly) {
    params.acknowledge_classifier_only = '1';
  }
  try {
    const response = await axios.post(
      `${BASE_API_URL}/system/processor-weights/upload`,
      form,
      {
        withCredentials: true,
        params,
        timeout: _PROCESSOR_WEIGHTS_UPLOAD_TIMEOUT_MS,
        headers: { 'Content-Type': 'multipart/form-data' },
      },
    );
    return { ok: true, status: response.data?.status };
  } catch (e: unknown) {
    const err = e as { response?: { data?: { error?: string } } };
    return {
      ok: false,
      error: err.response?.data?.error || 'upload_failed',
    };
  }
};

export const resetProcessorWeights = async (
  roles: Array<'binary' | 'classifier' | 'class_names' | 'all'>,
): Promise<{ ok: boolean; error?: string; status?: ProcessorWeightsStatusResponse }> => {
  try {
    const response = await axios.post(
      `${BASE_API_URL}/system/processor-weights/reset`,
      { roles },
      { withCredentials: true },
    );
    return { ok: true, status: response.data?.status };
  } catch (e: unknown) {
    const err = e as { response?: { data?: { error?: string } } };
    return {
      ok: false,
      error: err.response?.data?.error || 'reset_failed',
    };
  }
};

/** Download SQLite DB backup from System page. */
const _downloadYamlResponse = async (url: string, fallbackName: string) => {
  const res = await fetch(url, { credentials: 'include' });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: res.statusText }));
    throw new Error(err.error || res.statusText);
  }
  const blob = await res.blob();
  const cd = res.headers.get('Content-Disposition');
  const filename =
    cd?.match(/filename="?([^";\n]+)"?/)?.[1] || fallbackName;
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  a.click();
  URL.revokeObjectURL(a.href);
};

export const downloadSettingsYamlSafe = async (): Promise<void> => {
  await _downloadYamlResponse(
    `${BASE_API_URL}/settings/yaml-export?mode=safe`,
    'user_config_safe.yaml',
  );
};

export const downloadSettingsYamlFull = async (): Promise<void> => {
  await _downloadYamlResponse(
    `${BASE_API_URL}/settings/yaml-export?mode=full&ack=full`,
    'user_config_full.yaml',
  );
};

export const importSettingsYaml = async (
  file: File,
): Promise<{ ok: boolean; message?: string }> => {
  const formData = new FormData();
  formData.append('file', file);
  const res = await fetch(`${BASE_API_URL}/settings/yaml-import`, {
    method: 'POST',
    credentials: 'include',
    body: formData,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    return {
      ok: false,
      message: (data as { error?: string }).error || res.statusText,
    };
  }
  return { ok: true, message: (data as { message?: string }).message };
};

export const downloadDbBackup = async (): Promise<void> => {
  const res = await fetch(`${BASE_API_URL}/system/db/backup`, {
    credentials: 'include',
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: res.statusText }));
    throw new Error(err.error || res.statusText);
  }
  const blob = await res.blob();
  const cd = res.headers.get('Content-Disposition');
  const filename =
    cd?.match(/filename="?([^";\n]+)"?/)?.[1] ||
    `birdlense_db_backup_${new Date().toISOString().replace(/[:.]/g, '-')}.db`;
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  a.click();
  URL.revokeObjectURL(a.href);
};

/** Restore SQLite DB from uploaded file (.db). */
export const restoreDbBackup = async (
  file: File,
): Promise<{ message: string; backup_path?: string }> => {
  const formData = new FormData();
  formData.append('file', file);
  const res = await fetch(`${BASE_API_URL}/system/db/restore`, {
    method: 'POST',
    credentials: 'include',
    body: formData,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: res.statusText }));
    throw new Error(err.error || res.statusText);
  }
  return res.json();
};

export type PurgeStorageBody =
  | { date: string }
  | { start_date: string; end_date: string };

/** Delete recordings by cutoff date or inclusive calendar range (admin). */
export const purgeStorageRecordings = async (
  body: PurgeStorageBody,
): Promise<{ message: string; deletedCount: number; deletedSize: number }> => {
  const { data } = await axios.post(`${BASE_API_URL}/storage/purge`, body, {
    withCredentials: true,
  });
  return data;
};

export const fetchCoordinatesByZip = async (
  zip: string,
): Promise<{ lat: string; lon: string }> => {
  const response = await axios.get(
    'https://nominatim.openstreetmap.org/search',
    {
      params: {
        format: 'json',
        postalcode: zip,
        countrycodes: 'ru,us,de,gb',
      },
    },
  );
  const data = response.data;

  if (data && data.length > 0) {
    return {
      lat: data[0].lat,
      lon: data[0].lon,
    };
  } else {
    throw new Error('Invalid ZIP code or no data found.');
  }
};

export const fetchBirdDirectory = async (): Promise<Species[]> => {
  const response = await axios.get(`${BASE_API_URL}/species`);
  return response.data;
};

export interface SpeciesDataQualityReport {
  species_total: number;
  duplicate_name_group_count: number;
  duplicate_name_groups: Array<{
    normalized_name: string;
    count: number;
    species: Array<{ id: number; name: string }>;
  }>;
  hints: Record<string, string>;
}

export const fetchSpeciesDataQuality = async (): Promise<SpeciesDataQualityReport> => {
  const response = await axios.get(`${BASE_API_URL}/system/species-registry/data-quality`, {
    params: { suspect_limit: 500, duplicate_limit: 100 },
  });
  return response.data;
};

export interface ClassifierDatasetAlignmentReport {
  classifier_weights_path: string;
  classifier_weights_resolved: string;
  classifier_readable: boolean;
  classifier_error: string | null;
  classifier_class_count: number;
  in_classifier_not_in_catalog: string[];
  in_classifier_not_in_catalog_count: number;
  in_catalog_not_in_classifier: Array<{ id: number; name: string }>;
  in_catalog_not_in_classifier_count: number;
  dataset_folder_count: number;
  dataset_folders_without_catalog_match: string[];
  dataset_folders_without_catalog_match_count: number;
  dataset_folders_species_not_in_classifier: Array<{
    folder: string;
    species_id: number;
    species_name: string;
  }>;
  dataset_folders_species_not_in_classifier_count: number;
  species_with_video_detections: number;
  catalog_species_total: number;
  catalog_classifier_dataset_aligned?: boolean;
  hints?: Record<string, string>;
}

export interface CatalogCoverageMetrics {
  observed_species_count: number;
  dataset_species_count: number;
  full_eu_species_count: number;
  observed_in_full_eu_count: number;
  dataset_in_full_eu_count: number;
  observed_vs_full_eu_percent: number;
  dataset_vs_full_eu_percent: number;
  observed_in_dataset_count: number;
  observed_in_dataset_percent: number;
  tuning_candidate_count: number;
  tuning_candidates: Array<{ id: number; name: string }>;
}

export interface CatalogCardsCoverageSnapshot {
  allowlist_total: number;
  /** Allowlist file lines that resolved to some ``Species`` row (can exceed unique species). */
  allowlist_lines_matched: number;
  /** Distinct ``Species`` rows referenced by at least one allowlist line. */
  species_matched: number;
  with_image: number;
  with_description: number;
  complete_cards: number;
  completion_percent: number;
}

export interface CatalogRepairStatus {
  status: 'idle' | 'running' | 'done' | 'error';
  result: null | {
    checked: number;
    metadata_fixed: number;
    images_replaced_from_inat: number;
    images_realigned_allowlist_science?: number;
    still_missing: number;
    dry_run: boolean;
    auto?: boolean;
    coverage_after?: CatalogCardsCoverageSnapshot;
  };
  error: string | null;
  progress: null | {
    auto?: boolean;
    limit: number;
    coverage_before?: CatalogCardsCoverageSnapshot;
  };
  coverage_now: CatalogCardsCoverageSnapshot;
  schedule?: {
    autorun_enabled: boolean;
    interval_min: number;
    limit: number;
    next_run_in_sec: number;
  };
}

export const fetchClassifierDatasetAlignment =
  async (): Promise<ClassifierDatasetAlignmentReport> => {
    const response = await axios.get(
      `${BASE_API_URL}/system/species-registry/classifier-dataset-alignment`,
      { params: { classifier_limit: 400, catalog_limit: 300, dataset_limit: 150 } },
    );
    return response.data;
  };

export const fetchCatalogCoverageMetrics =
  async (): Promise<CatalogCoverageMetrics> => {
    const response = await axios.get(
      `${BASE_API_URL}/system/species-registry/coverage-metrics`,
    );
    return response.data;
  };

export const fetchCatalogRepairStatus = async (): Promise<CatalogRepairStatus> => {
  const response = await axios.get(
    `${BASE_API_URL}/system/species-registry/repair-cards/status`,
    { withCredentials: true },
  );
  return response.data;
};

export const startCatalogRepair = async (
  limit = 6000,
): Promise<{ message: string; status: CatalogRepairStatus }> => {
  const response = await axios.post(
    `${BASE_API_URL}/system/species-registry/repair-cards/start`,
    { limit },
    { withCredentials: true },
  );
  return response.data;
};

export type SystemJobStatus = {
  status: string;
  result?: Record<string, unknown> | null;
  error?: string | null;
  progress?: Record<string, unknown> | null;
};

export type BirdnetSpeciesFifoRow = {
  display_label: string;
  canonical_for_video: string;
  scientific_name?: string | null;
  active: number;
  last_heard_at?: string;
  seconds_since_heard?: number;
  event_count: number;
};

export type BirdnetFifoDialogSnapshot = {
  queue_len?: number;
  fifo_cap?: number;
  fifo_fill_ratio?: number;
  mqtt_connected?: boolean;
  processor_pid?: number;
  species_hearing?: {
    active_within_hours?: number;
    by_species?: Record<string, { active?: number }>;
  };
  species_fifo_table?: BirdnetSpeciesFifoRow[];
  species_counts?: Record<string, number>;
};

export type BirdnetFifoPayload = {
  available?: boolean;
  snapshot?: BirdnetFifoDialogSnapshot | null;
} & Record<string, unknown>;

const postSystemAction = async (
  path: string,
  body: Record<string, unknown> = {},
): Promise<Record<string, unknown>> => {
  const response = await axios.post(`${BASE_API_URL}${path}`, body, {
    withCredentials: true,
  });
  return response.data as Record<string, unknown>;
};

export const fetchFusionExportStatus = async (): Promise<SystemJobStatus> => {
  const response = await axios.get(`${BASE_API_URL}/system/fusion/export/status`, {
    withCredentials: true,
  });
  return response.data as SystemJobStatus;
};

export const fetchFusionEvalStatus = async (): Promise<SystemJobStatus> => {
  const response = await axios.get(`${BASE_API_URL}/system/fusion/eval/status`, {
    withCredentials: true,
  });
  return response.data as SystemJobStatus;
};

export const startFusionExport = async (): Promise<{ message?: string }> => {
  const response = await axios.post(
    `${BASE_API_URL}/system/fusion/export`,
    {},
    { withCredentials: true },
  );
  return response.data as { message?: string };
};

export const startFusionEval = async (): Promise<{ message?: string }> => {
  const response = await axios.post(
    `${BASE_API_URL}/system/fusion/eval`,
    {},
    { withCredentials: true },
  );
  return response.data as { message?: string };
};

export const downloadLatestFusionExport = (): void => {
  window.open(
    `${BASE_API_URL}/system/fusion/export/download`,
    '_blank',
    'noopener,noreferrer',
  );
};

/** Long-form CSV from the last successful fusion eval (section / metric / value). */
export const downloadLatestFusionEvalReport = (): void => {
  window.open(
    `${BASE_API_URL}/system/fusion/eval/download`,
    '_blank',
    'noopener,noreferrer',
  );
};

export const fetchBirdnetFifoSnapshot = async (): Promise<BirdnetFifoPayload> => {
  const response = await axios.get(`${BASE_API_URL}/system/diagnostics/birdnet-fifo`, {
    withCredentials: true,
  });
  return response.data as BirdnetFifoPayload;
};

export const seedSpeciesRegistry = async (): Promise<Record<string, unknown>> =>
  postSystemAction('/system/species-registry/seed');

export const backfillSpeciesRegistry = async (): Promise<Record<string, unknown>> =>
  postSystemAction('/system/species-registry/backfill', { dry_run: false });

export const enrichSpeciesRegistryMetadata = async (): Promise<Record<string, unknown>> =>
  postSystemAction('/system/species-registry/enrich-metadata/start', {
    limit: 300,
    retry_failed_only: false,
  });

export const materializeSpeciesAllowlist = async (): Promise<Record<string, unknown>> =>
  postSystemAction('/system/species-registry/materialize-allowlist', {
    dry_run: false,
    fill_metadata: true,
  });

export const mergeDuplicateSpecies = async (): Promise<Record<string, unknown>> =>
  postSystemAction('/system/merge-duplicate-species');

export const reconcileSpeciesCatalog = async (): Promise<Record<string, unknown>> =>
  postSystemAction('/system/species-catalog/reconcile', { dry_run: false });

export const previewBrokenVideosPurge = async (): Promise<Record<string, unknown>> =>
  postSystemAction('/system/diagnostics/broken-videos/purge', {
    dry_run: true,
    max_scan: 200_000,
  });

export const purgeBrokenVideosBatch = async (
  confirmText: string,
): Promise<Record<string, unknown>> =>
  postSystemAction('/system/diagnostics/broken-videos/purge', {
    dry_run: false,
    confirm_text: confirmText,
    limit: 500,
  });

export const previewNoSpeciesVideosPurge = async (): Promise<Record<string, unknown>> =>
  postSystemAction('/system/diagnostics/no-species-videos/purge', { dry_run: true });

export const purgeNoSpeciesVideosBatch = async (
  confirmText: string,
): Promise<Record<string, unknown>> =>
  postSystemAction('/system/diagnostics/no-species-videos/purge', {
    dry_run: false,
    confirm_text: confirmText,
    limit: 500,
  });

/** Lightweight: only species with count > 0 (for Settings exclude list). */
export const fetchObservedSpecies = async (): Promise<Array<{ id: number; name: string; count: number }>> => {
  const response = await axios.get(`${BASE_API_URL}/species/observed`);
  return response.data;
};

/** Species present on recordings (VideoSpecies); use for track regen picker. */
export const fetchTrackRegenSpeciesOptions = async (): Promise<
  Array<{ id: number; name: string; count: number }>
> => {
  const response = await axios.get(`${BASE_API_URL}/species/track-regen-options`);
  return response.data;
};

export interface TrackRegenerationJobStatus {
  status: string;
  result?: unknown;
  error?: string | null;
  progress?: unknown;
}

export const fetchTrackRegenerationStatus =
  async (): Promise<TrackRegenerationJobStatus> => {
    const response = await axios.get(
      `${BASE_API_URL}/system/regenerate-tracks/status`,
      { withCredentials: true },
    );
    return response.data;
  };

/** Перегенерация YOLO-треков для одной записи (только админ при двух паролях). */
export const regenerateTracksForSingleVideo = async (
  videoId: number,
  options?: { force?: boolean },
): Promise<{ message: string; started: boolean; video_id: number }> => {
  const response = await axios.post(
    `${BASE_API_URL}/videos/${videoId}/regenerate-tracks`,
    { force: options?.force === true },
    { withCredentials: true, timeout: JOB_STATUS_POLL_TIMEOUT_MS },
  );
  return response.data;
};

export interface SpectrogramRegenerationJobStatus {
  status: string;
  result?: unknown;
  error?: string | null;
  progress?: unknown;
}

export const fetchSpectrogramRegenerationStatus =
  async (): Promise<SpectrogramRegenerationJobStatus> => {
    const response = await axios.get(
      `${BASE_API_URL}/system/regenerate-spectrograms/status`,
      { withCredentials: true },
    );
    return response.data;
  };

/** Пересборка спектрограммы для одной записи (только админ при двух паролях). */
export const regenerateSpectrogramForSingleVideo = async (
  videoId: number,
): Promise<{ message: string; started: boolean; video_id: number }> => {
  const response = await axios.post(
    `${BASE_API_URL}/videos/${videoId}/regenerate-spectrogram`,
    {},
    { withCredentials: true, timeout: JOB_STATUS_POLL_TIMEOUT_MS },
  );
  return response.data;
};

export interface MigrationCalendarData {
  species: Array<{
    id: number | null;
    name: string;
    image_url: string | null;
    monthly_counts: number[];
    total: number;
  }>;
  month_labels: string[];
  catalog?: 'observed' | 'dataset' | 'full_eu';
}

export const fetchMigrationCalendar = async (params?: {
  start_year?: number;
  end_year?: number;
  start_date?: string;
  end_date?: string;
  catalog?: 'observed' | 'dataset' | 'full_eu' | 'active' | 'full';
}): Promise<MigrationCalendarData> => {
  const response = await axios.get(`${BASE_API_URL}/migration-calendar`, {
    params: params || {},
  });
  return response.data;
};

export const fetchOverviewData = async (
  date: string,
): Promise<OverviewData> => {
  const response = await axios.get(`${BASE_API_URL}/overview`, {
    params: {
      date,
    },
  });
  return response.data;
};

export const fetchSpeciesSummary = async (
  speciesId: number,
): Promise<SpeciesSummary> => {
  const response = await axios.get(
    `${BASE_API_URL}/species/${speciesId}/summary`,
  );
  return response.data;
};

export interface RefreshSpeciesMetadataResponse {
  ok: boolean;
  species_id: number;
  name: string;
  image_url: string | null;
  description: string | null;
  metadata_source: string | null;
  metadata_source_url: string | null;
}

/** Перезапрос фото/описания для одной карточки вида (нужен пароль настроек, withCredentials). */
export const refreshSpeciesMetadata = async (
  speciesId: number,
): Promise<RefreshSpeciesMetadataResponse> => {
  const response = await axios.post<RefreshSpeciesMetadataResponse>(
    `${BASE_API_URL}/species/${speciesId}/refresh-metadata`,
    {},
    { withCredentials: true },
  );
  return response.data;
};

export interface TuningTargetEntry {
  id: number;
  name: string;
  observed_count: number;
  in_dataset: boolean;
  in_full_catalog: boolean;
}

export interface TuningTargetsResponse {
  ids: number[];
  targets: TuningTargetEntry[];
}

export const fetchTuningTargets = async (): Promise<TuningTargetsResponse> => {
  const response = await axios.get(`${BASE_API_URL}/species/tuning-targets`, {
    withCredentials: true,
  });
  return response.data;
};

export const setSpeciesTuningTarget = async (
  speciesId: number,
  enabled: boolean,
): Promise<{ ok: boolean; species_id: number; enabled: boolean; tuning_target_species_ids: number[] }> => {
  const response = await axios.post(
    `${BASE_API_URL}/species/${speciesId}/tuning-target`,
    { enabled },
    { withCredentials: true },
  );
  return response.data;
};

export const fetchTuningTargetsExport = async (
  format: 'json' | 'csv' = 'json',
): Promise<{ count: number; targets: Array<{ id: number; name: string }> }> => {
  const response = await axios.get(
    `${BASE_API_URL}/system/species-registry/tuning-targets/export`,
    {
      params: { format },
      withCredentials: true,
    },
  );
  return response.data;
};

export interface XenoCantoRecording {
  id: number | string;
  file: string;
  en?: string;
  type?: string;
  rec?: string;
  cnt?: string;
}

export const fetchXenoCantoRecordings = async (
  speciesId: number,
): Promise<{
  recordings: XenoCantoRecording[];
  species_name: string;
  xeno_canto_search_url: string | null;
}> => {
  const response = await axios.get(
    `${BASE_API_URL}/species/${speciesId}/xeno-canto`,
  );
  return response.data;
};

export interface UnknownDetection {
  id: number;
  video_id: number;
  species_id: number;
  species_name: string;
  confidence: number;
  start_time: string;
  end_time: string;
  source: string;
  detection_provider?: string;
  image_url?: string;
  review_state?: 'pending' | 'reviewed' | 'not_applicable';
  review_reason?: 'low_confidence' | 'generic_bird' | string;
  review_source?: string;
}

export interface ReviewQueueDeletePreviewVideo {
  video_id: number;
  video_path: string | null;
  start_time: string | null;
  end_time: string | null;
  has_video_path: boolean;
  file_exists: boolean;
  recording_dir: string | null;
  unknown_count: number;
  unknown_ids: number[];
  species_names: string[];
  review_reasons: string[];
}

export interface ReviewQueueDeletePreview {
  confirmation_phrase: string;
  date: string;
  time_of_day: string;
  hour: number | null;
  unknown_count: number;
  video_count: number;
  unknown_ids: number[];
  video_ids: number[];
  missing_video_ids: number[];
  videos: ReviewQueueDeletePreviewVideo[];
}

export const fetchUnknowns = async (
  startTime: Dayjs,
  endTime: Dayjs,
  limit = 100,
): Promise<UnknownDetection[]> => {
  const response = await axios.get(`${BASE_API_URL}/unknowns`, {
    params: {
      start_time: startTime.unix(),
      end_time: endTime.unix(),
      limit,
    },
  });
  return response.data;
};

export const fetchUnknownsForObserverDate = async (
  date: string,
  options?: { timeOfDay?: TimeOfDay; hour?: number | null; limit?: number },
): Promise<UnknownDetection[]> => {
  const response = await axios.get(`${BASE_API_URL}/unknowns`, {
    params: {
      date,
      limit: options?.limit ?? 100,
      ...(options?.hour != null
        ? { hour: options.hour }
        : { time_of_day: options?.timeOfDay ?? 'all' }),
    },
  });
  return response.data;
};

/** Download monthly PDF report. month: YYYY-MM */
export const downloadReportPdf = async (month: string): Promise<void> => {
  const url = `${BASE_API_URL}/report/pdf?month=${encodeURIComponent(month)}`;
  const res = await fetch(url);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: res.statusText }));
    throw new Error(err.error || res.statusText);
  }
  const blob = await res.blob();
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = `birdlense_report_${month.replace('-', '')}.pdf`;
  a.click();
  URL.revokeObjectURL(a.href);
};

export const updateDetectionSpecies = async (
  detectionId: number,
  speciesId: number,
  source?: 'unknowns' | 'video',
  applyScope?: 'single_track' | 'whole_visit' | 'legacy_fanout',
): Promise<{ message: string; species_id: number; updated_count?: number }> => {
  const response = await axios.patch(
    `${BASE_API_URL}/detections/${detectionId}`,
    {
      species_id: speciesId,
      source,
      ...(applyScope ? { apply_scope: applyScope } : {}),
    },
    { withCredentials: true },
  );
  return response.data;
};

/** Confirm detection: mark as verified (manually_corrected), remove from Unknowns. */
export const confirmDetection = async (
  detectionId: number,
  source?: 'unknowns' | 'video',
): Promise<{ message: string; updated_count: number }> => {
  const response = await axios.post(
    `${BASE_API_URL}/detections/${detectionId}/confirm`,
    { source },
    { withCredentials: true },
  );
  return response.data;
};

export const previewReviewQueueDelete = async (params: {
  date: string;
  timeOfDay: TimeOfDay;
  hour?: number | null;
  unknownIds: number[];
}): Promise<ReviewQueueDeletePreview> => {
  const response = await axios.post(`${BASE_API_URL}/system/review-queue/delete-preview`, {
    date: params.date,
    time_of_day: params.timeOfDay,
    ...(params.hour != null ? { hour: params.hour } : {}),
    unknown_ids: params.unknownIds,
  });
  return response.data;
};

export const deleteReviewQueueVideos = async (params: {
  date: string;
  timeOfDay: TimeOfDay;
  hour?: number | null;
  unknownIds: number[];
  confirmText: string;
}): Promise<{
  message: string;
  deletedCount: number;
  deletedVideoIds: number[];
  deletedDirs: number;
  deletedFiles: number;
  deletedSize: number;
  confirmation_phrase: string;
}> => {
  const response = await axios.post(`${BASE_API_URL}/system/review-queue/delete`, {
    date: params.date,
    time_of_day: params.timeOfDay,
    ...(params.hour != null ? { hour: params.hour } : {}),
    unknown_ids: params.unknownIds,
    confirm_text: params.confirmText,
  });
  return response.data;
};

export type CorrectionHistoryEntry = {
  id: number;
  created_at: string;
  action: 'correct_species' | 'confirm_species';
  source: 'unknowns' | 'video' | 'other';
  detection_id: number | null;
  from_species_name?: string | null;
  to_species_name?: string | null;
  updated_count?: number;
};

export const fetchRecentCorrections = async (limit = 10): Promise<CorrectionHistoryEntry[]> => {
  const response = await axios.get(`${BASE_API_URL}/corrections/recent`, {
    params: { limit },
    withCredentials: true,
  });
  return response.data;
};

export const mergeVideoSpecies = async (
  videoId: string | number,
  speciesId: number,
): Promise<{ message: string; species_id: number; updated_count: number }> => {
  const response = await axios.post(
    `${BASE_API_URL}/videos/${videoId}/merge-species`,
    { species_id: speciesId },
    { withCredentials: true },
  );
  return response.data;
};
