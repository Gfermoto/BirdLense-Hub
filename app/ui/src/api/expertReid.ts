import { apiClient } from './client';

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

export async function fetchReidGalleryStatus() {
  const { data } = await apiClient.get<{
    reid_gallery_enabled: boolean;
    reid_track_clustering_enabled: boolean;
    reid_expert_queue_enabled: boolean;
  }>('/reid/gallery/status');
  return data;
}

export async function fetchReidGallery(params?: {
  video_id?: number;
  species_id?: number;
  limit?: number;
}) {
  const { data } = await apiClient.get<{
    enabled: boolean;
    clusters: ReidGalleryCluster[];
    message?: string;
  }>('/reid/gallery', { params });
  return data;
}

export async function fetchExpertQueue(params?: { status?: string; limit?: number; sync?: boolean }) {
  const { data } = await apiClient.get<{ enabled: boolean; items: ExpertQueueItem[]; count: number }>(
    '/expert/queue',
    { params: { sync: params?.sync === false ? 0 : 1, ...params } },
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
  const { data } = await apiClient.post('/expert/resolve', body);
  return data;
}
