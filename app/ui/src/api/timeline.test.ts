import axios from 'axios';
import dayjs from 'dayjs';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { fetchTimeline } from './timeline';

afterEach(() => {
  vi.restoreAllMocks();
});

describe('timeline API', () => {
  it('fetchTimeline passes unix range to GET /timeline', async () => {
    vi.spyOn(axios, 'get').mockResolvedValue({ data: [] });
    const start = dayjs.unix(1_700_000_000);
    const end = dayjs.unix(1_700_008_640);
    await fetchTimeline(start, end);
    expect(axios.get).toHaveBeenCalledWith(
      expect.stringMatching(/\/api\/ui\/timeline$/),
      {
        params: {
          start_time: 1_700_000_000,
          end_time: 1_700_008_640,
        },
      },
    );
  });
});
