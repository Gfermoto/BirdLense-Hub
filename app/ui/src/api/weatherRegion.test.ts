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

describe('weatherRegion API', () => {
  beforeEach(() => {
    apiFetchMock.mockReset();
  });

  it('fetchWeather GET /weather', async () => {
    apiFetchMock.mockResolvedValue({ temp: 1 });
    const { fetchWeather } = await import('./weatherRegion');
    const d = await fetchWeather();
    expect(d).toEqual({ temp: 1 });
    expect(apiFetchMock).toHaveBeenCalledWith('/api/ui/weather');
  });
});
