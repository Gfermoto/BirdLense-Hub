import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const apiFetchMock = vi.fn();

vi.mock('./client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('./client')>();
  return {
    ...actual,
    apiFetch: (...args: unknown[]) => apiFetchMock(...args),
    BASE_API_URL: '/api/ui',
  };
});

describe('video API', () => {
  beforeEach(() => {
    apiFetchMock.mockReset();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('fetchVideoNeighbors sends local day_scope and cross_day', async () => {
    vi.spyOn(Date.prototype, 'getTimezoneOffset').mockReturnValue(-180);
    apiFetchMock.mockResolvedValue({
      day_scope: 'local',
      day_label: 'x',
      timezone_offset_minutes: -180,
      cross_day: true,
      previous_id: null,
      next_id: null,
      index: 0,
      total: 1,
    });
    const { fetchVideoNeighbors } = await import('./video');
    await fetchVideoNeighbors('42');
    expect(apiFetchMock).toHaveBeenCalledWith(
      '/api/ui/videos/42/neighbors?day_scope=local&tz_offset_minutes=-180&cross_day=1',
    );
  });
});
