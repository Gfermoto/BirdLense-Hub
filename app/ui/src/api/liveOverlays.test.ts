import { beforeEach, describe, expect, it, vi } from 'vitest';

const apiFetchMock = vi.fn();

vi.mock('./client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('./client')>();
  return {
    ...actual,
    apiFetch: (...args: unknown[]) => apiFetchMock(...args),
    BASE_API_URL: '/api/ui',
  };
});

describe('liveOverlays API', () => {
  beforeEach(() => {
    apiFetchMock.mockReset();
  });

  it('fetchLiveRuntimeOverlays GET with camera_id', async () => {
    apiFetchMock.mockResolvedValue({ trigger_polygons: [], detector_polygons: [] });
    const { fetchLiveRuntimeOverlays } = await import('./liveOverlays');
    await fetchLiveRuntimeOverlays({ cameraId: 'BirdBox' });
    expect(apiFetchMock).toHaveBeenCalledWith(
      '/api/ui/live/overlays?camera_id=BirdBox',
    );
  });
});
