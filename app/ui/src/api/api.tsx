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

// Relative path = same origin (works with any host/IP). При SSR/тестах — из env или дефолт.
export const BASE_URL =
  typeof window !== 'undefined'
    ? ''
    : (import.meta.env?.VITE_BASE_URL as string) || '';
export const BASE_API_URL = `${BASE_URL}/api/ui`;

axios.defaults.timeout = 30000;

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
  if (url.startsWith('http://') || url.startsWith('https://')) return url;
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
    const d = new Date(iso);
    return d.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' });
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
      id: number;
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
  birdnet_url?: string | null;
  heimdall_url?: string | null;
}> => {
  const response = await axios.get(`${BASE_API_URL}/status`);
  return response.data;
};

export const fetchFeedInfo = async (): Promise<{
  last_dispense_at: string | null;
  donate_url: string | null;
  feed_source?: string;
  scale?: {
    weight: number;
    unit?: string;
    updated_at?: string;
    source?: string;
  } | null;
}> => {
  const response = await axios.get(`${BASE_API_URL}/feed/info`);
  return response.data;
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

export type ConfigAudit = {
  deprecated_keys_present: string[];
  unknown_keys: string[];
  telegram: {
    proxy_type: string;
    send_photo: boolean;
  };
  gallery: {
    enabled: boolean;
    upload_url: string | null;
    min_confidence?: number;
  };
  mapping: {
    gray_to_grey_ok: boolean;
    pairs: Record<string, string | undefined>;
  };
  heimdall: {
    url: string | null;
    configured: boolean;
    probe?: {
      configured: boolean;
      reachable: boolean;
      http_status?: number | null;
      latency_ms?: number | null;
      title?: string | null;
      version?: string | null;
      error?: string | null;
    };
  };
};

export const fetchConfigAudit = async (): Promise<ConfigAudit> => {
  const response = await axios.get(`${BASE_API_URL}/system/config-audit`, {
    withCredentials: true,
  });
  return response.data;
};

export type ObservabilityPayload = {
  notify_preview_24h: Record<string, number>;
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

/** Download SQLite DB backup from System page. */
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

/** Lightweight: only species with count > 0 (for Settings exclude list). */
export const fetchObservedSpecies = async (): Promise<Array<{ id: number; name: string; count: number }>> => {
  const response = await axios.get(`${BASE_API_URL}/species/observed`);
  return response.data;
};

export interface MigrationCalendarData {
  species: Array<{
    id: number;
    name: string;
    image_url: string | null;
    monthly_counts: number[];
    total: number;
  }>;
  month_labels: string[];
}

export const fetchMigrationCalendar = async (params?: {
  start_year?: number;
  end_year?: number;
  start_date?: string;
  end_date?: string;
  catalog?: 'active' | 'full';
  evidence?: 'all' | 'video';
}): Promise<MigrationCalendarData> => {
  const response = await axios.get(`${BASE_API_URL}/migration-calendar`, {
    params: params || {},
  });
  return response.data;
};

export const fetchOverviewData = async (
  date: string,
): Promise<OverviewData> => {
  const localStart = new Date(date + 'T00:00:00');
  const localEnd = new Date(date + 'T23:59:59.999');
  const response = await axios.get(`${BASE_API_URL}/overview`, {
    params: {
      start_time: Math.floor(localStart.getTime() / 1000),
      end_time: Math.floor(localEnd.getTime() / 1000),
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
): Promise<{ message: string; species_id: number; updated_count?: number }> => {
  const response = await axios.patch(
    `${BASE_API_URL}/detections/${detectionId}`,
    { species_id: speciesId, source },
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
