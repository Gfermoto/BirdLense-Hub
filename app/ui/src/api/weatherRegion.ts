/** Weather, sun times, eBird region comparison (#343). */
import axios from 'axios';
import { formatLocalTime } from '../util';
import { BASE_API_URL } from './client';

export const fetchWeather = async () => {
  const response = await axios.get(`${BASE_API_URL}/weather`);
  return response.data;
};

/** Sunrise, sunset, dawn, dusk for date at configured location. date: YYYY-MM-DD. Returns ISO strings (UTC). */
export const fetchSunTimes = async (
  date: string,
): Promise<{
  dawn?: string;
  sunrise?: string;
  noon?: string;
  sunset?: string;
  dusk?: string;
} | null> => {
  try {
    const res = await axios.get(`${BASE_API_URL}/sun-times`, {
      params: { date },
    });
    const d = res.data;
    if (!d || typeof d !== 'object' || !('sunrise' in d)) return null;
    return d;
  } catch {
    return null;
  }
};

/** Format ISO UTC string to local HH:MM */
export const formatSunTimeLocal = (iso: string): string => {
  try {
    return formatLocalTime(iso);
  } catch {
    return '--:--';
  }
};

/** Region comparison with eBird. Returns null if API key not configured or error. */
export const fetchRegionComparison = async (): Promise<{
  regionCode: string;
  userCount: number;
  regionTopCount: number;
  matchCount: number;
  matchedSpecies: string[];
  regionTop: string[];
} | null> => {
  try {
    const res = await axios.get(`${BASE_API_URL}/region-comparison`);
    const d = res.data;
    if (!d || typeof d !== 'object' || !('regionCode' in d)) return null;
    return d;
  } catch {
    return null;
  }
};
