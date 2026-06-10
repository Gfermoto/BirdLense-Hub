import { beforeEach, describe, expect, it, vi } from 'vitest';

const apiFetchMock = vi.fn();
const csrfFetchMock = vi.fn();

vi.mock('./client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('./client')>();
  return {
    ...actual,
    apiFetch: (...args: unknown[]) => apiFetchMock(...args),
    csrfFetch: (...args: unknown[]) => csrfFetchMock(...args),
    BASE_API_URL: '/api/ui',
  };
});

describe('camerasHealth API', () => {
  beforeEach(() => {
    apiFetchMock.mockReset();
    csrfFetchMock.mockReset();
  });

  it('fetchStatus calls GET /api/ui/status', async () => {
    apiFetchMock.mockResolvedValue({
      web: 'ok',
      processor: 'ok',
      video: 'ok',
      mqtt: 'ok',
      yolo: 'ok',
    });
    const { fetchStatus } = await import('./camerasHealth');
    await fetchStatus();
    expect(apiFetchMock).toHaveBeenCalledWith('/api/ui/status');
  });

  it('fetchReadiness calls GET /api/ui/readiness via csrfFetch', async () => {
    csrfFetchMock.mockResolvedValue({
      status: 200,
      json: async () => ({
        status: 'ok',
        ready: true,
        checked_at: '2026-01-01T00:00:00Z',
        checks: {},
        components: {},
      }),
    });
    const { fetchReadiness } = await import('./camerasHealth');
    await fetchReadiness();
    expect(csrfFetchMock).toHaveBeenCalledWith(
      '/api/ui/readiness',
      expect.objectContaining({ credentials: 'include' }),
    );
  });

  it('fetchCameras returns cameras array from wrapper', async () => {
    apiFetchMock.mockResolvedValue({
      cameras: [
        {
          id: '1',
          name: 'Cam',
          stream_url: 'https://example/stream',
        },
      ],
    });
    const { fetchCameras } = await import('./camerasHealth');
    const rows = await fetchCameras();
    expect(rows).toHaveLength(1);
    expect(rows[0].name).toBe('Cam');
  });
});
