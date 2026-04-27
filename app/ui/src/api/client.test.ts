import axios from 'axios';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

describe('api client', () => {
  beforeEach(() => {
    vi.resetModules();
    vi.restoreAllMocks();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('exposes JOB_STATUS_POLL_TIMEOUT_MS as a positive number', async () => {
    const { JOB_STATUS_POLL_TIMEOUT_MS } = await import('./client');
    expect(JOB_STATUS_POLL_TIMEOUT_MS).toBeGreaterThan(0);
  });

  it('BASE_API_URL is BASE_URL + /api/ui', async () => {
    const { BASE_API_URL, BASE_URL } = await import('./client');
    expect(BASE_API_URL).toBe(`${BASE_URL}/api/ui`);
  });

  it('fetches and caches CSRF token', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ csrf_token: 'csrf-token-1' }),
    });
    vi.stubGlobal('fetch', fetchMock);

    const { getCsrfToken } = await import('./client');

    await expect(getCsrfToken()).resolves.toBe('csrf-token-1');
    await expect(getCsrfToken()).resolves.toBe('csrf-token-1');
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock).toHaveBeenCalledWith('/api/ui/csrf-token', {
      credentials: 'include',
      headers: { Accept: 'application/json' },
    });
  });

  it('rejects invalid CSRF token responses', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ csrf_token: '' }),
      }),
    );
    const { getCsrfToken } = await import('./client');

    await expect(getCsrfToken()).rejects.toThrow(
      'CSRF token response is invalid',
    );
  });

  it('adds CSRF header and credentials to mutating fetch requests', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ csrf_token: 'csrf-token-2' }),
      })
      .mockResolvedValueOnce({ ok: true });
    vi.stubGlobal('fetch', fetchMock);

    const { csrfFetch } = await import('./client');
    await csrfFetch('/api/ui/settings', {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: '{}',
    });

    const [, mutationInit] = fetchMock.mock.calls[1];
    expect(mutationInit.credentials).toBe('include');
    expect(mutationInit.headers.get('X-Birdlense-CSRF-Token')).toBe(
      'csrf-token-2',
    );
    expect(mutationInit.headers.get('Content-Type')).toBe('application/json');
  });

  it('does not add CSRF token to read-only fetch requests', async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true });
    vi.stubGlobal('fetch', fetchMock);

    const { csrfFetch } = await import('./client');
    await csrfFetch('/api/ui/species');

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock).toHaveBeenCalledWith('/api/ui/species', {});
  });

  it('adds CSRF header to mutating axios requests', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ csrf_token: 'csrf-token-3' }),
      }),
    );
    await import('./client');

    const handlers = (
      axios.interceptors.request as unknown as {
        handlers: Array<{
          fulfilled?: (config: {
            method: string;
            headers: InstanceType<typeof axios.AxiosHeaders>;
            withCredentials?: boolean;
          }) => Promise<{
            headers: InstanceType<typeof axios.AxiosHeaders>;
            withCredentials?: boolean;
          }>;
        }>;
      }
    ).handlers;
    const interceptor = handlers[handlers.length - 1];
    const config = await interceptor?.fulfilled?.({
      method: 'post',
      headers: new axios.AxiosHeaders(),
    });

    expect(config?.withCredentials).toBe(true);
    expect(config?.headers.get('X-Birdlense-CSRF-Token')).toBe('csrf-token-3');
  });
});
