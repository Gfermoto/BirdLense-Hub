import { beforeEach, describe, expect, it, vi } from 'vitest';

const apiFetchMock = vi.fn();
const apiBlobMock = vi.fn();
const triggerBlobDownloadMock = vi.fn();

vi.mock('./client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('./client')>();
  return {
    ...actual,
    apiFetch: (...args: unknown[]) => apiFetchMock(...args),
    apiBlob: (...args: unknown[]) => apiBlobMock(...args),
    triggerBlobDownload: (...args: unknown[]) => triggerBlobDownloadMock(...args),
    BASE_API_URL: '/api/ui',
    ApiHttpError: actual.ApiHttpError,
  };
});

describe('settingsYamlDb api', () => {
  beforeEach(() => {
    apiFetchMock.mockReset();
    apiBlobMock.mockReset();
    triggerBlobDownloadMock.mockReset();
  });

  it('downloadSettingsYamlSafe downloads via apiBlob', async () => {
    apiBlobMock.mockResolvedValue({
      blob: new Blob(['yaml']),
      filename: 'user_config_safe.yaml',
    });
    const { downloadSettingsYamlSafe } = await import('./settingsYamlDb');
    await downloadSettingsYamlSafe();
    expect(apiBlobMock).toHaveBeenCalledWith(
      '/api/ui/settings/yaml-export?mode=safe',
    );
    expect(triggerBlobDownloadMock).toHaveBeenCalledWith(
      expect.any(Blob),
      'user_config_safe.yaml',
    );
  });

  it('purgeStorageRecordings POSTs JSON via apiFetch', async () => {
    apiFetchMock.mockResolvedValue({
      message: 'ok',
      deletedCount: 2,
      deletedSize: 1024,
    });
    const { purgeStorageRecordings } = await import('./settingsYamlDb');
    const body = { date: '2026-01-01' };
    await purgeStorageRecordings(body);
    expect(apiFetchMock).toHaveBeenCalledWith(
      '/api/ui/storage/purge',
      expect.objectContaining({
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      }),
    );
  });

  it('importSettingsYaml returns ok:false on ApiHttpError', async () => {
    const { ApiHttpError } = await import('./client');
    apiFetchMock.mockRejectedValue(new ApiHttpError(400, 'bad yaml'));
    const { importSettingsYaml } = await import('./settingsYamlDb');
    const file = new File(['x'], 'user_config.yaml', { type: 'text/yaml' });
    await expect(importSettingsYaml(file)).resolves.toEqual({
      ok: false,
      message: 'bad yaml',
    });
  });

  it('restoreDbBackup POSTs FormData via apiFetch', async () => {
    apiFetchMock.mockResolvedValue({ message: 'restored' });
    const { restoreDbBackup } = await import('./settingsYamlDb');
    const file = new File(['db'], 'backup.db', { type: 'application/octet-stream' });
    await restoreDbBackup(file);
    expect(apiFetchMock).toHaveBeenCalledWith(
      '/api/ui/system/db/restore',
      expect.objectContaining({ method: 'POST' }),
    );
    const init = apiFetchMock.mock.calls[0][1] as RequestInit;
    expect(init.body).toBeInstanceOf(FormData);
  });
});
