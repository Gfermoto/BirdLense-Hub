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

describe('migrationCalendar API', () => {
  beforeEach(() => {
    apiFetchMock.mockReset();
  });

  it('fetchMigrationCalendar GET without params', async () => {
    apiFetchMock.mockResolvedValue({ species: [], month_labels: [] });
    const { fetchMigrationCalendar } = await import('./migrationCalendar');
    await fetchMigrationCalendar();
    expect(apiFetchMock).toHaveBeenCalledWith('/api/ui/migration-calendar');
  });

  it('fetchMigrationCalendar GET with catalog param', async () => {
    apiFetchMock.mockResolvedValue({ species: [], month_labels: [] });
    const { fetchMigrationCalendar } = await import('./migrationCalendar');
    await fetchMigrationCalendar({ catalog: 'observed', start_year: 2024 });
    expect(apiFetchMock).toHaveBeenCalledWith(
      expect.stringMatching(/^\/api\/ui\/migration-calendar\?(?:start_year=2024&catalog=observed|catalog=observed&start_year=2024)$/),
    );
  });
});
