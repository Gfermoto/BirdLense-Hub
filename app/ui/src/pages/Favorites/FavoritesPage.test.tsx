import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { FavoritesPage } from './index';

const fetchFavoritesBySpecies = vi.hoisted(() => vi.fn());
const memoryRouterFuture = {
  v7_startTransition: true,
  v7_relativeSplatPath: true,
} as const;

vi.mock('../../api/favorites', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../api/favorites')>();
  return {
    ...actual,
    fetchFavoritesBySpecies,
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

vi.mock('../../api/speciesOverviewDetections', async (importOriginal) => {
  const actual =
    await importOriginal<
      typeof import('../../api/speciesOverviewDetections')
    >();
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

vi.mock('../../api/timeline', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../api/timeline')>();
  return {
    ...actual,
    fetchUnknownsForObserverDate: vi.fn().mockResolvedValue([]),
  };
});

function renderPage() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter
        future={memoryRouterFuture}
        initialEntries={['/favorites']}
      >
        <FavoritesPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('FavoritesPage', () => {
  beforeEach(() => {
    fetchFavoritesBySpecies.mockResolvedValue({
      total_videos: 2,
      total_species: 1,
      groups: [
        {
          species: {
            id: 10,
            name: 'Great Tit',
            image_url: 'data/images/great-tit.jpg',
            parent_id: null,
          },
          count: 2,
          latest_start_time: '2026-04-10T15:00:00+00:00',
          videos: [
            {
              id: 101,
              start_time: '2026-04-10T15:00:00+00:00',
              end_time: '2026-04-10T15:00:20+00:00',
              video_path: 'data/recordings/2026/04/10/150000/video.mp4',
              favorite: true,
              deleted: false,
              duration_seconds: 20,
              species: [
                {
                  id: 10,
                  name: 'Great Tit',
                  image_url: 'data/images/great-tit.jpg',
                  confidence: 0.91,
                  start_time: 0,
                  end_time: 4,
                  source: 'video',
                },
              ],
              scales: null,
            },
          ],
        },
      ],
      unclassified: { count: 0, videos: [] },
    });
  });

  it('renders favorite videos grouped by species', async () => {
    renderPage();

    expect(
      await screen.findByRole('heading', { name: /favorites/i }),
    ).toBeInTheDocument();
    expect(screen.getAllByText('Great Tit').length).toBeGreaterThan(0);
    expect(screen.getByText(/2 favorite recordings/i)).toBeInTheDocument();
    expect(screen.getByText(/1 species/i)).toBeInTheDocument();
  });
});
