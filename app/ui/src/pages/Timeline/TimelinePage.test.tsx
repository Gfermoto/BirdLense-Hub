import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { TimelinePage } from './index';

/** Align with App.tsx BrowserRouter future flags (silences v7 upgrade warnings). */
const memoryRouterFuture = {
  v7_startTransition: true,
  v7_relativeSplatPath: true,
} as const;

vi.mock('@mui/material/useMediaQuery', () => ({
  default: () => false,
}));

const exportTimelineForObserverDate = vi.hoisted(() =>
  vi.fn().mockResolvedValue(undefined),
);

vi.mock('../../api/timeline', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../api/timeline')>();
  return {
    ...actual,
    exportTimelineForObserverDate,
    fetchTimelineForObserverDate: vi.fn().mockResolvedValue([]),
    fetchUnknownsForObserverDate: vi.fn().mockResolvedValue([]),
  };
});

vi.mock('../../api/video', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../api/video')>();
  return {
    ...actual,
    fetchNearestRecordingDay: vi.fn().mockResolvedValue({ found: false }),
  };
});

vi.mock('../../api/speciesOverviewDetections', async (importOriginal) => {
  const actual =
    await importOriginal<typeof import('../../api/speciesOverviewDetections')>();
  return {
    ...actual,
    fetchOverviewData: vi.fn().mockResolvedValue({
      topSpecies: [],
      stats: {
        uniqueSpecies: 0,
        totalDetections: 0,
        lastHourDetections: 0,
        videoDuration: 0,
        audioDuration: 0,
        busiestHour: 0,
        avgVisitDuration: 0,
      },
      hourlyTemperature: Array(24).fill(null),
      observer_timezone: 'UTC',
    }),
  };
});

vi.mock('../../contexts/ProtectedAreaContext', () => ({
  useProtectedArea: () => ({
    canEdit: true,
    role: 'admin',
    requiresPassword: false,
    isLoading: false,
  }),
}));

function renderPage() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter
        future={memoryRouterFuture}
        initialEntries={['/timeline?date=2026-04-15']}
      >
        <Routes>
          <Route path="/timeline" element={<TimelinePage />} />
          <Route path="/favorites" element={<div>favorites-page</div>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('TimelinePage', () => {
  beforeEach(() => {
    exportTimelineForObserverDate.mockClear();
    exportTimelineForObserverDate.mockResolvedValue(undefined);
  });

  it('shows a snackbar when timeline export fails', async () => {
    const errSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
    try {
      exportTimelineForObserverDate.mockRejectedValueOnce(
        new Error('Export blocked'),
      );
      const user = userEvent.setup();
      renderPage();

      const exportTrigger = await screen.findByTestId(
        'timeline-export-menu-trigger',
      );
      expect(exportTrigger).toBeEnabled();

      await user.click(exportTrigger);
      await user.click(screen.getByRole('menuitem', { name: /export csv/i }));

      await waitFor(() => {
        expect(screen.getByTestId('timeline-export-error')).toHaveTextContent(
          'Export blocked',
        );
      });
    } finally {
      errSpy.mockRestore();
    }
  }, 10000);

  it('opens the favorites catalog from the existing favorites chip', async () => {
    const user = userEvent.setup();
    renderPage();

    await user.click(await screen.findByRole('button', { name: /favorites/i }));

    expect(await screen.findByText('favorites-page')).toBeInTheDocument();
  });
});
