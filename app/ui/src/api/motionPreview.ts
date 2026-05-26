export type MotionPreviewMode = 'detection_mog2' | 'trigger_mog2' | 'static';

export type MotionPreviewWarning = {
  level: string;
  code: string;
  message: string;
};

export type MotionPreviewResponse = {
  mode: string;
  image_jpeg_base64?: string;
  mask_jpeg_base64?: string;
  foreground_pixel_fraction?: number;
  warnings?: MotionPreviewWarning[];
  error?: string;
};

export async function fetchMotionPreview(params: {
  mode: MotionPreviewMode;
  cameraId?: string;
  overrides?: Record<string, unknown>;
}): Promise<MotionPreviewResponse> {
  const qs = new URLSearchParams();
  qs.set('mode', params.mode);
  if (params.cameraId) {
    qs.set('camera_id', params.cameraId);
  }
  if (params.overrides && Object.keys(params.overrides).length > 0) {
    qs.set('overrides', JSON.stringify(params.overrides));
  }
  const res = await fetch(`/api/debug/motion-preview?${qs.toString()}`, {
    credentials: 'include',
  });
  const body = (await res.json()) as MotionPreviewResponse;
  if (!res.ok) {
    throw new Error(body.error || `motion_preview_${res.status}`);
  }
  return body;
}
