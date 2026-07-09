import { render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { SystemReadinessCard } from './SystemReadinessCard';

const memoryRouterFuture = {
  v7_startTransition: true,
  v7_relativeSplatPath: true,
} as const;

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

const fetchSystemMetricsLive = vi.hoisted(() =>
  vi.fn().mockResolvedValue({
    cpu: { percent: 12 },
    memory: { total: 16, used: 8, percent: 50 },
    disk: { total: 100, used: 84, percent: 84 },
    encoding: 'cpu',
    gpu_percent: null,
  }),
);

const fetchRetentionConfig = vi.hoisted(() =>
  vi.fn().mockResolvedValue({
    mode: 'cascade',
    max_gb: 120,
    orphan_recording_files: {
      orphan_session_count: 3,
      orphan_bytes: 512 * 1024 * 1024,
    },
  }),
);

const fetchStorageStats = vi.hoisted(() =>
  vi.fn().mockResolvedValue([
    { date: '2026-06-09', fileCount: 10, totalSize: 40 * 1024 ** 3 },
    { date: '2026-06-10', fileCount: 5, totalSize: 20 * 1024 ** 3 },
  ]),
);

vi.mock('../../api/camerasHealth', async (importOriginal) => {
  const actual =
    await importOriginal<typeof import('../../api/camerasHealth')>();
  return {
    ...actual,
    fetchReadiness,
  };
});

vi.mock('../../api/systemAuditMetrics', async (importOriginal) => {
  const actual =
    await importOriginal<typeof import('../../api/systemAuditMetrics')>();
  return {
    ...actual,
    fetchSystemMetricsLive,
  };
});

vi.mock('../../api/retention', () => ({
  fetchRetentionConfig,
}));

vi.mock('../../api/storageStats', () => ({
  fetchStorageStats,
  sumStorageStats: (days: Array<{ totalSize: number; fileCount: number }>) =>
    days.reduce(
      (acc, row) => ({
        totalBytes: acc.totalBytes + row.totalSize,
        totalFiles: acc.totalFiles + row.fileCount,
      }),
      { totalBytes: 0, totalFiles: 0 },
    ),
}));

function renderCard() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter future={memoryRouterFuture}>
        <SystemReadinessCard />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('SystemReadinessCard', () => {
  beforeEach(() => {
    fetchReadiness.mockClear();
    fetchSystemMetricsLive.mockClear();
    fetchRetentionConfig.mockClear();
    fetchStorageStats.mockClear();
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

  it('renders operator disk, quota, and orphan snapshot', async () => {
    renderCard();
    await waitFor(() => {
      expect(screen.getByText(/Operator snapshot/i)).toBeInTheDocument();
    });
    expect(screen.getByText(/84\.0 \/ 100\.0 GB \(84%\)/i)).toBeInTheDocument();
    expect(screen.getByText(/Cap 120\.0 GB/i)).toBeInTheDocument();
    expect(screen.getByText(/3 sessions/i)).toBeInTheDocument();
    expect(screen.getByText(/15 files/i)).toBeInTheDocument();
    expect(
      screen.getByRole('link', { name: /Library → storage/i }),
    ).toHaveAttribute('href', '/library');
  });
});
