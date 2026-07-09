import type { ReactElement } from 'react';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { describe, expect, it } from 'vitest';
import { UnknownCard } from './index';
import type { UnknownDetection } from '../../api/timeline';

/** Align with App.tsx BrowserRouter future flags (silences v7 upgrade warnings). */
const memoryRouterFuture = {
  v7_startTransition: true,
  v7_relativeSplatPath: true,
} as const;

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: false } },
});

function renderUnknownCard(ui: ReactElement) {
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter future={memoryRouterFuture}>{ui}</MemoryRouter>
    </QueryClientProvider>,
  );
}

const detection: UnknownDetection = {
  id: 1,
  video_id: 10,
  species_id: 99,
  species_name: 'Bird',
  confidence: 0.41,
  start_time: '2026-04-15T08:00:00Z',
  end_time: '2026-04-15T08:00:02Z',
  source: 'video',
  review_state: 'pending',
  review_reason: 'low_confidence',
};

describe('UnknownCard', () => {
  it('shows localized review reason chip for operator explainability', () => {
    renderUnknownCard(
        <UnknownCard
          detection={detection}
          onCorrect={() => Promise.resolve()}
          onConfirm={() => Promise.resolve()}
          canEdit={false}
          videoListReturnPath="/timeline?review=1"
          selected={false}
          onToggleSelected={() => {}}
        />,
    );

    expect(screen.getByText('Model unsure about species')).toBeInTheDocument();
  });
});
