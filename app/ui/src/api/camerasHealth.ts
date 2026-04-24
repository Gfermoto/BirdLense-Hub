import axios from 'axios';
import type { paths } from '../generated/openapi-types';
import { BASE_API_URL } from './client';

/** Ответ `GET /cameras`: в OpenAPI тело — произвольный JSON; фактически `{ cameras: [...] }`. */
export type CameraRow = {
  id: string;
  name: string;
  stream_url: string;
  stream_url_mjpeg?: string;
};

export const fetchCameras = async (): Promise<CameraRow[]> => {
  const response = await axios.get(`${BASE_API_URL}/cameras`);
  return response.data.cameras || [];
};

export type ComponentStatusPayload =
  paths['/status']['get']['responses']['200']['content']['application/json'];

export const fetchStatus = async (): Promise<ComponentStatusPayload> => {
  const response = await axios.get(`${BASE_API_URL}/status`);
  return response.data;
};

export type ReadinessPayload =
  | paths['/readiness']['get']['responses']['200']['content']['application/json']
  | paths['/readiness']['get']['responses']['503']['content']['application/json'];

export const fetchReadiness = async (): Promise<ReadinessPayload> => {
  const response = await axios.get(`${BASE_API_URL}/readiness`, {
    validateStatus: (status) => status === 200 || status === 503,
  });
  return response.data;
};
