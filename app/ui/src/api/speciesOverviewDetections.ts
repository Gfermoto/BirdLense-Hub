/** Species directory, overview, detections, bird profiles API (#343, #617). */
import type { TimeOfDay } from '../utils/timeUtils';
import type { OverviewData, Species, SpeciesSummary } from '../types';
import { BASE_API_URL, apiFetch } from './client';

export type SpeciesCatalogScope = 'allowlist' | 'project' | 'observed' | 'all';

export type SpeciesCatalogMeta = {
  db_species_total: number;
  allowlist_total: number;
  listed_allowlist: number;
  allowlist_incomplete: number;
  classifier_engine?: string;
  classifier_class_count?: number;
  project_vocabulary_total?: number;
  listed_project?: number;
  arbitration_vocabulary_total?: number;
  catalog_with_audio?: number;
  catalog_missing_audio?: number;
  catalog_cards?: {
    complete_cards?: number;
    allowlist_total?: number;
    completion_percent?: number;
  };
};

export type SpeciesDirectoryResponse = {
  items: Species[];
  meta: SpeciesCatalogMeta;
};

export function speciesDirectoryItems(
  data: Species[] | SpeciesDirectoryResponse | undefined,
): Species[] {
  if (!data) return [];
  return Array.isArray(data) ? data : data.items;
}

export const fetchBirdDirectory = async (options?: {
  scope?: SpeciesCatalogScope;
  meta?: boolean;
  missing_audio?: boolean;
  catalog_incomplete?: boolean;
}): Promise<Species[] | SpeciesDirectoryResponse> => {
  const q = new URLSearchParams({
    exclude_suspects: '1',
    scope: options?.scope ?? 'project',
  });
  if (options?.meta) q.set('meta', '1');
  if (options?.missing_audio) q.set('missing_audio', '1');
  if (options?.catalog_incomplete) q.set('catalog_incomplete', '1');
  const data = await apiFetch<Species[] | SpeciesDirectoryResponse>(
    `${BASE_API_URL}/species?${q}`,
  );
  if (
    options?.meta &&
    data &&
    typeof data === 'object' &&
    Array.isArray((data as SpeciesDirectoryResponse).items)
  ) {
    return data as SpeciesDirectoryResponse;
  }
  return data as Species[];
};

/** Lightweight: only species with count > 0 (for Settings exclude list). */
export const fetchObservedSpecies = async (): Promise<
  Array<{ id: number; name: string; count: number }>
> => apiFetch(`${BASE_API_URL}/species/observed`);

/** Species present on recordings (VideoSpecies); use for track regen picker. */
export const fetchTrackRegenSpeciesOptions = async (): Promise<
  Array<{ id: number; name: string; count: number }>
> => apiFetch(`${BASE_API_URL}/species/track-regen-options`);

/** Поля прогресса из `/system/regenerate-tracks/status` (воркер + single-video pre-queue). */
export interface TrackRegenProgress {
  processed?: number;
  total?: number;
  generated?: number;
  failed?: number;
  skipped?: number;
  current_video?: string | null;
  current_video_id?: number | null;
  active_request_video_id?: number | null;
  phase?: string | null;
  /** Оценка числа YOLO-проходов (декодированных кадров / frame_step) для прогресс-бара. */
  yolo_frames_done?: number | null;
  yolo_frames_total?: number | null;
  regen_params?: Record<string, unknown>;
}

export interface TrackRegenerationJobStatus {
  status: string;
  result?: unknown;
  error?: string | null;
  progress?: TrackRegenProgress | null;
}

export const fetchTrackRegenerationStatus =
  async (): Promise<TrackRegenerationJobStatus> =>
    apiFetch(`${BASE_API_URL}/system/regenerate-tracks/status`);

export const fetchOverviewData = async (
  date: string,
): Promise<OverviewData> => {
  const q = new URLSearchParams({ date });
  return apiFetch(`${BASE_API_URL}/overview?${q}`);
};

export const fetchSpeciesSummary = async (
  speciesId: number,
): Promise<SpeciesSummary> =>
  apiFetch(`${BASE_API_URL}/species/${speciesId}/summary`);

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
): Promise<RefreshSpeciesMetadataResponse> =>
  apiFetch(`${BASE_API_URL}/species/${speciesId}/refresh-metadata`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({}),
  });

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

