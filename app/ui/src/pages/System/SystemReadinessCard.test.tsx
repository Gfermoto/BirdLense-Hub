import { render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { SystemReadinessCard } from './SystemReadinessCard';

const fetchReadiness = vi.hoisted(() =>
  vi.fn().mockResolvedValue({
    status: 'degraded',
    ready: false,
    quality_ready: false,
    checked_at: '2026-06-10T12:00:00Z',
    checks: {
      database: { status: 'ok' },
      data_dir: { status: 'ok' },
      app_config_dir: { status: 'ok' },
      pipeline_funnel: {
        status: 'degraded',
        top_root_causes: ['decision_fusion_drop_tracks_gt_0_persisted_0'],
        alerts: ['fusion_drop rate 90.0% > 35.0%'],
      },
      yolo_detector: { status: 'ok', source: 'heartbeat' },
    },
    components: { web: 'ok', processor: 'ok', video: 'ok', mqtt: 'ok', yolo: 'ok' },
    pipeline_funnel: {
      schema: 'persist_funnel_summary@v1',
      window_hours: 24,
      sessions_total: 10,
      healthy_persist_rate: 0.1,
      fusion_drop_rate: 0.9,
      status: 'degraded',
      top_root_causes: ['decision_fusion_drop_tracks_gt_0_persisted_0'],
      alerts: ['fusion_drop rate 90.0% > 35.0%'],
      by_camera: {
        cam1: { decision_fusion_drop_tracks_gt_0_persisted_0: 3 },
      },
    },
    security_gates: { runtime: 'development', items: [] },
  }),
);

vi.mock('../../api/camerasHealth', async (importOriginal) => {
  const actual =
    await importOriginal<typeof import('../../api/camerasHealth')>();
  return {
    ...actual,
    fetchReadiness,
  };
});

function renderCard() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <SystemReadinessCard />
    </QueryClientProvider>,
  );
}

describe('SystemReadinessCard', () => {
  beforeEach(() => {
    fetchReadiness.mockClear();
  });

  it('renders persist funnel metrics and failure mode hints', async () => {
    renderCard();
    await waitFor(() => {
      expect(screen.getByText(/Persist funnel/i)).toBeInTheDocument();
    });
    expect(
      screen.getAllByText(/Fusion drop — tracks present/i).length,
    ).toBeGreaterThan(0);
    expect(screen.getByText(/cam1:/i)).toBeInTheDocument();
    expect(screen.getByText(/fusion_drop rate/i)).toBeInTheDocument();
    expect(screen.getByText(/Sessions: 10/i)).toBeInTheDocument();
  });
});
