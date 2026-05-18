import { BASE_API_URL, csrfFetch } from './client';

export type LabellingCaseStatus = 'pending' | 'approved' | 'rejected';

export type LabellingCase = {
  id: number;
  created_at: string | null;
  updated_at: string | null;
  status: LabellingCaseStatus;
  reason_code: string;
  camera_id: string | null;
  video_id: number | null;
  video_species_id: number | null;
  species_name: string | null;
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
  behavior_label?: string | null;
  behavior_confidence?: number | null;
  behavior_shadow_label?: string | null;
  behavior_shadow_confidence?: number | null;
  payload: Record<string, unknown> | null;
};

export type LabellingCasesResponse = {
  items: LabellingCase[];
  count: number;
};

export const fetchLabellingCases = async (
  status: LabellingCaseStatus | 'all' = 'pending',
  limit = 120,
): Promise<LabellingCasesResponse> => {
  const q = new URLSearchParams();
  if (status !== 'all') q.set('status', status);
  q.set('limit', String(limit));
  const res = await fetch(`${BASE_API_URL}/labelling/cases?${q.toString()}`, {
    credentials: 'include',
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
};

export const mineLabellingCases = async (body?: {
  lookback_hours?: number;
  max_rows?: number;
  blind_score_threshold?: number;
  fallback_ratio_threshold?: number;
  conf_min?: number;
  conf_max?: number;
}): Promise<{ ok: boolean; created: number; skipped: number }> => {
  const res = await csrfFetch(`${BASE_API_URL}/labelling/cases/mine`, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body || {}),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
};

export const patchLabellingCase = async (
  id: number,
  status: LabellingCaseStatus,
  note?: string,
): Promise<{ id: number; status: LabellingCaseStatus }> => {
  const res = await csrfFetch(`${BASE_API_URL}/labelling/cases/${id}`, {
    method: 'PATCH',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ status, note }),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
};

export const exportLabellingCases = async (
  format: 'yolo' | 'coco',
  status: LabellingCaseStatus = 'approved',
): Promise<{ version: string; path: string; format: string }> => {
  const res = await csrfFetch(`${BASE_API_URL}/labelling/export`, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ format, status }),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
};

export const postLabellingFeedback = async (
  id: number,
  body: { action: 'confirm_behavior' | 'reject_box' | 'tag_species'; behavior_tag?: string; species_tag?: string },
): Promise<{ id: number; status: LabellingCaseStatus; action: string }> => {
  const res = await csrfFetch(`${BASE_API_URL}/labelling/cases/${id}/feedback`, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
};
