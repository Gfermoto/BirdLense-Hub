import dayjs from 'dayjs';
import { afterEach, describe, expect, it, vi } from 'vitest';

const apiFetchMock = vi.fn();

vi.mock('./client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('./client')>();
  return {
    ...actual,
    apiFetch: (...args: unknown[]) => apiFetchMock(...args),
  };
});

import { fetchTimeline, fetchUnknownsForObserverDate } from './timeline';

afterEach(() => {
  apiFetchMock.mockReset();
  vi.restoreAllMocks();
});

describe('timeline API', () => {
  it('fetchTimeline passes unix range to apiFetch GET /timeline', async () => {
    apiFetchMock.mockResolvedValue([]);
    const start = dayjs.unix(1_700_000_000);
    const end = dayjs.unix(1_700_008_640);
    await fetchTimeline(start, end);
    expect(apiFetchMock).toHaveBeenCalledWith(
      '/api/ui/timeline?start_time=1700000000&end_time=1700008640',
    );
  });

  it('fetchUnknownsForObserverDate builds query for observer date', async () => {
    apiFetchMock.mockResolvedValue([]);
    await fetchUnknownsForObserverDate('2026-06-10', {
      hour: 14,
      queue: 'expert',
      reviewReason: 'low_confidence',
      limit: 50,
    });
    expect(apiFetchMock).toHaveBeenCalledWith(
      '/api/ui/unknowns?date=2026-06-10&limit=50&queue=expert&review_reason=low_confidence&hour=14',
    );
  });
});
