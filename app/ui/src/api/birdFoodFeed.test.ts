import axios from 'axios';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { fetchBirdFood, fetchFeedInfo } from './birdFoodFeed';

afterEach(() => {
  vi.restoreAllMocks();
});

describe('birdFoodFeed API', () => {
  it('fetchBirdFood calls GET /api/ui/birdfood', async () => {
    vi.spyOn(axios, 'get').mockResolvedValue({ data: [] });
    await fetchBirdFood();
    expect(axios.get).toHaveBeenCalledWith(
      expect.stringMatching(/\/api\/ui\/birdfood$/),
    );
  });

  it('fetchFeedInfo calls GET /api/ui/feed/info', async () => {
    vi.spyOn(axios, 'get').mockResolvedValue({
      data: { last_dispense_at: null, donate_url: null },
    });
    await fetchFeedInfo();
    expect(axios.get).toHaveBeenCalledWith(
      expect.stringMatching(/\/api\/ui\/feed\/info$/),
    );
  });
});
