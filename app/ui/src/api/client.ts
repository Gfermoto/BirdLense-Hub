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

export class ApiHttpError extends Error {
  readonly status: number;
  readonly data: unknown;

  constructor(status: number, message: string, data: unknown = null) {
    super(message);
    this.name = 'ApiHttpError';
    this.status = status;
    this.data = data;
  }
}

async function readApiErrorBody(res: Response): Promise<{ message: string; data: unknown }> {
  const data: unknown = await res.json().catch(() => null);
  if (data && typeof data === 'object' && data !== null && 'error' in data) {
    const msg = (data as { error?: unknown }).error;
    if (typeof msg === 'string' && msg.trim()) {
      return { message: msg, data };
    }
  }
  return { message: res.statusText || `HTTP ${res.status}`, data };
}

/** JSON API via csrfFetch; throws ApiHttpError on non-2xx. */
export async function apiFetch<T>(url: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (!headers.has('Accept')) {
    headers.set('Accept', 'application/json');
  }
  const res = await csrfFetch(url, {
    ...init,
    credentials: init.credentials ?? 'include',
    headers,
  });
  if (!res.ok) {
    const { message, data } = await readApiErrorBody(res);
    throw new ApiHttpError(res.status, message, data);
  }
  if (res.status === 204) {
    return undefined as T;
  }
  return (await res.json()) as T;
}

export type ApiBlobResult = {
  blob: Blob;
  filename?: string;
  contentDisposition: string | null;
};

/** Binary GET/POST via csrfFetch; throws ApiHttpError on non-2xx. */
export async function apiBlob(url: string, init: RequestInit = {}): Promise<ApiBlobResult> {
  const res = await csrfFetch(url, {
    ...init,
    credentials: init.credentials ?? 'include',
  });
  if (!res.ok) {
    const { message, data } = await readApiErrorBody(res);
    throw new ApiHttpError(res.status, message, data);
  }
  const blob = await res.blob();
  const contentDisposition = res.headers.get('Content-Disposition');
  const match = contentDisposition?.match(/filename="?([^";\n]+)"?/);
  return { blob, filename: match?.[1], contentDisposition };
}

export function triggerBlobDownload(blob: Blob, filename: string): void {
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  a.click();
  URL.revokeObjectURL(a.href);
}

