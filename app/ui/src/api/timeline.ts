/** Timeline + unknowns list API (#343). */
import type { Dayjs } from 'dayjs';
import axios from 'axios';
import type { SpeciesVisit } from '../types';
import type { TimeOfDay } from '../utils/timeUtils';
import { BASE_API_URL } from './client';

export const fetchTimeline = async (
  startTime: Dayjs,
  endTime: Dayjs,
): Promise<SpeciesVisit[]> => {
  const response = await axios.get(`${BASE_API_URL}/timeline`, {
    params: {
      start_time: startTime.unix(),
      end_time: endTime.unix(),
    },
  });
  return response.data;
};

export const fetchTimelineForObserverDate = async (
  date: string,
  options?: {
    timeOfDay?: TimeOfDay;
    hour?: number | null;
    favoritesOnly?: boolean;
  },
): Promise<SpeciesVisit[]> => {
  const response = await axios.get(`${BASE_API_URL}/timeline`, {
    params: {
      date,
      ...(options?.hour != null
        ? { hour: options.hour }
        : { time_of_day: options?.timeOfDay ?? 'all' }),
      ...(options?.favoritesOnly ? { favorite_only: 1 } : {}),
    },
  });
  return response.data;
};

/** Export timeline as CSV, JSON, or eBird format. Triggers download. */
export const exportTimeline = async (
  startTime: Dayjs,
  endTime: Dayjs,
  format: 'csv' | 'json' | 'ebird',
): Promise<void> => {
  const params = new URLSearchParams({
    start_time: String(startTime.unix()),
    end_time: String(endTime.unix()),
    format,
  });
  const url = `${BASE_API_URL}/timeline/export?${params}`;
  const res = await fetch(url);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: res.statusText }));
    throw new Error(err.error || res.statusText);
  }
  const blob = await res.blob();
  const ext = format === 'ebird' ? 'csv' : format === 'csv' ? 'csv' : 'json';
  const filename =
    format === 'ebird' ? 'birdlense_ebird.csv' : `birdlense_timeline.${ext}`;
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  a.click();
  URL.revokeObjectURL(a.href);
};

export const exportTimelineForObserverDate = async (
  date: string,
  format: 'csv' | 'json' | 'ebird',
  options?: {
    timeOfDay?: TimeOfDay;
    hour?: number | null;
    favoritesOnly?: boolean;
  },
): Promise<void> => {
  const params = new URLSearchParams({
    date,
    format,
    ...(options?.hour != null
      ? { hour: String(options.hour) }
      : { time_of_day: options?.timeOfDay ?? 'all' }),
    ...(options?.favoritesOnly ? { favorite_only: '1' } : {}),
  });
  const url = `${BASE_API_URL}/timeline/export?${params}`;
  const res = await fetch(url);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: res.statusText }));
    throw new Error(err.error || res.statusText);
  }
  const blob = await res.blob();
  const ext = format === 'ebird' ? 'csv' : format === 'csv' ? 'csv' : 'json';
  const filename =
    format === 'ebird' ? 'birdlense_ebird.csv' : `birdlense_timeline.${ext}`;
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  a.click();
  URL.revokeObjectURL(a.href);
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
  review_state?: 'pending' | 'reviewed' | 'not_applicable';
  review_reason?: 'low_confidence' | 'generic_bird' | string;
  review_source?: string;
}

export const fetchUnknowns = async (
  startTime: Dayjs,
  endTime: Dayjs,
  limit = 100,
): Promise<UnknownDetection[]> => {
  const response = await axios.get(`${BASE_API_URL}/unknowns`, {
    params: {
      start_time: startTime.unix(),
      end_time: endTime.unix(),
      limit,
    },
  });
  return response.data;
};

export const fetchUnknownsForObserverDate = async (
  date: string,
  options?: { timeOfDay?: TimeOfDay; hour?: number | null; limit?: number },
): Promise<UnknownDetection[]> => {
  const response = await axios.get(`${BASE_API_URL}/unknowns`, {
    params: {
      date,
      limit: options?.limit ?? 100,
      ...(options?.hour != null
        ? { hour: options.hour }
        : { time_of_day: options?.timeOfDay ?? 'all' }),
    },
  });
  return response.data;
};
