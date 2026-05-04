/** Video details, neighbors, fusion trace, storage day navigation (#343). */
import axios from 'axios';
import type { TrackFrame } from '../types';
import { BASE_API_URL, JOB_STATUS_POLL_TIMEOUT_MS, csrfFetch } from './client';

export const fetchVideo = async (id: string) => {
  const response = await axios.get(`${BASE_API_URL}/videos/${id}`);
  return response.data;
};

/** Покадровые bbox — отдельно от GET /videos/:id (лёгкая первая отрисовка страницы). */
export const fetchVideoDetectionFrames = async (id: string) => {
  const response = await axios.get(
    `${BASE_API_URL}/videos/${id}/detection-frames`,
  );
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

export type VideoActionEvent = {
  label: string;
  source?: string;
  time_offset?: number;
  time?: string;
  confidence?: number;
  evidence?: {
    species_name?: string | null;
    reason?: string;
    [key: string]: unknown;
  };
};

export type VideoActionEventsPayload = {
  schema: string;
  video_id: number;
  available: boolean;
  message?: string;
  events: VideoActionEvent[];
};

export const fetchVideoActionEvents = async (
  id: string,
): Promise<VideoActionEventsPayload> => {
  const response = await axios.get(`${BASE_API_URL}/videos/${id}/action-events`);
  return response.data;
};

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
): Promise<VideoReidMatchPayload> => {
  const response = await axios.get(`${BASE_API_URL}/videos/${id}/reid-match`, {
    withCredentials: true,
  });
  return response.data;
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

export const fetchVideoNeighbors = async (
  id: string,
): Promise<VideoNeighbors> => {
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

export const fetchVideoFusionTrace = async (
  id: number,
): Promise<FusionTracePayload> => {
  const response = await axios.get(
    `${BASE_API_URL}/videos/${id}/fusion-trace`,
    {
      withCredentials: true,
    },
  );
  return response.data;
};

export const fetchNearestRecordingDay = async (
  date: string,
  direction: 'prev' | 'next',
): Promise<{
  date: string | null;
  direction: 'prev' | 'next';
  found: boolean;
}> => {
  const response = await axios.get(
    `${BASE_API_URL}/storage/nearest-recording-day`,
    {
      params: { date, direction },
    },
  );
  return response.data;
};

/** Mark recording as favorite (retention may skip it when protect favorites is on). Contributor/admin. */
export const patchVideoFavorite = async (
  id: number,
  favorite: boolean,
): Promise<{ favorite?: boolean } & Record<string, unknown>> => {
  const response = await axios.patch(
    `${BASE_API_URL}/videos/${id}`,
    { favorite },
    { withCredentials: true },
  );
  return response.data;
};

/** Delete video recording. Requires contributor or admin access. */
export const deleteVideo = async (id: number): Promise<void> => {
  const res = await csrfFetch(`${BASE_API_URL}/videos/${id}`, {
    method: 'DELETE',
    credentials: 'include',
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: res.statusText }));
    throw new Error(err.error || res.statusText);
  }
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
