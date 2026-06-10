import axios from 'axios';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

type AxiosInterceptorConfig = {
  method?: string;
  headers: InstanceType<typeof axios.AxiosHeaders>;
  withCredentials?: boolean;
};

async function loadHandlers() {
  await import('./client');
  return (
    axios.interceptors.request as unknown as {
      handlers: Array<{
        fulfilled?: (
          config: AxiosInterceptorConfig,
        ) => Promise<AxiosInterceptorConfig>;
      }>;
    }
  ).handlers;
}

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

  it('resetCsrfToken clears cache so the next getCsrfToken refetches', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ csrf_token: 'csrf-token-reset' }),
    });
    vi.stubGlobal('fetch', fetchMock);

    const { getCsrfToken, resetCsrfToken } = await import('./client');
    await getCsrfToken();
    resetCsrfToken();
    await getCsrfToken();

    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it('rejects when CSRF token HTTP response is not ok', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 503,
        json: async () => ({}),
      }),
    );
    const { getCsrfToken } = await import('./client');

    await expect(getCsrfToken()).rejects.toThrow(
      'CSRF token request failed: 503',
    );
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

    const handlers = await loadHandlers();
    const interceptor = handlers[handlers.length - 1];
    const config = await interceptor?.fulfilled?.({
      method: 'post',
      headers: new axios.AxiosHeaders(),
    });

    expect(config?.withCredentials).toBe(true);
    expect(config?.headers.get('X-Birdlense-CSRF-Token')).toBe('csrf-token-3');
  });

  it('axios interceptor leaves GET requests unchanged', async () => {
    vi.stubGlobal('fetch', vi.fn());
    await import('./client');

    const handlers = await loadHandlers();
    const interceptor = handlers[handlers.length - 1];
    const headers = new axios.AxiosHeaders();
    const config = await interceptor?.fulfilled?.({
      method: 'get',
      headers,
    });

    expect(config?.headers).toBe(headers);
    expect(config?.withCredentials).toBeUndefined();
    expect(vi.mocked(globalThis.fetch)).not.toHaveBeenCalled();
  });


  it('apiFetch returns parsed JSON on success', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ items: [], count: 0 }),
    });
    vi.stubGlobal('fetch', fetchMock);

    const { apiFetch } = await import('./client');
    await expect(apiFetch('/api/ui/labelling/cases')).resolves.toEqual({
      items: [],
      count: 0,
    });
    expect(fetchMock).toHaveBeenCalledWith('/api/ui/labelling/cases', {
      credentials: 'include',
      headers: expect.any(Headers),
    });
  });

  it('apiFetch throws ApiHttpError with backend message', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ csrf_token: 'csrf-token-post' }),
      })
      .mockResolvedValueOnce({
        ok: false,
        status: 403,
        statusText: 'Forbidden',
        json: async () => ({ error: 'denied' }),
      });
    vi.stubGlobal('fetch', fetchMock);

    const { apiFetch, ApiHttpError } = await import('./client');
    await expect(apiFetch('/api/ui/dataset/clean', { method: 'POST' })).rejects.toMatchObject({
      name: 'ApiHttpError',
      status: 403,
      message: 'denied',
    });
    expect(ApiHttpError).toBeDefined();
  });

  it('apiBlob returns blob and parsed filename', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      blob: async () => new Blob(['zip']),
      headers: {
        get: (name: string) =>
          name === 'Content-Disposition' ? 'attachment; filename="data.zip"' : null,
      },
    });
    vi.stubGlobal('fetch', fetchMock);

    const { apiBlob } = await import('./client');
    await expect(apiBlob('/api/ui/dataset/export')).resolves.toMatchObject({
      filename: 'data.zip',
    });
  });
});
