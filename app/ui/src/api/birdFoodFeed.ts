import type { BirdFood } from '../types';
import { BASE_API_URL, ApiHttpError, apiFetch } from './client';

export const fetchBirdFood = async (): Promise<BirdFood[]> =>
  apiFetch(`${BASE_API_URL}/birdfood`);

export const toggleBirdFood = async (id: number) =>
  apiFetch(`${BASE_API_URL}/birdfood/${id}/toggle`, { method: 'PATCH' });

export const addBirdFood = async (newFood: Partial<BirdFood>) =>
  apiFetch(`${BASE_API_URL}/birdfood`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(newFood),
  });

export const fetchFeedInfo = async (): Promise<{
  last_dispense_at: string | null;
  donate_url: string | null;
  feed_source?: string;
  scales_enabled?: boolean;
  scales_source?: 'mqtt' | 'esphome' | 'homeassistant' | null;
  scale_tare_available?: boolean;
  scale?: {
    weight?: number;
    unit?: string;
    updated_at?: string;
    source?: string;
    bird_present?: boolean;
  } | null;
}> => apiFetch(`${BASE_API_URL}/feed/info`);

function feedActionErrorMessage(
  e: unknown,
  fallback: string,
): string {
  if (e instanceof ApiHttpError) {
    const err = (e.data as { error?: string } | null)?.error;
    if (typeof err === 'string' && err.trim()) {
      return err;
    }
    if (e.message.trim()) {
      return e.message;
    }
  }
  return fallback;
}

export const postScaleTare = async (): Promise<{
  success: boolean;
  message?: string;
}> => {
  try {
    const data = await apiFetch<{ message?: string }>(
      `${BASE_API_URL}/feed/scale-tare`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({}),
      },
    );
    return { success: true, message: data?.message };
  } catch (e: unknown) {
    return {
      success: false,
      message: feedActionErrorMessage(e, 'Scale tare failed'),
    };
  }
};

export const dispenseFeed = async (): Promise<{
  success: boolean;
  message?: string;
}> => {
  try {
    const data = await apiFetch<{ message?: string }>(
      `${BASE_API_URL}/feed/dispense`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({}),
      },
    );
    return { success: true, message: data?.message };
  } catch (e: unknown) {
    return {
      success: false,
      message: feedActionErrorMessage(e, 'Failed to dispense feed'),
    };
  }
};
