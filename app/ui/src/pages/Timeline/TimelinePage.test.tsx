import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { TimelinePage } from './index';

vi.mock('@mui/material/useMediaQuery', () => ({
  default: () => false,
}));

const exportTimelineForObserverDate = vi.hoisted(() =>
  vi.fn().mockResolvedValue(undefined),
);

vi.mock('../../api/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../api/api')>();
  return {
    ...actual,
    exportTimelineForObserverDate,
    fetchTimelineForObserverDate: vi.fn().mockResolvedValue([]),
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
    fetchUnknownsForObserverDate: vi.fn().mockResolvedValue([]),
    fetchNearestRecordingDay: vi.fn().mockResolvedValue({ found: false }),
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
      <MemoryRouter initialEntries={['/timeline?date=2026-04-15']}>
        <Routes>
          <Route path="/timeline" element={<TimelinePage />} />
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
  });
});
