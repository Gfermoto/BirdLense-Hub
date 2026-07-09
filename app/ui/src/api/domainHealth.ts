import { BASE_API_URL, apiFetch } from './client';

/** Ответ `GET /system/domain-health` (см. `system_domain_health_service.build_domain_health_payload`). */
export type DomainStrictQuality = {
  duplicate_video_groups_ok: boolean;
  duplicate_detection_groups_ok: boolean;
  duplicate_clip_candidates_ok: boolean;
  visit_species_mismatches_ok: boolean;
  video_detections_with_frames_ratio_ok: boolean;
  video_detections_primary_yolo_ratio_ok: boolean;
  strict_quality_ready: boolean;
};

export type DomainHealthPayload = {
  domain_contract_version?: string;
  snapshot_degraded?: boolean;
  snapshot_error_class?: string;
  thresholds?: {
    clip_duplicate_gap_seconds?: number;
    visit_large_gap_seconds?: number;
    visit_timeout_seconds?: number;
    min_seconds_between_recordings?: number;
  };
  metrics?: Record<string, number | null | undefined>;
  strict_quality?: DomainStrictQuality;
};

export const fetchDomainHealth = async (): Promise<DomainHealthPayload> =>
  apiFetch(`${BASE_API_URL}/system/domain-health`);
