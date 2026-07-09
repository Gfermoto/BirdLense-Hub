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

describe('expertReid API', () => {
  beforeEach(() => {
    apiFetchMock.mockReset();
  });

  it('fetchReidGalleryStatus GET /reid/gallery/status', async () => {
    apiFetchMock.mockResolvedValue({ reid_gallery_enabled: true });
    const { fetchReidGalleryStatus } = await import('./expertReid');
    await fetchReidGalleryStatus();
    expect(apiFetchMock).toHaveBeenCalledWith('/api/ui/reid/gallery/status');
  });

  it('fetchExpertQueue defaults sync=1', async () => {
    apiFetchMock.mockResolvedValue({ enabled: true, items: [], count: 0 });
    const { fetchExpertQueue } = await import('./expertReid');
    await fetchExpertQueue();
    expect(apiFetchMock).toHaveBeenCalledWith('/api/ui/expert/queue?sync=1');
  });

  it('fetchExpertQueue sync=0 when sync false', async () => {
    apiFetchMock.mockResolvedValue({ enabled: true, items: [], count: 0 });
    const { fetchExpertQueue } = await import('./expertReid');
    await fetchExpertQueue({ sync: false, status: 'pending' });
    expect(apiFetchMock).toHaveBeenCalledWith(
      '/api/ui/expert/queue?sync=0&status=pending',
    );
  });

  it('resolveExpertTask POST /expert/resolve', async () => {
    apiFetchMock.mockResolvedValue({ ok: true });
    const { resolveExpertTask } = await import('./expertReid');
    await resolveExpertTask({ task_id: 1, action: 'dismiss' });
    expect(apiFetchMock).toHaveBeenCalledWith('/api/ui/expert/resolve', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ task_id: 1, action: 'dismiss' }),
    });
  });
});
