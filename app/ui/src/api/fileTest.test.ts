import { beforeEach, describe, expect, it, vi } from 'vitest';

const apiFetchMock = vi.fn();

vi.mock('./client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('./client')>();
  return {
    ...actual,
    apiFetch: (...args: unknown[]) => apiFetchMock(...args),
    BASE_API_URL: '/api/ui',
  };
});

describe('fileTest API', () => {
  beforeEach(() => {
    apiFetchMock.mockReset();
  });

  it('fetchFileTestFiles GET /system/file-test/files', async () => {
    apiFetchMock.mockResolvedValue({ file_dir: '/tmp', files: [] });
    const { fetchFileTestFiles } = await import('./fileTest');
    await fetchFileTestFiles();
    expect(apiFetchMock).toHaveBeenCalledWith('/api/ui/system/file-test/files');
  });

  it('fileTestRun POSTs JSON body', async () => {
    apiFetchMock.mockResolvedValue({ ok: true });
    const { fileTestRun } = await import('./fileTest');
    await fileTestRun({ armed: true, loop: false });
    expect(apiFetchMock).toHaveBeenCalledWith(
      '/api/ui/system/file-test/run',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ armed: true, loop: false }),
      }),
    );
  });

  it('fileTestDeleteFile DELETE with encoded name', async () => {
    apiFetchMock.mockResolvedValue(undefined);
    const { fileTestDeleteFile } = await import('./fileTest');
    await fileTestDeleteFile('clip with spaces.mp4');
    expect(apiFetchMock).toHaveBeenCalledWith(
      '/api/ui/system/file-test/files/clip%20with%20spaces.mp4',
      { method: 'DELETE' },
    );
  });

  it('fileTestUpload POSTs FormData', async () => {
    apiFetchMock.mockResolvedValue({ ok: true, name: 'x.mp4' });
    const { fileTestUpload } = await import('./fileTest');
    const file = new File(['x'], 'x.mp4', { type: 'video/mp4' });
    await fileTestUpload(file);
    const init = apiFetchMock.mock.calls[0][1] as RequestInit;
    expect(apiFetchMock.mock.calls[0][0]).toBe('/api/ui/system/file-test/upload');
    expect(init.method).toBe('POST');
    expect(init.body).toBeInstanceOf(FormData);
  });
});
