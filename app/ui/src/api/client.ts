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

const CSRF_HEADER_NAME = 'X-Birdlense-CSRF-Token';
const mutatingMethods = new Set(['post', 'put', 'patch', 'delete']);
let csrfToken: string | null = null;
let csrfTokenPromise: Promise<string> | null = null;

export function resetCsrfToken() {
  csrfToken = null;
  csrfTokenPromise = null;
}

export async function getCsrfToken(): Promise<string> {
  if (csrfToken) return csrfToken;
  if (!csrfTokenPromise) {
    csrfTokenPromise = fetch(`${BASE_API_URL}/csrf-token`, {
      credentials: 'include',
      headers: { Accept: 'application/json' },
    })
      .then(async (res) => {
        if (!res.ok)
          throw new Error(`CSRF token request failed: ${res.status}`);
        const data = (await res.json()) as { csrf_token?: unknown };
        if (typeof data.csrf_token !== 'string' || !data.csrf_token) {
          throw new Error('CSRF token response is invalid');
        }
        csrfToken = data.csrf_token;
        return data.csrf_token;
      })
      .finally(() => {
        csrfTokenPromise = null;
      });
  }
  return csrfTokenPromise;
}

export async function csrfFetch(
  input: RequestInfo | URL,
  init: RequestInit = {},
) {
  const method = (init.method || 'GET').toString().toLowerCase();
  if (!mutatingMethods.has(method)) {
    return fetch(input, init);
  }
  const token = await getCsrfToken();
  const headers = new Headers(init.headers || {});
  headers.set(CSRF_HEADER_NAME, token);
  return fetch(input, {
    ...init,
    headers,
    credentials: init.credentials ?? 'include',
  });
}

axios.interceptors.request.use(async (config) => {
  const method = (config.method || 'get').toLowerCase();
  if (!mutatingMethods.has(method)) {
    return config;
  }
  const token = await getCsrfToken();
  config.headers.set(CSRF_HEADER_NAME, token);
  config.withCredentials = true;
  return config;
});
