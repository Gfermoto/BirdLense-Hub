import axios from 'axios';
import { BASE_API_URL } from './client';

export const fetchCameras = async (): Promise<
  { id: string; name: string; stream_url: string; stream_url_mjpeg?: string }[]
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
  motion_source?: string;
  trigger_display?: string;
  active_triggers?: ('opencv' | 'frigate' | 'motion_sensor' | 'scales')[];
  birdnet_url?: string | null;
}> => {
  const response = await axios.get(`${BASE_API_URL}/status`);
  return response.data;
};

export type ReadinessPayload = {
  status: string;
  ready: boolean;
  checked_at: string;
  checks: {
    database: { status: string; error?: string };
    data_dir: {
      path: string;
      exists: boolean;
      is_dir: boolean;
      writable: boolean;
      status: string;
    };
    app_config_dir: {
      path: string;
      exists: boolean;
      is_dir: boolean;
      writable: boolean;
      status: string;
    };
  };
  components: {
    web: string;
    processor: string;
    video: string;
    mqtt: string;
    esphome?: string;
    yolo: string;
    motion_source?: string;
    trigger_display?: string;
    active_triggers?: ('opencv' | 'frigate' | 'motion_sensor' | 'scales')[];
    birdnet_url?: string | null;
  };
};

export const fetchReadiness = async (): Promise<ReadinessPayload> => {
  const response = await axios.get(`${BASE_API_URL}/readiness`, {
    validateStatus: (status) => status === 200 || status === 503,
  });
  return response.data;
};
