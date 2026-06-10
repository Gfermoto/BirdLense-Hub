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

describe('systemAuditMetrics API', () => {
  beforeEach(() => {
    apiFetchMock.mockReset();
  });

  it('fetchConfigAudit GETs config-audit', async () => {
    apiFetchMock.mockResolvedValue({ schema: 'config-audit' });
    const { fetchConfigAudit } = await import('./systemAuditMetrics');
    await fetchConfigAudit();
    expect(apiFetchMock).toHaveBeenCalledWith('/api/ui/system/config-audit');
  });

  it('applyTuningPreset POSTs preset_id', async () => {
    apiFetchMock.mockResolvedValue({ ok: true });
    const { applyTuningPreset } = await import('./systemAuditMetrics');
    await applyTuningPreset('balanced');
    expect(apiFetchMock).toHaveBeenCalledWith(
      '/api/ui/system/tuning-workbench/apply-preset',
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ preset_id: 'balanced' }),
      },
    );
  });

  it('fetchClassifierCalibrationReport sends pair_limit', async () => {
    apiFetchMock.mockResolvedValue({ available: true, corrections_analyzed: 0 });
    const { fetchClassifierCalibrationReport } = await import(
      './systemAuditMetrics'
    );
    await fetchClassifierCalibrationReport(25);
    expect(apiFetchMock).toHaveBeenCalledWith(
      '/api/ui/system/classifier-calibration-report?pair_limit=25',
    );
  });

  it('fetchSystemMetricsHistory sends hours and max_points', async () => {
    apiFetchMock.mockResolvedValue({ samples: [] });
    const { fetchSystemMetricsHistory } = await import('./systemAuditMetrics');
    await fetchSystemMetricsHistory(12, 100);
    expect(apiFetchMock).toHaveBeenCalledWith(
      '/api/ui/system/metrics/history?hours=12&max_points=100',
    );
  });

  it('trackSiteVisitor POSTs browser_id', async () => {
    apiFetchMock.mockResolvedValue(undefined);
    const { trackSiteVisitor } = await import('./systemAuditMetrics');
    await trackSiteVisitor('browser-abc');
    expect(apiFetchMock).toHaveBeenCalledWith('/api/ui/system/visitors/track', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ browser_id: 'browser-abc' }),
    });
  });

  it('fetchYoloDetectorHealth sends hours param', async () => {
    apiFetchMock.mockResolvedValue({ window_hours: 48 });
    const { fetchYoloDetectorHealth } = await import('./systemAuditMetrics');
    await fetchYoloDetectorHealth(48);
    expect(apiFetchMock).toHaveBeenCalledWith(
      '/api/ui/system/yolo-detector-health?hours=48',
    );
  });
});
