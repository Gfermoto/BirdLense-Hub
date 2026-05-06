import axios from 'axios';
import type { TimeOfDay } from '../utils/timeUtils';
import type { OverviewData, Species, SpeciesSummary } from '../types';
import { BASE_API_URL } from './client';

export const fetchBirdDirectory = async (): Promise<Species[]> => {
  const response = await axios.get(`${BASE_API_URL}/species`);
  return response.data;
};

/** Lightweight: only species with count > 0 (for Settings exclude list). */
export const fetchObservedSpecies = async (): Promise<
  Array<{ id: number; name: string; count: number }>
> => {
  const response = await axios.get(`${BASE_API_URL}/species/observed`);
  return response.data;
};

/** Species present on recordings (VideoSpecies); use for track regen picker. */
export const fetchTrackRegenSpeciesOptions = async (): Promise<
  Array<{ id: number; name: string; count: number }>
> => {
  const response = await axios.get(
    `${BASE_API_URL}/species/track-regen-options`,
  );
  return response.data;
};

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
  async (): Promise<TrackRegenerationJobStatus> => {
    const response = await axios.get(
      `${BASE_API_URL}/system/regenerate-tracks/status`,
      { withCredentials: true },
    );
    return response.data;
  };

export interface SpectrogramRegenProgress {
  processed?: number;
  total?: number;
  generated?: number;
  failed?: number;
  skipped?: number;
  current_video?: string | null;
  current_video_id?: number | null;
  active_request_video_id?: number | null;
  phase?: string | null;
}

export interface SpectrogramRegenerationJobStatus {
  status: string;
  result?: unknown;
  error?: string | null;
  progress?: SpectrogramRegenProgress | null;
}

export const fetchSpectrogramRegenerationStatus =
  async (): Promise<SpectrogramRegenerationJobStatus> => {
    const response = await axios.get(
      `${BASE_API_URL}/system/regenerate-spectrograms/status`,
      { withCredentials: true },
    );
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
): Promise<{
  ok: boolean;
  species_id: number;
  enabled: boolean;
  tuning_target_species_ids: number[];
}> => {
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

export const updateDetectionNickname = async (
  detectionId: number,
  individualNickname: string | null,
): Promise<{ message: string; detection_id: number; individual_nickname: string | null }> => {
  const response = await axios.patch(
    `${BASE_API_URL}/detections/${detectionId}`,
    {
      individual_nickname: individualNickname,
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
  const response = await axios.post(
    `${BASE_API_URL}/system/review-queue/delete-preview`,
    {
      date: params.date,
      time_of_day: params.timeOfDay,
      ...(params.hour != null ? { hour: params.hour } : {}),
      unknown_ids: params.unknownIds,
    },
  );
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
  const response = await axios.post(
    `${BASE_API_URL}/system/review-queue/delete`,
    {
      date: params.date,
      time_of_day: params.timeOfDay,
      ...(params.hour != null ? { hour: params.hour } : {}),
      unknown_ids: params.unknownIds,
      confirm_text: params.confirmText,
    },
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

export const fetchRecentCorrections = async (
  limit = 10,
): Promise<CorrectionHistoryEntry[]> => {
  const response = await axios.get(`${BASE_API_URL}/corrections/recent`, {
    params: { limit },
    withCredentials: true,
  });
  return response.data;
};
