import { Dayjs } from 'dayjs';
import {
  BirdFood,
  SpeciesVisit,
  Settings,
  SpeciesSummary,
  OverviewData,
  Species,
} from '../types';
import axios from 'axios';

// Relative path = same origin (works with any host/IP). При SSR/тестах — из env или дефолт.
export const BASE_URL =
  typeof window !== 'undefined'
    ? ''
    : (import.meta.env?.VITE_BASE_URL as string) || '';
export const BASE_API_URL = `${BASE_URL}/api/ui`;

/**
 * Resolve image URL for display.
 * - Absolute (http/https/data:) → as-is
 * - Relative path (data/images/...) → BASE_URL + path
 * Species: Wikipedia returns full URLs. Bird food: relative paths from seed.
 */
export const resolveImageUrl = (url: string | null | undefined): string | undefined => {
  if (!url) return undefined;
  if (url.startsWith('http://') || url.startsWith('https://') || url.startsWith('data:'))
    return url;
  const base = BASE_URL || '';
  return base ? `${base}/${url}` : `/${url}`;
};

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

/** Export timeline as CSV or JSON. Triggers download. */
export const exportTimeline = async (
  startTime: Dayjs,
  endTime: Dayjs,
  format: 'csv' | 'json',
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
  const ext = format === 'csv' ? 'csv' : 'json';
  const filename = `birdlense_timeline.${ext}`;
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  a.click();
  URL.revokeObjectURL(a.href);
};

export const fetchWeather = async () => {
  const response = await axios.get(`${BASE_API_URL}/weather`);
  return response.data;
};

export const fetchVideo = async (id: string) => {
  const response = await axios.get(`${BASE_API_URL}/videos/${id}`);
  return response.data;
};

export const fetchBirdFood = async (): Promise<BirdFood[]> => {
  const response = await axios.get(`${BASE_API_URL}/birdfood`);
  return response.data;
};

export const toggleBirdFood = async (id: number) => {
  const response = await axios.patch(`${BASE_API_URL}/birdfood/${id}/toggle`);
  return response.data;
};

export const addBirdFood = async (newFood: Partial<BirdFood>) => {
  const response = await axios.post(`${BASE_API_URL}/birdfood`, newFood);
  return response.data;
};

export const fetchCameras = async (): Promise<
  { id: string; name: string; stream_url: string }[]
> => {
  const response = await axios.get(`${BASE_API_URL}/cameras`);
  return response.data.cameras || [];
};

export const fetchStatus = async (): Promise<{
  web: string;
  processor: string;
  video: string;
  mqtt: string;
  esphome?: string;
  yolo: string;
  birdnet_url?: string | null;
}> => {
  const response = await axios.get(`${BASE_API_URL}/status`);
  return response.data;
};

export const dispenseFeed = async (): Promise<{ success: boolean; message?: string }> => {
  try {
    const response = await axios.post(`${BASE_API_URL}/feed/dispense`);
    return { success: true, message: response.data?.message };
  } catch (e: unknown) {
    const err = e as { response?: { data?: { error?: string } } };
    return {
      success: false,
      message: err.response?.data?.error || 'Failed to dispense feed',
    };
  }
};

export const fetchSettingsRequiresPassword = async (): Promise<boolean> => {
  const response = await axios.get(`${BASE_API_URL}/settings/requires-password`, {
    withCredentials: true,
  });
  return response.data?.requires === true;
};

export type CheckAccessResult =
  | { unlocked: true }
  | { unlocked: false; error?: 'network' };

export const checkSettingsAccess = async (): Promise<CheckAccessResult> => {
  try {
    const response = await axios.get(`${BASE_API_URL}/settings/check-access`, {
      withCredentials: true,
    });
    return response.data?.unlocked === true
      ? { unlocked: true }
      : { unlocked: false };
  } catch (e: unknown) {
    if (axios.isAxiosError(e) && e.response?.status === 403) {
      return { unlocked: false };
    }
    return { unlocked: false, error: 'network' };
  }
};

export type VerifyPasswordResult =
  | { ok: true }
  | { ok: false; error: 'wrong_password' | 'server_error' };

export const verifySettingsPassword = async (
  password: string,
): Promise<VerifyPasswordResult> => {
  try {
    const response = await axios.post(
      `${BASE_API_URL}/settings/verify-password`,
      { password },
      { withCredentials: true },
    );
    return response.data?.ok === true ? { ok: true } : { ok: false, error: 'wrong_password' };
  } catch (e: unknown) {
    return axios.isAxiosError(e) && e.response?.status === 401
      ? { ok: false, error: 'wrong_password' }
      : { ok: false, error: 'server_error' };
  }
};

export const fetchSettings = async () => {
  const response = await axios.get(`${BASE_API_URL}/settings`, {
    withCredentials: true,
  });
  return response.data;
};

export const updateSettings = async (settings: Settings) => {
  const response = await axios.patch(`${BASE_API_URL}/settings`, settings, {
    withCredentials: true,
  });
  return response.data;
};

export const restartProcessor = async (): Promise<{ success: boolean; message?: string }> => {
  try {
    const response = await axios.post(`${BASE_API_URL}/restart-processor`, {}, {
      withCredentials: true,
    });
    return { success: true, message: response.data?.message };
  } catch (e: unknown) {
    const err = e as { response?: { data?: { error?: string } } };
    return {
      success: false,
      message: err.response?.data?.error || 'Failed to restart',
    };
  }
};

export const fetchCoordinatesByZip = async (
  zip: string,
): Promise<{ lat: string; lon: string }> => {
  const response = await axios.get(
    'https://nominatim.openstreetmap.org/search',
    {
      params: {
        format: 'json',
        postalcode: zip,
        countrycodes: 'ru,us,de,gb',
      },
    },
  );
  const data = response.data;

  if (data && data.length > 0) {
    return {
      lat: data[0].lat,
      lon: data[0].lon,
    };
  } else {
    throw new Error('Invalid ZIP code or no data found.');
  }
};

export const fetchBirdDirectory = async (): Promise<Species[]> => {
  const response = await axios.get(`${BASE_API_URL}/species`);
  return response.data;
};

export const fetchOverviewData = async (
  date: string,
): Promise<OverviewData> => {
  const localStart = new Date(date + 'T00:00:00');
  const localEnd = new Date(date + 'T23:59:59.999');
  const response = await axios.get(`${BASE_API_URL}/overview`, {
    params: {
      start_time: Math.floor(localStart.getTime() / 1000),
      end_time: Math.floor(localEnd.getTime() / 1000),
    },
  });
  return response.data;
};

export const fetchSpeciesSummary = async (
  speciesId: number,
): Promise<SpeciesSummary> => {
  const response = await axios.get(
    `${BASE_API_URL}/species/${speciesId}/summary`,
  );
  return response.data;
};