export const fetchTuningTargets = async (): Promise<TuningTargetsResponse> =>
  apiFetch(`${BASE_API_URL}/species/tuning-targets`);

export const setSpeciesTuningTarget = async (
  speciesId: number,
  enabled: boolean,
): Promise<{
  ok: boolean;
  species_id: number;
  enabled: boolean;
  tuning_target_species_ids: number[];
}> =>
  apiFetch(`${BASE_API_URL}/species/${speciesId}/tuning-target`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ enabled }),
  });

export const fetchTuningTargetsExport = async (
  format: 'json' | 'csv' = 'json',
): Promise<{ count: number; targets: Array<{ id: number; name: string }> }> => {
  const q = new URLSearchParams({ format });
  return apiFetch(
    `${BASE_API_URL}/system/species-registry/tuning-targets/export?${q}`,
  );
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
}> => apiFetch(`${BASE_API_URL}/species/${speciesId}/xeno-canto`);

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
): Promise<{ message: string; species_id: number; updated_count?: number }> =>
  apiFetch(`${BASE_API_URL}/detections/${detectionId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      species_id: speciesId,
      source,
      ...(applyScope ? { apply_scope: applyScope } : {}),
    }),
  });

export const updateDetectionNickname = async (
  detectionId: number,
  individualNickname: string | null,
): Promise<{ message: string; detection_id: number; individual_nickname: string | null }> =>
  apiFetch(`${BASE_API_URL}/detections/${detectionId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ individual_nickname: individualNickname }),
  });

export type BirdProfile = {
  id: number;
  display_name: string;
  species_id: number | null;
  species_name?: string | null;
  avatar_url: string | null;
  status: string;
  created_at?: string | null;
};

export type BirdProfileSummary = {
  profile_id: number;
  display_name: string;
  status: string;
  total_detections: number;
  unique_video_count: number;
  first_seen?: string | null;
  last_seen?: string | null;
  top_species: Array<{ name: string; count: number }>;
  top_behaviors: Array<{ label: string; count: number }>;
  recent_detections: Array<{
    detection_id: number;
    video_id: number;
    species_name?: string | null;
    confidence: number;
    individual_nickname?: string | null;
    behavior_label?: string | null;
  }>;
};

export const fetchBirdProfiles = async (params?: {
  query?: string;
  speciesId?: number;
  limit?: number;
}): Promise<{ items: BirdProfile[] }> => {
  const q = new URLSearchParams();
  if (params?.query) q.set('query', params.query);
  if (params?.speciesId) q.set('species_id', String(params.speciesId));
  if (params?.limit) q.set('limit', String(params.limit));
  const suffix = q.toString();
  return apiFetch(
    `${BASE_API_URL}/bird-profiles${suffix ? `?${suffix}` : ''}`,
  );
};

export const createBirdProfile = async (body: {
  display_name: string;
  species_id?: number | null;
  avatar_url?: string | null;
  status?: string;
}): Promise<BirdProfile> =>
  apiFetch(`${BASE_API_URL}/bird-profiles`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });

export const patchBirdProfile = async (
  profileId: number,
  body: {
    display_name?: string;
    avatar_url?: string | null;
    status?: string;
  },
): Promise<BirdProfile> =>
  apiFetch(`${BASE_API_URL}/bird-profiles/${profileId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });

export const assignDetectionBirdProfile = async (
  detectionId: number,
  birdProfileId: number,
): Promise<{ detection_id: number; video_id: number; bird_profile_id: number; updated_count: number }> =>
  apiFetch(`${BASE_API_URL}/detections/${detectionId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ bird_profile_id: birdProfileId }),
  });

export const deleteBirdProfile = async (
  profileId: number,
): Promise<{
  id: number;
  display_name: string;
  unlinked_detections: number;
}> =>
  apiFetch(`${BASE_API_URL}/bird-profiles/${profileId}`, {
    method: 'DELETE',
  });

export const fetchBirdProfileSummary = async (
  profileId: number,
  recentLimit = 8,
): Promise<BirdProfileSummary> => {
  const q = new URLSearchParams({ recent_limit: String(recentLimit) });
  return apiFetch(
    `${BASE_API_URL}/bird-profiles/${profileId}/summary?${q}`,
  );
};

