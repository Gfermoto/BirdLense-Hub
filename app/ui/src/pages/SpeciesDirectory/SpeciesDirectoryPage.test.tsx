import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { describe, expect, it, vi } from 'vitest';
import { SpeciesDirectoryPage } from './index';

const memoryRouterFuture = {
  v7_startTransition: true,
  v7_relativeSplatPath: true,
} as const;

const fetchBirdDirectory = vi.hoisted(() =>
  vi.fn().mockResolvedValue([
    {
      id: 1,
      name: 'Great Tit',
      parent_id: null,
      created_at: '2026-01-01T00:00:00Z',
      image_url: null,
      description: 'Garden bird',
      active: true,
      count: 12,
    },
    {
      id: 2,
      name: 'House Sparrow',
      parent_id: null,
      created_at: '2026-01-01T00:00:00Z',
      image_url: null,
      description: 'Common visitor',
      active: true,
      count: 4,
    },
  ]),
);

vi.mock('../../api/speciesOverviewDetections', async (importOriginal) => {
  const actual =
    await importOriginal<
      typeof import('../../api/speciesOverviewDetections')
    >();
  return {
    ...actual,
    fetchBirdDirectory,
  };
});

function renderPage() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter future={memoryRouterFuture}>
        <SpeciesDirectoryPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('SpeciesDirectoryPage', () => {
  it('shows species list and filters by search', async () => {
    const user = userEvent.setup();
    renderPage();

    expect(await screen.findByText('Great Tit')).toBeInTheDocument();
    expect(screen.getByText('House Sparrow')).toBeInTheDocument();

    await user.type(screen.getByRole('searchbox'), 'sparrow');

    expect(screen.queryByText('Great Tit')).not.toBeInTheDocument();
    expect(screen.getByText('House Sparrow')).toBeInTheDocument();
  });
});
