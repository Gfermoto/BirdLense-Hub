import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { Navigation } from './Navigation';

const protectedAreaState = vi.hoisted(() => ({
  requiresPassword: false,
  unlocked: true,
  setUnlocked: vi.fn(),
  logoutAccess: vi.fn(),
  isLoading: false,
  isAdmin: true,
  canEdit: true,
}));

vi.mock('../contexts/ProtectedAreaContext', () => ({
  useProtectedArea: () => protectedAreaState,
}));

vi.mock('./SettingsPasswordDialog', () => ({
  SettingsPasswordDialog: () => null,
}));

vi.mock('./LanguageSwitcher', () => ({
  LanguageSwitcher: () => <div>lang</div>,
}));

vi.mock('./StatusIndicator', () => ({
  StatusIndicator: () => <div>status</div>,
}));

vi.mock('../api/birdFoodFeed', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../api/birdFoodFeed')>();
  return {
    ...actual,
    fetchFeedInfo: vi.fn().mockResolvedValue({ donate_url: '' }),
  };
});

function renderNav() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <Navigation />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('Navigation', () => {
  beforeEach(() => {
    protectedAreaState.isAdmin = true;
    protectedAreaState.canEdit = true;
  });

  it('shows species and recordings entry points for editable users', async () => {
    const { container } = renderNav();

    await screen.findByRole('link', { name: /home/i });
    const speciesLink = container.querySelector('a[href="/species"]');
    const timelineLink = container.querySelector('a[href="/timeline"]');

    expect(speciesLink).toBeInTheDocument();
    expect(timelineLink).toBeInTheDocument();
  });
});
