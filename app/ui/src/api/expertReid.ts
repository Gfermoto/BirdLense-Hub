import axios from 'axios';
import { BASE_API_URL } from './client';

export type ExpertQueueItem = {
  id: number;
  task_type: string;
  status: string;
  video_species_id: number | null;
  related_video_species_id: number | null;
  similarity: number | null;
  species_name: string | null;
  video_id: number | null;
  payload?: Record<string, unknown>;
};

export type ReidGalleryCluster = {
  cluster_id: string;
  species_id: number | null;
  min_pairwise_similarity: number;
  member_count: number;
  members: Array<{
    video_species_id: number;
    video_id: number;
    track_id: number | null;
    track_duration_sec: number;
    species_name: string | null;
  }>;
};

const withCreds = { withCredentials: true as const };

export async function fetchReidGalleryStatus() {
  const { data } = await axios.get<{
    reid_gallery_enabled: boolean;
    reid_track_clustering_enabled: boolean;
    reid_expert_queue_enabled: boolean;
  }>(`${BASE_API_URL}/reid/gallery/status`, withCreds);
  return data;
}

export async function fetchReidGallery(params?: {
  video_id?: number;
  species_id?: number;
  limit?: number;
}) {
  const { data } = await axios.get<{
    enabled: boolean;
    clusters: ReidGalleryCluster[];
    message?: string;
  }>(`${BASE_API_URL}/reid/gallery`, { ...withCreds, params });
  return data;
}

export async function fetchExpertQueue(params?: { status?: string; limit?: number; sync?: boolean }) {
  const { data } = await axios.get<{ enabled: boolean; items: ExpertQueueItem[]; count: number }>(
    `${BASE_API_URL}/expert/queue`,
    {
      ...withCreds,
      params: { sync: params?.sync === false ? 0 : 1, ...params },
    },
  );
  return data;
}

export async function resolveExpertTask(body: {
  task_id: number;
  action: 'dismiss' | 'confirm_species' | 'merge_tracks' | 'merge_profiles';
  species_id?: number;
  target_profile_id?: number;
  source_profile_id?: number;
  note?: string;
}) {
  const { data } = await axios.post(`${BASE_API_URL}/expert/resolve`, body, withCreds);
  return data;
}
