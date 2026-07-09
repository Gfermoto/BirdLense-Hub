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
  };
});

describe('dataset api', () => {
  beforeEach(() => {
    apiFetchMock.mockReset();
    apiBlobMock.mockReset();
    triggerBlobDownloadMock.mockReset();
  });

  it('cleanDataset POSTs via apiFetch', async () => {
    apiFetchMock.mockResolvedValue({
      deleted_fullframe: 0,
      deleted_orphaned: 0,
      errors: [],
      dry_run: true,
    });
    const { cleanDataset } = await import('./dataset');
    await cleanDataset({ dry_run: true });
    expect(apiFetchMock).toHaveBeenCalledWith(
      '/api/ui/dataset/clean',
      expect.objectContaining({ method: 'POST' }),
    );
  });

  it('exportDataset downloads blob from apiBlob', async () => {
    apiBlobMock.mockResolvedValue({
      blob: new Blob(['x']),
      filename: 'birdlense_dataset.zip',
    });
    const { exportDataset } = await import('./dataset');
    await exportDataset();
    expect(apiBlobMock).toHaveBeenCalledWith('/api/ui/dataset/export');
    expect(triggerBlobDownloadMock).toHaveBeenCalledWith(
      expect.any(Blob),
      'birdlense_dataset.zip',
    );
  });
});
