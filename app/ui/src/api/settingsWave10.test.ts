import { beforeEach, describe, expect, it, vi } from 'vitest';

const apiFetchMock = vi.fn();

vi.mock('./client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('./client')>();
  return {
    ...actual,
    apiFetch: (...args: unknown[]) => apiFetchMock(...args),
    BASE_API_URL: '/api/ui',
    ApiHttpError: actual.ApiHttpError,
  };
});

describe('domainHealth apiFetch', () => {
  beforeEach(() => {
    apiFetchMock.mockReset();
  });

  it('fetchDomainHealth calls GET /api/ui/system/domain-health', async () => {
    apiFetchMock.mockResolvedValue({ strict_quality: { strict_quality_ready: true } });
    const { fetchDomainHealth } = await import('./domainHealth');
    await fetchDomainHealth();
    expect(apiFetchMock).toHaveBeenCalledWith('/api/ui/system/domain-health');
  });
});

describe('liveOverlays apiFetch', () => {
  beforeEach(() => {
    apiFetchMock.mockReset();
  });

  it('fetchLiveRuntimeOverlays passes camera_id query', async () => {
    apiFetchMock.mockResolvedValue({
      trigger_polygons: [],
      detector_polygons: [],
    });
    const { fetchLiveRuntimeOverlays } = await import('./liveOverlays');
    await fetchLiveRuntimeOverlays({ cameraId: 'BirdBox' });
    expect(apiFetchMock).toHaveBeenCalledWith(
      '/api/ui/live/overlays?camera_id=BirdBox',
    );
  });
});

describe('migrationCalendar apiFetch', () => {
  beforeEach(() => {
    apiFetchMock.mockReset();
  });

  it('fetchMigrationCalendar builds query from params', async () => {
    apiFetchMock.mockResolvedValue({ species: [], month_labels: [] });
    const { fetchMigrationCalendar } = await import('./migrationCalendar');
    await fetchMigrationCalendar({ start_year: 2024, catalog: 'observed' });
    expect(apiFetchMock).toHaveBeenCalledWith(
      '/api/ui/migration-calendar?start_year=2024&catalog=observed',
    );
  });
});

describe('expertReid apiFetch', () => {
  beforeEach(() => {
    apiFetchMock.mockReset();
  });

  it('fetchExpertQueue defaults sync=1', async () => {
    apiFetchMock.mockResolvedValue({ enabled: true, items: [], count: 0 });
    const { fetchExpertQueue } = await import('./expertReid');
    await fetchExpertQueue();
    expect(apiFetchMock).toHaveBeenCalledWith('/api/ui/expert/queue?sync=1');
  });

  it('resolveExpertTask POSTs JSON body', async () => {
    apiFetchMock.mockResolvedValue({ ok: true });
    const { resolveExpertTask } = await import('./expertReid');
    await resolveExpertTask({ task_id: 1, action: 'dismiss' });
    expect(apiFetchMock).toHaveBeenCalledWith(
      '/api/ui/expert/resolve',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ task_id: 1, action: 'dismiss' }),
      }),
    );
  });
});

describe('notificationsProcessor apiFetch', () => {
  beforeEach(() => {
    apiFetchMock.mockReset();
  });

  it('restartProcessor returns success payload', async () => {
    apiFetchMock.mockResolvedValue({ message: 'restarted' });
    const { restartProcessor } = await import('./notificationsProcessor');
    await expect(restartProcessor()).resolves.toEqual({
      success: true,
      message: 'restarted',
    });
  });

  it('sendTestNotification maps ApiHttpError to failure', async () => {
    const { ApiHttpError } = await import('./client');
    apiFetchMock.mockRejectedValue(
      new ApiHttpError(500, 'fail', { error: 'notify down' }),
    );
    const { sendTestNotification } = await import('./notificationsProcessor');
    await expect(sendTestNotification()).resolves.toEqual({
      success: false,
      message: 'notify down',
    });
  });
});
