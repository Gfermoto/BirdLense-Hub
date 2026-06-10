import { beforeEach, describe, expect, it, vi } from 'vitest';

const apiFetchMock = vi.fn();
const resetCsrfTokenMock = vi.fn();

vi.mock('./client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('./client')>();
  return {
    ...actual,
    apiFetch: (...args: unknown[]) => apiFetchMock(...args),
    resetCsrfToken: () => resetCsrfTokenMock(),
    BASE_API_URL: '/api/ui',
    ApiHttpError: actual.ApiHttpError,
  };
});

describe('settingsSession apiFetch', () => {
  beforeEach(() => {
    apiFetchMock.mockReset();
    resetCsrfTokenMock.mockReset();
  });

  it('fetchSettingsRequiresPassword maps response', async () => {
    apiFetchMock.mockResolvedValue({
      requires: true,
      has_contributor_tier: false,
    });
    const { fetchSettingsRequiresPassword } = await import('./settingsSession');
    await expect(fetchSettingsRequiresPassword()).resolves.toEqual({
      requires: true,
      has_contributor_tier: false,
    });
    expect(apiFetchMock).toHaveBeenCalledWith(
      '/api/ui/settings/requires-password',
    );
  });

  it('checkSettingsAccess returns network on non-403 errors', async () => {
    const { ApiHttpError } = await import('./client');
    apiFetchMock.mockRejectedValue(new ApiHttpError(500, 'fail'));
    const { checkSettingsAccess } = await import('./settingsSession');
    await expect(checkSettingsAccess()).resolves.toEqual({
      unlocked: false,
      error: 'network',
    });
  });

  it('verifySettingsPassword retries after CSRF 403', async () => {
    const { ApiHttpError } = await import('./client');
    apiFetchMock
      .mockRejectedValueOnce(
        new ApiHttpError(403, 'CSRF token required', {
          error: 'CSRF token required',
        }),
      )
      .mockResolvedValueOnce({ ok: true, role: 'admin' });
    const { verifySettingsPassword } = await import('./settingsSession');
    await expect(verifySettingsPassword('secret')).resolves.toEqual({
      ok: true,
      role: 'admin',
    });
    expect(resetCsrfTokenMock).toHaveBeenCalledTimes(1);
    expect(apiFetchMock).toHaveBeenCalledTimes(2);
  });

  it('patchSettings PATCHes JSON', async () => {
    apiFetchMock.mockResolvedValue({ ok: true });
    const { patchSettings } = await import('./settingsSession');
    await patchSettings({ library: { foo: 1 } });
    expect(apiFetchMock).toHaveBeenCalledWith(
      '/api/ui/settings',
      expect.objectContaining({
        method: 'PATCH',
        body: JSON.stringify({ library: { foo: 1 } }),
      }),
    );
  });
});

describe('storageStats apiFetch', () => {
  beforeEach(() => {
    apiFetchMock.mockReset();
  });

  it('fetchStorageStats returns array from apiFetch', async () => {
    apiFetchMock.mockResolvedValue([
      { date: '2026-01-01', fileCount: 1, totalSize: 100 },
    ]);
    const { fetchStorageStats } = await import('./storageStats');
    await expect(fetchStorageStats()).resolves.toHaveLength(1);
  });

  it('fetchStorageStats returns [] when response is not array', async () => {
    apiFetchMock.mockResolvedValue(null);
    const { fetchStorageStats } = await import('./storageStats');
    await expect(fetchStorageStats()).resolves.toEqual([]);
  });
});

describe('retention apiFetch', () => {
  beforeEach(() => {
    apiFetchMock.mockReset();
  });

  it('fetchRetentionConfig GETs system retention', async () => {
    apiFetchMock.mockResolvedValue({ mode: 'days', days: 30 });
    const { fetchRetentionConfig } = await import('./retention');
    await expect(fetchRetentionConfig()).resolves.toEqual({
      mode: 'days',
      days: 30,
    });
    expect(apiFetchMock).toHaveBeenCalledWith('/api/ui/system/retention');
  });
});
