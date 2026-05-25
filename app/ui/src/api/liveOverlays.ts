import axios from 'axios';
import { BASE_API_URL } from './client';

export type LiveRuntimeOverlaysPayload = {
  camera_id?: string;
  trigger_polygons: number[][][];
  detector_polygons: number[][][];
  source?: string;
  generated_at?: string;
};

export const fetchLiveRuntimeOverlays = async ({
  cameraId,
}: {
  cameraId: string;
}): Promise<LiveRuntimeOverlaysPayload> => {
  const response = await axios.get(`${BASE_API_URL}/live/overlays`, {
    params: { camera_id: cameraId },
  });
  return response.data as LiveRuntimeOverlaysPayload;
};
