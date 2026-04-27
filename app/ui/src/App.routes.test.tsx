import { render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import App from './App';

vi.mock('./api/systemAuditMetrics', () => ({
  trackSiteVisitor: vi.fn().mockResolvedValue(undefined),
}));

vi.mock('./contexts/ProtectedAreaContext', () => ({
  ProtectedAreaProvider: ({ children }: { children: React.ReactNode }) => (
    <>{children}</>
  ),
}));

vi.mock('./components/Navigation', () => ({
  Navigation: () => <nav>nav</nav>,
}));

vi.mock('./components/SkipToContent', () => ({
  SkipToContent: () => null,
}));

vi.mock('./components/Footer', () => ({
  Footer: () => null,
}));

vi.mock('./components/InstallPrompt', () => ({
  InstallPrompt: () => null,
}));

vi.mock('./components/PwaUpdatePrompt', () => ({
  PwaUpdatePrompt: () => null,
}));

vi.mock('./components/ErrorBoundary', () => ({
  ErrorBoundary: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

vi.mock('./pages/Overview', () => ({
  default: () => <div>overview-page</div>,
}));

vi.mock('./pages/Timeline', () => ({
  default: () => <div>timeline-page</div>,
}));

vi.mock('./pages/Favorites', () => ({
  default: () => <div>favorites-page</div>,
}));

vi.mock('./pages/VideoDetails', () => ({
  VideoDetails: () => <div>video-details-page</div>,
}));

vi.mock('./pages/FoodManagement', () => ({
  FoodManagement: () => <div>food-page</div>,
}));

vi.mock('./pages/Live', () => ({
  LivePage: () => <div>live-page</div>,
}));

vi.mock('./pages/Settings', () => ({
  Settings: () => <div>settings-page</div>,
}));

vi.mock('./pages/SpeciesDirectory', () => ({
  default: () => <div>species-directory-page</div>,
}));

vi.mock('./pages/SpeciesSummary', () => ({
  default: () => <div>species-summary-page</div>,
}));

vi.mock('./pages/System', () => ({
  System: () => <div>system-page</div>,
}));

vi.mock('./pages/Library', () => ({
  Library: () => <div>library-page</div>,
}));

vi.mock('./pages/MigrationCalendar', () => ({
  MigrationCalendar: () => <div>migration-catalog-page</div>,
}));

vi.mock('./pages/NotFound', () => ({
  default: () => <div>not-found-page</div>,
}));

describe('App species routes', () => {
  beforeEach(() => {
    window.history.pushState({}, '', '/');
  });

  it('renders migration catalog on /species', async () => {
    window.history.pushState({}, '', '/species');

    render(<App />);

    expect(await screen.findByText('migration-catalog-page')).toBeInTheDocument();
    expect(screen.queryByText('species-directory-page')).not.toBeInTheDocument();
  });

  it('renders card directory on /species-directory', async () => {
    window.history.pushState({}, '', '/species-directory');

    render(<App />);

    expect(await screen.findByText('species-directory-page')).toBeInTheDocument();
  });

  it('renders favorites catalog on /favorites', async () => {
    window.history.pushState({}, '', '/favorites');

    render(<App />);

    expect(await screen.findByText('favorites-page')).toBeInTheDocument();
  });
});
