import { BASE_API_URL, apiFetch } from './client';

export type LiveRuntimeOverlaysPayload = {
  camera_id?: string;
  trigger_polygons: number[][][];
  detector_polygons: number[][][];
  source?: string;
  generated_at?: string;
  opencv_last_decision_reason?: string | null;
};

export const fetchLiveRuntimeOverlays = async ({
  cameraId,
}: {
  cameraId: string;
}): Promise<LiveRuntimeOverlaysPayload> => {
  const q = new URLSearchParams({ camera_id: cameraId });
  return apiFetch(`${BASE_API_URL}/live/overlays?${q}`);
};
