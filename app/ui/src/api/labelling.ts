import { BASE_API_URL, apiFetch } from './client';

export type LabellingCaseStatus = 'pending' | 'approved' | 'rejected' | 'semantic_review_required';

export type LabellingCase = {
  id: number;
  created_at: string | null;
  updated_at: string | null;
  status: LabellingCaseStatus;
  reason_code: string;
  camera_id: string | null;
  video_id: number | null;
  video_species_id: number | null;
  track_id?: number | null;
  species_name: string | null;
  individual_nickname?: string | null;
  bird_profile_id?: number | null;
  bird_profile_name?: string | null;
  bird_profile_avatar_url?: string | null;
  bird_profile_status?: string | null;
  video_path: string | null;
  video_stream_url?: string | null;
  video_details_url?: string | null;
  bbox?: [number, number, number, number] | null;
  track_frames?: Array<{
    t: number | null;
    bbox: [number, number, number, number];
    bbox_xyxy?: [number, number, number, number];
  }>;
  confidence: number | null;
  blind_score: number | null;
  fallback_ratio: number | null;
  pre_approved?: boolean;
  suggested_species?: string | null;
  payload: Record<string, unknown> | null;
};

export type LabellingCasesResponse = {
  items: LabellingCase[];
  count: number;
};

export const fetchLabellingCases = async (
  status: LabellingCaseStatus | 'all' = 'pending',
  limit = 120,
  withMediaOnly = true,
): Promise<LabellingCasesResponse> => {
  const q = new URLSearchParams();
  if (status !== 'all') q.set('status', status);
  q.set('limit', String(limit));
  if (withMediaOnly) q.set('with_media_only', '1');
  return apiFetch<LabellingCasesResponse>(
    `${BASE_API_URL}/labelling/cases?${q.toString()}`,
  );
};

export const mineLabellingCases = async (body?: {
  lookback_hours?: number;
  max_rows?: number;
  blind_score_threshold?: number;
  fallback_ratio_threshold?: number;
  conf_min?: number;
  conf_max?: number;
}): Promise<{ ok: boolean; created: number; skipped: number }> =>
  apiFetch(`${BASE_API_URL}/labelling/cases/mine`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body || {}),
  });

export const patchLabellingCase = async (
  id: number,
  status: LabellingCaseStatus,
  note?: string,
): Promise<{ id: number; status: LabellingCaseStatus }> =>
  apiFetch(`${BASE_API_URL}/labelling/cases/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ status, note }),
  });

export const exportLabellingCases = async (
  format: 'yolo' | 'coco',
  status: LabellingCaseStatus = 'approved',
): Promise<{ version: string; path: string; format: string }> =>
  apiFetch(`${BASE_API_URL}/labelling/export`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ format, status }),
  });

export const postLabellingFeedback = async (
  id: number,
  body: {
    action: 'reject_box' | 'tag_species' | 'flag_semantic_error';
    species_tag?: string;
  },
): Promise<{ id: number; status: LabellingCaseStatus; action: string }> =>
  apiFetch(`${BASE_API_URL}/labelling/cases/${id}/feedback`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });

export type LabellingBatchOperation =
  | {
      kind: 'feedback';
      case_id: number;
      action: 'reject_box' | 'tag_species' | 'flag_semantic_error';
      species_tag?: string;
    }
  | {
      kind: 'status';
      case_id: number;
      status: LabellingCaseStatus;
      note?: string;
    };

export const postLabellingBatchFeedback = async (
  operations: LabellingBatchOperation[],
): Promise<{ ok: boolean; count: number; processed: Array<{ id: number; status: LabellingCaseStatus }> }> =>
  apiFetch(`${BASE_API_URL}/labelling/batch-feedback`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ operations }),
  });
