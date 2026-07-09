import { BASE_API_URL, apiFetch } from './client';

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

function queryString(params: Record<string, unknown>): string {
  const q = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== '') {
      q.set(key, String(value));
    }
  }
  const qs = q.toString();
  return qs ? `?${qs}` : '';
}

export async function fetchReidGalleryStatus() {
  return apiFetch<{
    reid_gallery_enabled: boolean;
    reid_track_clustering_enabled: boolean;
    reid_expert_queue_enabled: boolean;
  }>(`${BASE_API_URL}/reid/gallery/status`);
}

export async function fetchReidGallery(params?: {
  video_id?: number;
  species_id?: number;
  limit?: number;
}) {
  return apiFetch<{
    enabled: boolean;
    clusters: ReidGalleryCluster[];
    message?: string;
  }>(`${BASE_API_URL}/reid/gallery${queryString(params ?? {})}`);
}

export async function fetchExpertQueue(params?: {
  status?: string;
  limit?: number;
  sync?: boolean;
}) {
  const query = {
    sync: params?.sync === false ? 0 : 1,
    ...(params?.status !== undefined ? { status: params.status } : {}),
    ...(params?.limit !== undefined ? { limit: params.limit } : {}),
  };
  return apiFetch<{ enabled: boolean; items: ExpertQueueItem[]; count: number }>(
    `${BASE_API_URL}/expert/queue${queryString(query)}`,
  );
}

export async function resolveExpertTask(body: {
  task_id: number;
  action: 'dismiss' | 'confirm_species' | 'merge_tracks' | 'merge_profiles';
  species_id?: number;
  target_profile_id?: number;
  source_profile_id?: number;
  note?: string;
}) {
  return apiFetch(`${BASE_API_URL}/expert/resolve`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
}
