import axios from 'axios';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { fetchVideoNeighbors } from './video';

afterEach(() => {
  vi.restoreAllMocks();
});

describe('video API', () => {
  it('fetchVideoNeighbors sends local day_scope and cross_day', async () => {
    vi.spyOn(Date.prototype, 'getTimezoneOffset').mockReturnValue(-180);
    vi.spyOn(axios, 'get').mockResolvedValue({
      data: {
        day_scope: 'local',
        day_label: 'x',
        timezone_offset_minutes: -180,
        cross_day: true,
        previous_id: null,
        next_id: null,
        index: 0,
        total: 1,
      },
    });
    await fetchVideoNeighbors('42');
    expect(axios.get).toHaveBeenCalledWith(
      expect.stringMatching(/\/videos\/42\/neighbors$/),
      {
        params: {
          day_scope: 'local',
          tz_offset_minutes: -180,
          cross_day: 1,
        },
      },
    );
  });
});
