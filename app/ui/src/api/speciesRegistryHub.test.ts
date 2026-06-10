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

describe('speciesRegistryHub API', () => {
  beforeEach(() => {
    apiFetchMock.mockReset();
  });

  it('fetchSpeciesDataQuality sends query params', async () => {
    apiFetchMock.mockResolvedValue({ species_total: 1 });
    const { fetchSpeciesDataQuality } = await import('./speciesRegistryHub');
    await fetchSpeciesDataQuality();
    expect(apiFetchMock).toHaveBeenCalledWith(
      '/api/ui/system/species-registry/data-quality?suspect_limit=500&duplicate_limit=100',
    );
  });

  it('fetchClassifierDatasetAlignment sends alignment limits', async () => {
    apiFetchMock.mockResolvedValue({ classifier_class_count: 0 });
    const { fetchClassifierDatasetAlignment } = await import(
      './speciesRegistryHub'
    );
    await fetchClassifierDatasetAlignment();
    expect(apiFetchMock).toHaveBeenCalledWith(
      '/api/ui/system/species-registry/classifier-dataset-alignment?classifier_limit=400&catalog_limit=300&dataset_limit=150',
    );
  });

  it('startCatalogRepair POSTs limit body', async () => {
    apiFetchMock.mockResolvedValue({ message: 'ok', status: { status: 'idle' } });
    const { startCatalogRepair } = await import('./speciesRegistryHub');
    await startCatalogRepair(120);
    expect(apiFetchMock).toHaveBeenCalledWith(
      '/api/ui/system/species-registry/repair-cards/start',
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ limit: 120 }),
      },
    );
  });

  it('seedSpeciesRegistry POSTs to seed endpoint', async () => {
    apiFetchMock.mockResolvedValue({ ok: true });
    const { seedSpeciesRegistry } = await import('./speciesRegistryHub');
    await seedSpeciesRegistry();
    expect(apiFetchMock).toHaveBeenCalledWith(
      '/api/ui/system/species-registry/seed',
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({}),
      },
    );
  });

  it('fetchRecognitionImprovementSummary GETs summary', async () => {
    apiFetchMock.mockResolvedValue({ active_mode: 'disabled' });
    const { fetchRecognitionImprovementSummary } = await import(
      './speciesRegistryHub'
    );
    await fetchRecognitionImprovementSummary();
    expect(apiFetchMock).toHaveBeenCalledWith(
      '/api/ui/system/recognition-improvement',
    );
  });
});