export const clearDetectionBirdProfile = async (
  detectionId: number,
): Promise<{
  detection_id: number;
  video_id: number;
  bird_profile_id: null;
  updated_count: number;
}> =>
  apiFetch(`${BASE_API_URL}/detections/${detectionId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ bird_profile_id: null }),
  });

export type BirdProfileLinkCandidate = {
  profile_id: number;
  display_name: string;
  species_id: number | null;
  avatar_url: string | null;
  similarity: number;
  similarity_percent: number;
  tier: 'auto' | 'suggest';
  status?: string | null;
};

export type BirdProfileSuggestLinksResponse = {
  schema: string;
  available: boolean;
  thresholds: { high: number; low: number };
  candidates: BirdProfileLinkCandidate[];
  message?: string;
};

export const fetchBirdProfileSuggestLinks = async (
  profileId: number | null,
  body: {
    video_species_id?: number;
    species_id?: number;
    limit?: number;
  },
): Promise<BirdProfileSuggestLinksResponse> => {
  const path =
    profileId && profileId > 0
      ? `${BASE_API_URL}/bird-profiles/${profileId}/suggest-links`
      : `${BASE_API_URL}/bird-profiles/suggest-links`;
  return apiFetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
};

export const recordBirdProfileLinkFeedback = async (body: {
  action: 'confirm' | 'reject';
  candidate_profile_id: number;
  anchor_profile_id?: number | null;
  video_species_id?: number;
  similarity?: number;
}): Promise<{ ok: boolean; label: string }> =>
  apiFetch(`${BASE_API_URL}/bird-profiles/link-feedback`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });

export const mergeBirdProfiles = async (
  targetProfileId: number,
  sourceProfileId: number,
): Promise<{
  target_profile_id: number;
  source_profile_id: number;
  merged_detections: number;
  display_name: string;
}> =>
  apiFetch(`${BASE_API_URL}/bird-profiles/${targetProfileId}/merge`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ source_profile_id: sourceProfileId }),
  });

export const setDetectionSemanticReview = async (
  detectionId: number,
  body: {
    semantic_review_required: boolean;
    semantic_review_note?: string;
    source?: string;
  },
): Promise<{ detection_id: number; required: boolean; review_reason: string | null }> =>
  apiFetch(`${BASE_API_URL}/detections/${detectionId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });

/** Confirm detection: mark as verified (manually_corrected), remove from Unknowns. */
export const confirmDetection = async (
  detectionId: number,
  source?: 'unknowns' | 'video',
): Promise<{ message: string; updated_count: number }> =>
  apiFetch(`${BASE_API_URL}/detections/${detectionId}/confirm`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ source }),
  });

export const deleteDetection = async (
  detectionId: number,
  body?: { source?: 'unknowns' | 'video' | 'timeline'; reason?: string },
): Promise<{
  message: string;
  detection_id: number;
  video_id: number;
  track_id: number | null;
  removed_dataset_crops: number;
}> =>
  apiFetch(`${BASE_API_URL}/detections/${detectionId}`, {
    method: 'DELETE',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body || {}),
  });

export const deleteVisit = async (
  visitId: number,
  body?: { source?: 'unknowns' | 'video' | 'timeline'; reason?: string },
): Promise<{
  message: string;
  visit_id: number;
  deleted_detections: number;
}> =>
  apiFetch(`${BASE_API_URL}/visits/${visitId}`, {
    method: 'DELETE',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body || {}),
  });

export const previewReviewQueueDelete = async (params: {
  date: string;
  timeOfDay: TimeOfDay;
  hour?: number | null;
  unknownIds: number[];
}): Promise<ReviewQueueDeletePreview> =>
  apiFetch(`${BASE_API_URL}/system/review-queue/delete-preview`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      date: params.date,
      time_of_day: params.timeOfDay,
      ...(params.hour != null ? { hour: params.hour } : {}),
      unknown_ids: params.unknownIds,
    }),
  });

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
}> =>
  apiFetch(`${BASE_API_URL}/system/review-queue/delete`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      date: params.date,
      time_of_day: params.timeOfDay,
      ...(params.hour != null ? { hour: params.hour } : {}),
      unknown_ids: params.unknownIds,
      confirm_text: params.confirmText,
    }),
  });

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

export const fetchRecentCorrections = async (
  limit = 10,
): Promise<CorrectionHistoryEntry[]> => {
  const q = new URLSearchParams({ limit: String(limit) });
  return apiFetch(`${BASE_API_URL}/corrections/recent?${q}`);
};
