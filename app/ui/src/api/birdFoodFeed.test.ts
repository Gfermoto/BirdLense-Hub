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

describe('birdFoodFeed API', () => {
  beforeEach(() => {
    apiFetchMock.mockReset();
  });

  it('fetchBirdFood calls GET /api/ui/birdfood', async () => {
    apiFetchMock.mockResolvedValue([]);
    const { fetchBirdFood } = await import('./birdFoodFeed');
    await fetchBirdFood();
    expect(apiFetchMock).toHaveBeenCalledWith('/api/ui/birdfood');
  });

  it('fetchFeedInfo calls GET /api/ui/feed/info', async () => {
    apiFetchMock.mockResolvedValue({
      last_dispense_at: null,
      donate_url: null,
    });
    const { fetchFeedInfo } = await import('./birdFoodFeed');
    await fetchFeedInfo();
    expect(apiFetchMock).toHaveBeenCalledWith('/api/ui/feed/info');
  });
});
