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
  vi.fn().mockResolvedValue({
    items: [
    {
      id: 1,
      name: 'Great Tit',
      parent_id: null,
      created_at: '2026-01-01T00:00:00Z',
      image_url: null,
      description: 'Garden bird',
      active: true,
      count: 12,
      catalog_card_incomplete: true,
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
      catalog_card_incomplete: true,
    },
    {
      id: 3,
      name: 'Common Wood-Pigeon',
      parent_id: null,
      created_at: '2026-01-01T00:00:00Z',
      image_url: null,
      description: 'Pigeon from woodland edges',
      active: true,
      count: 2,
      catalog_card_incomplete: true,
    },
    ],
    meta: {
      db_species_total: 1214,
      allowlist_total: 526,
      listed_allowlist: 3,
      allowlist_incomplete: 3,
    },
  }),
);

vi.mock('../../contexts/ProtectedAreaContext', () => ({
  useProtectedArea: () => ({
    requiresPassword: false,
    hasContributorTier: false,
    unlocked: true,
    role: null,
    setUnlocked: () => {},
    logoutAccess: async () => {},
    isLoading: false,
    accessError: null,
    canEdit: false,
    isAdmin: false,
  }),
}));

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

  it('matches hyphenated species names when user types spaces', async () => {
    const user = userEvent.setup();
    renderPage();

    expect(await screen.findByText('Common Wood-Pigeon')).toBeInTheDocument();

    await user.type(screen.getByRole('searchbox'), 'wood pigeon');

    expect(screen.getByText('Common Wood-Pigeon')).toBeInTheDocument();
    expect(screen.queryByText('Great Tit')).not.toBeInTheDocument();
  });
});
