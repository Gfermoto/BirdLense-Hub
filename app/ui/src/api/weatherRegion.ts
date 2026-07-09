/** Weather, sun times, eBird region comparison (#343). */
import { formatLocalTime } from '../util';
import { BASE_API_URL, ApiHttpError, apiFetch } from './client';

export const fetchWeather = async () => apiFetch(`${BASE_API_URL}/weather`);

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
    const d = await apiFetch<Record<string, unknown>>(
      `${BASE_API_URL}/sun-times?${new URLSearchParams({ date })}`,
    );
    if (!d || typeof d !== 'object' || !('sunrise' in d)) return null;
    return d as {
      dawn?: string;
      sunrise?: string;
      noon?: string;
      sunset?: string;
      dusk?: string;
    };
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
    const d = await apiFetch<Record<string, unknown>>(
      `${BASE_API_URL}/region-comparison`,
    );
    if (!d || typeof d !== 'object' || !('regionCode' in d)) return null;
    return d as {
      regionCode: string;
      userCount: number;
      regionTopCount: number;
      matchCount: number;
      matchedSpecies: string[];
      regionTop: string[];
    };
  } catch (e: unknown) {
    if (e instanceof ApiHttpError) {
      return null;
    }
    return null;
  }
};
