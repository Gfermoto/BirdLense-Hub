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

describe('labelling api', () => {
  beforeEach(() => {
    apiFetchMock.mockReset();
  });

  it('fetchLabellingCases builds query and uses apiFetch GET', async () => {
    apiFetchMock.mockResolvedValue({ items: [], count: 0 });
    const { fetchLabellingCases } = await import('./labelling');
    await fetchLabellingCases('pending', 50, true);
    expect(apiFetchMock).toHaveBeenCalledWith(
      '/api/ui/labelling/cases?status=pending&limit=50&with_media_only=1',
    );
  });

  it('mineLabellingCases POSTs JSON via apiFetch', async () => {
    apiFetchMock.mockResolvedValue({ ok: true, created: 1, skipped: 0 });
    const { mineLabellingCases } = await import('./labelling');
    await mineLabellingCases({ lookback_hours: 24 });
    expect(apiFetchMock).toHaveBeenCalledWith(
      '/api/ui/labelling/cases/mine',
      expect.objectContaining({
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      }),
    );
  });
});
