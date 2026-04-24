import axios from 'axios';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { fetchCameras, fetchReadiness, fetchStatus } from './camerasHealth';

afterEach(() => {
  vi.restoreAllMocks();
});

describe('camerasHealth API', () => {
  it('fetchStatus calls GET /api/ui/status', async () => {
    vi.spyOn(axios, 'get').mockResolvedValue({
      data: {
        web: 'ok',
        processor: 'ok',
        video: 'ok',
        mqtt: 'ok',
        yolo: 'ok',
      },
    });
    await fetchStatus();
    expect(axios.get).toHaveBeenCalledWith(
      expect.stringMatching(/\/api\/ui\/status$/),
    );
  });

  it('fetchReadiness calls GET /api/ui/readiness with validateStatus', async () => {
    vi.spyOn(axios, 'get').mockResolvedValue({
      data: {
        status: 'ok',
        ready: true,
        checked_at: '2026-01-01T00:00:00Z',
        checks: {},
        components: {},
      },
    });
    await fetchReadiness();
    expect(axios.get).toHaveBeenCalledWith(
      expect.stringMatching(/\/api\/ui\/readiness$/),
      expect.objectContaining({
        validateStatus: expect.any(Function),
      }),
    );
  });

  it('fetchCameras returns cameras array from wrapper', async () => {
    vi.spyOn(axios, 'get').mockResolvedValue({
      data: {
        cameras: [
          {
            id: '1',
            name: 'Cam',
            stream_url: 'https://example/stream',
          },
        ],
      },
    });
    const rows = await fetchCameras();
    expect(rows).toHaveLength(1);
    expect(rows[0].name).toBe('Cam');
  });
});
