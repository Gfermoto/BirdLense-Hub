/** HTTP client defaults and base URLs for UI → Hub API (#343). */
import axios from 'axios';

// Relative path = same origin (works with any host/IP). При SSR/тестах — из env или дефолт.
export const BASE_URL =
  typeof window !== 'undefined'
    ? ''
    : (import.meta.env?.VITE_BASE_URL as string) || '';
export const BASE_API_URL = `${BASE_URL}/api/ui`;

axios.defaults.timeout = 30000;

/** Длинный timeout для POST перегенерации треков/спектрограмм и опроса job status. */
export const JOB_STATUS_POLL_TIMEOUT_MS = 120_000;
