import axios from 'axios';
import type { BirdFood } from '../types';
import { BASE_API_URL } from './client';

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
}> => {
  const response = await axios.get(`${BASE_API_URL}/feed/info`);
  return response.data;
};

export const postScaleTare = async (): Promise<{
  success: boolean;
  message?: string;
}> => {
  try {
    const response = await axios.post(
      `${BASE_API_URL}/feed/scale-tare`,
      {},
      { withCredentials: true },
    );
    return { success: true, message: response.data?.message };
  } catch (e: unknown) {
    const err = e as { response?: { data?: { error?: string } } };
    return {
      success: false,
      message: err.response?.data?.error || 'Scale tare failed',
    };
  }
};

export const dispenseFeed = async (): Promise<{
  success: boolean;
  message?: string;
}> => {
  try {
    const response = await axios.post(
      `${BASE_API_URL}/feed/dispense`,
      {},
      {
        withCredentials: true,
      },
    );
    return { success: true, message: response.data?.message };
  } catch (e: unknown) {
    const err = e as { response?: { data?: { error?: string } } };
    return {
      success: false,
      message: err.response?.data?.error || 'Failed to dispense feed',
    };
  }
};
