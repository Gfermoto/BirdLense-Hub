import { describe, expect, it } from 'vitest';
import { BASE_API_URL, BASE_URL, JOB_STATUS_POLL_TIMEOUT_MS } from './client';

describe('api client', () => {
  it('exposes JOB_STATUS_POLL_TIMEOUT_MS as a positive number', () => {
    expect(JOB_STATUS_POLL_TIMEOUT_MS).toBeGreaterThan(0);
  });

  it('BASE_API_URL is BASE_URL + /api/ui', () => {
    expect(BASE_API_URL).toBe(`${BASE_URL}/api/ui`);
  });
});
