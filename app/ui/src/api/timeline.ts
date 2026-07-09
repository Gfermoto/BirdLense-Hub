/** Timeline + unknowns list API (#343). */
import type { Dayjs } from 'dayjs';
import type { SpeciesVisit } from '../types';
import type { TimeOfDay } from '../utils/timeUtils';
import {
  BASE_API_URL,
  apiBlob,
  apiFetch,
  triggerBlobDownload,
} from './client';

const timelineExportFallbackName = (format: 'csv' | 'json' | 'ebird'): string =>
  format === 'ebird' ? 'birdlense_ebird.csv' : `birdlense_timeline.${format === 'csv' ? 'csv' : 'json'}`;

export const fetchTimeline = async (
  startTime: Dayjs,
  endTime: Dayjs,
): Promise<SpeciesVisit[]> => {
  const q = new URLSearchParams({
    start_time: String(startTime.unix()),
    end_time: String(endTime.unix()),
  });
  return apiFetch<SpeciesVisit[]>(`${BASE_API_URL}/timeline?${q}`);
};

export const fetchTimelineForObserverDate = async (
  date: string,
  options?: {
    timeOfDay?: TimeOfDay;
    hour?: number | null;
    favoritesOnly?: boolean;
    triggerSource?:
      | 'all'
      | 'opencv'
      | 'frigate'
      | 'motion_sensor'
      | 'scales';
  },
): Promise<SpeciesVisit[]> => {
  const q = new URLSearchParams({ date });
  if (options?.hour != null) {
    q.set('hour', String(options.hour));
  } else {
    q.set('time_of_day', options?.timeOfDay ?? 'all');
  }
  if (options?.favoritesOnly) {
    q.set('favorite_only', '1');
  }
  if (options?.triggerSource && options.triggerSource !== 'all') {
    q.set('trigger_source', options.triggerSource);
  }
  return apiFetch<SpeciesVisit[]>(`${BASE_API_URL}/timeline?${q}`);
};

/** Export timeline as CSV, JSON, or eBird format. Triggers download. */
export const exportTimeline = async (
  startTime: Dayjs,
  endTime: Dayjs,
  format: 'csv' | 'json' | 'ebird',
): Promise<void> => {
  const q = new URLSearchParams({
    start_time: String(startTime.unix()),
    end_time: String(endTime.unix()),
    format,
  });
  const { blob, filename } = await apiBlob(`${BASE_API_URL}/timeline/export?${q}`);
  triggerBlobDownload(blob, filename || timelineExportFallbackName(format));
};

export const exportTimelineForObserverDate = async (
  date: string,
  format: 'csv' | 'json' | 'ebird',
  options?: {
    timeOfDay?: TimeOfDay;
    hour?: number | null;
    favoritesOnly?: boolean;
    triggerSource?:
      | 'all'
      | 'opencv'
      | 'frigate'
      | 'motion_sensor'
      | 'scales';
  },
): Promise<void> => {
  const q = new URLSearchParams({ date, format });
  if (options?.hour != null) {
    q.set('hour', String(options.hour));
  } else {
    q.set('time_of_day', options?.timeOfDay ?? 'all');
  }
  if (options?.favoritesOnly) {
    q.set('favorite_only', '1');
  }
  if (options?.triggerSource && options.triggerSource !== 'all') {
    q.set('trigger_source', options.triggerSource);
  }
  const { blob, filename } = await apiBlob(`${BASE_API_URL}/timeline/export?${q}`);
  triggerBlobDownload(blob, filename || timelineExportFallbackName(format));
};

export interface UnknownDetection {
  id: number;
  video_id: number;
  species_id: number;
  species_name: string;
  confidence: number;
  start_time: string;
  end_time: string;
  source: string;
  detection_provider?: string;
  image_url?: string;
  review_state?: 'pending' | 'reviewed' | 'not_applicable' | 'semantic_review_required';
  review_reason?: 'low_confidence' | 'generic_bird' | 'classifier_uncertainty' | 'semantic_review_required' | string;
  review_source?: string;
  classifier_entropy?: number | null;
  classifier_top1_top2_margin?: number | null;
  classifier_needs_review?: boolean;
}

export const fetchUnknowns = async (
  startTime: Dayjs,
  endTime: Dayjs,
  limit = 100,
): Promise<UnknownDetection[]> => {
  const q = new URLSearchParams({
    start_time: String(startTime.unix()),
    end_time: String(endTime.unix()),
    limit: String(limit),
  });
  return apiFetch<UnknownDetection[]>(`${BASE_API_URL}/unknowns?${q}`);
};

export const fetchUnknownsForObserverDate = async (
  date: string,
  options?: {
    timeOfDay?: TimeOfDay;
    hour?: number | null;
    limit?: number;
    queue?: 'expert' | 'default';
    reviewReason?: string;
  },
): Promise<UnknownDetection[]> => {
  const q = new URLSearchParams({
    date,
    limit: String(options?.limit ?? 100),
  });
  if (options?.queue && options.queue !== 'default') {
    q.set('queue', options.queue);
  }
  if (options?.reviewReason) {
    q.set('review_reason', options.reviewReason);
  }
  if (options?.hour != null) {
    q.set('hour', String(options.hour));
  } else {
    q.set('time_of_day', options?.timeOfDay ?? 'all');
  }
  return apiFetch<UnknownDetection[]>(`${BASE_API_URL}/unknowns?${q}`);
};
