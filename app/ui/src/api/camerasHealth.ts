import type { paths } from '../generated/openapi-types';
import { BASE_API_URL, ApiHttpError, apiFetch, csrfFetch } from './client';

/** Ответ `GET /cameras`: в OpenAPI тело — произвольный JSON; фактически `{ cameras: [...] }`. */
export type CameraRow = {
  id: string;
  name: string;
  stream_url: string;
  /** Имя потока в Go2RTC (≠ id камеры, если так задано в настройках). */
  go2rtc_src?: string;
  camera_slot?: string;
  camera_profile?: string;
  stream_url_mjpeg?: string;
};

export const fetchCameras = async (): Promise<CameraRow[]> => {
  const data = await apiFetch<{ cameras?: CameraRow[] }>(
    `${BASE_API_URL}/cameras`,
  );
  return data.cameras || [];
};

export type ComponentStatusPayload =
  paths['/status']['get']['responses']['200']['content']['application/json'];

export const fetchStatus = async (): Promise<ComponentStatusPayload> =>
  apiFetch(`${BASE_API_URL}/status`);

export type ReadinessPayload =
  | paths['/readiness']['get']['responses']['200']['content']['application/json']
  | paths['/readiness']['get']['responses']['503']['content']['application/json'];

export const fetchReadiness = async (): Promise<ReadinessPayload> => {
  const res = await csrfFetch(`${BASE_API_URL}/readiness`, {
    credentials: 'include',
  });
  if (res.status === 200 || res.status === 503) {
    return (await res.json()) as ReadinessPayload;
  }
  const data: unknown = await res.json().catch(() => null);
  let message = res.statusText || `HTTP ${res.status}`;
  if (data && typeof data === 'object' && data !== null && 'error' in data) {
    const err = (data as { error?: unknown }).error;
    if (typeof err === 'string' && err.trim()) {
      message = err;
    }
  }
  throw new ApiHttpError(res.status, message, data);
};
