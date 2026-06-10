/** Video details, neighbors, fusion trace, storage day navigation (#343). */
import type { TrackFrame, Video } from '../types';
import {
  BASE_API_URL,
  JOB_STATUS_POLL_TIMEOUT_MS,
  apiFetch,
} from './client';

export const fetchVideo = async (id: string): Promise<Video> =>
  apiFetch<Video>(`${BASE_API_URL}/videos/${id}`);

/** Покадровые bbox — отдельно от GET /videos/:id (лёгкая первая отрисовка страницы). */
export const fetchVideoDetectionFrames = async (id: string) =>
  apiFetch<{
    tracks: Array<{
      id: number | null;
      species_id: number;
      start_time: number;
      end_time: number;
      frames: TrackFrame[];
    }>;
  }>(`${BASE_API_URL}/videos/${id}/detection-frames`);

export type VideoReidMatchItem = {
  video_species_id: number;
  track_id?: number | null;
  species_name?: string | null;
  individual_nickname?: string | null;
  candidate_video_species_id?: number | null;
  candidate_video_id?: number | null;
  candidate_track_id?: number | null;
  candidate_species_name?: string | null;
  candidate_nickname?: string | null;
  similarity: number;
  decision?: string;
  policy_decision?: string;
  policy_reasons?: string[];
  effective_threshold?: number | null;
  cross_camera?: boolean;
  hours_apart?: number | null;
};

export type VideoReidMatchPayload = {
  schema: string;
  available: boolean;
  video_id: number;
  message?: string;
  policy?: Record<string, unknown>;
  contract_ready?: boolean;
  matches: VideoReidMatchItem[];
};

export const fetchVideoReidMatch = async (
  id: string,
): Promise<VideoReidMatchPayload> =>
  apiFetch(`${BASE_API_URL}/videos/${id}/reid-match`);

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

export const fetchVideoNeighbors = async (
  id: string,
): Promise<VideoNeighbors> => {
  const tzOffset = new Date().getTimezoneOffset();
  const q = new URLSearchParams({
    day_scope: 'local',
    tz_offset_minutes: String(tzOffset),
    cross_day: '1',
  });
  return apiFetch(`${BASE_API_URL}/videos/${id}/neighbors?${q}`);
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

export const fetchVideoFusionTrace = async (
  id: number,
): Promise<FusionTracePayload> =>
  apiFetch(`${BASE_API_URL}/videos/${id}/fusion-trace`);

export const fetchNearestRecordingDay = async (
  date: string,
  direction: 'prev' | 'next',
): Promise<{
  date: string | null;
  direction: 'prev' | 'next';
  found: boolean;
}> => {
  const q = new URLSearchParams({ date, direction });
  return apiFetch(`${BASE_API_URL}/storage/nearest-recording-day?${q}`);
};

/** Mark recording as favorite (retention may skip it when protect favorites is on). Contributor/admin. */
export type PatchVideoRecordingBody = {
  favorite?: boolean;
  behavior_label?: string | null;
  behavior_confidence?: number | null;
};

export const patchVideoRecording = async (
  id: number,
  body: PatchVideoRecordingBody,
): Promise<Record<string, unknown>> =>
  apiFetch(`${BASE_API_URL}/videos/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });

export const patchVideoFavorite = async (
  id: number,
  favorite: boolean,
): Promise<Record<string, unknown>> => {
  return patchVideoRecording(id, { favorite });
};

/** Delete video recording. Requires contributor or admin access. */
export const deleteVideo = async (id: number): Promise<void> => {
  await apiFetch(`${BASE_API_URL}/videos/${id}`, { method: 'DELETE' });
};

/** Перегенерация YOLO-треков для одной записи (только админ при двух паролях). */
export const regenerateTracksForSingleVideo = async (
  videoId: number,
  options?: { force?: boolean },
): Promise<{ message: string; started: boolean; video_id: number }> =>
  apiFetch(`${BASE_API_URL}/videos/${videoId}/regenerate-tracks`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ force: options?.force === true }),
    signal: AbortSignal.timeout(JOB_STATUS_POLL_TIMEOUT_MS),
  });

export const mergeVideoSpecies = async (
  videoId: string | number,
  speciesId: number,
): Promise<{ message: string; species_id: number; updated_count: number }> =>
  apiFetch(`${BASE_API_URL}/videos/${videoId}/merge-species`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ species_id: speciesId }),
  });
