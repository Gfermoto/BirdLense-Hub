import axios from 'axios';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { fetchWeather } from './weatherRegion';

afterEach(() => {
  vi.restoreAllMocks();
});

describe('weatherRegion API', () => {
  it('fetchWeather GET /weather', async () => {
    vi.spyOn(axios, 'get').mockResolvedValue({ data: { temp: 1 } });
    const d = await fetchWeather();
    expect(d).toEqual({ temp: 1 });
    expect(axios.get).toHaveBeenCalledWith(
      expect.stringMatching(/\/api\/ui\/weather$/),
    );
  });
});
