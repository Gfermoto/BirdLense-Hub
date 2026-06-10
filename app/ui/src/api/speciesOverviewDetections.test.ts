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

describe('speciesOverviewDetections API', () => {
  beforeEach(() => {
    apiFetchMock.mockReset();
  });

  it('fetchBirdDirectory builds species query with defaults', async () => {
    apiFetchMock.mockResolvedValue([]);
    const { fetchBirdDirectory } = await import('./speciesOverviewDetections');
    await fetchBirdDirectory();
    expect(apiFetchMock).toHaveBeenCalledWith(
      '/api/ui/species?exclude_suspects=1&scope=project',
    );
  });

  it('fetchBirdDirectory adds meta and catalog filters', async () => {
    apiFetchMock.mockResolvedValue({ items: [], meta: {} });
    const { fetchBirdDirectory } = await import('./speciesOverviewDetections');
    await fetchBirdDirectory({
      scope: 'all',
      meta: true,
      missing_audio: true,
      catalog_incomplete: true,
    });
    expect(apiFetchMock).toHaveBeenCalledWith(
      '/api/ui/species?exclude_suspects=1&scope=all&meta=1&missing_audio=1&catalog_incomplete=1',
    );
  });

  it('fetchObservedSpecies GETs /species/observed', async () => {
    apiFetchMock.mockResolvedValue([]);
    const { fetchObservedSpecies } = await import('./speciesOverviewDetections');
    await fetchObservedSpecies();
    expect(apiFetchMock).toHaveBeenCalledWith('/api/ui/species/observed');
  });

  it('fetchOverviewData passes date param', async () => {
    apiFetchMock.mockResolvedValue({});
    const { fetchOverviewData } = await import('./speciesOverviewDetections');
    await fetchOverviewData('2026-06-10');
    expect(apiFetchMock).toHaveBeenCalledWith('/api/ui/overview?date=2026-06-10');
  });

  it('refreshSpeciesMetadata POSTs empty body', async () => {
    apiFetchMock.mockResolvedValue({ ok: true });
    const { refreshSpeciesMetadata } = await import('./speciesOverviewDetections');
    await refreshSpeciesMetadata(42);
    expect(apiFetchMock).toHaveBeenCalledWith(
      '/api/ui/species/42/refresh-metadata',
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({}),
      },
    );
  });

  it('setSpeciesTuningTarget POSTs enabled flag', async () => {
    apiFetchMock.mockResolvedValue({ ok: true });
    const { setSpeciesTuningTarget } = await import('./speciesOverviewDetections');
    await setSpeciesTuningTarget(7, true);
    expect(apiFetchMock).toHaveBeenCalledWith(
      '/api/ui/species/7/tuning-target',
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enabled: true }),
      },
    );
  });

  it('updateDetectionSpecies PATCHes species and apply_scope', async () => {
    apiFetchMock.mockResolvedValue({ message: 'ok' });
    const { updateDetectionSpecies } = await import('./speciesOverviewDetections');
    await updateDetectionSpecies(10, 3, 'video', 'whole_visit');
    expect(apiFetchMock).toHaveBeenCalledWith('/api/ui/detections/10', {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        species_id: 3,
        source: 'video',
        apply_scope: 'whole_visit',
      }),
    });
  });

  it('fetchBirdProfiles builds optional query params', async () => {
    apiFetchMock.mockResolvedValue({ items: [] });
    const { fetchBirdProfiles } = await import('./speciesOverviewDetections');
    await fetchBirdProfiles({ query: 'robin', speciesId: 5, limit: 20 });
    expect(apiFetchMock).toHaveBeenCalledWith(
      '/api/ui/bird-profiles?query=robin&species_id=5&limit=20',
    );
  });

  it('deleteBirdProfile sends DELETE', async () => {
    apiFetchMock.mockResolvedValue({ id: 1 });
    const { deleteBirdProfile } = await import('./speciesOverviewDetections');
    await deleteBirdProfile(99);
    expect(apiFetchMock).toHaveBeenCalledWith('/api/ui/bird-profiles/99', {
      method: 'DELETE',
    });
  });

  it('confirmDetection POSTs source', async () => {
    apiFetchMock.mockResolvedValue({ message: 'ok', updated_count: 1 });
    const { confirmDetection } = await import('./speciesOverviewDetections');
    await confirmDetection(55, 'unknowns');
    expect(apiFetchMock).toHaveBeenCalledWith(
      '/api/ui/detections/55/confirm',
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ source: 'unknowns' }),
      },
    );
  });

  it('deleteDetection DELETEs with body', async () => {
    apiFetchMock.mockResolvedValue({ message: 'ok' });
    const { deleteDetection } = await import('./speciesOverviewDetections');
    await deleteDetection(12, { source: 'timeline', reason: 'test' });
    expect(apiFetchMock).toHaveBeenCalledWith('/api/ui/detections/12', {
      method: 'DELETE',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ source: 'timeline', reason: 'test' }),
    });
  });

  it('fetchRecentCorrections passes limit', async () => {
    apiFetchMock.mockResolvedValue([]);
    const { fetchRecentCorrections } = await import('./speciesOverviewDetections');
    await fetchRecentCorrections(25);
    expect(apiFetchMock).toHaveBeenCalledWith(
      '/api/ui/corrections/recent?limit=25',
    );
  });

  it('speciesDirectoryItems unwraps directory response', async () => {
    const { speciesDirectoryItems } = await import('./speciesOverviewDetections');
    expect(speciesDirectoryItems(undefined)).toEqual([]);
    expect(speciesDirectoryItems([{ id: 1 } as never])).toEqual([{ id: 1 }]);
    expect(
      speciesDirectoryItems({ items: [{ id: 2 } as never], meta: {} as never }),
    ).toEqual([{ id: 2 }]);
  });
});
