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

describe('domainHealth API', () => {
  beforeEach(() => {
    apiFetchMock.mockReset();
  });

  it('fetchDomainHealth GET /system/domain-health', async () => {
    apiFetchMock.mockResolvedValue({ strict_quality: { strict_quality_ready: true } });
    const { fetchDomainHealth } = await import('./domainHealth');
    await fetchDomainHealth();
    expect(apiFetchMock).toHaveBeenCalledWith('/api/ui/system/domain-health');
  });
});
