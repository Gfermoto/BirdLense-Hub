import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it } from 'vitest';
import { UnknownCard } from './index';
import type { UnknownDetection } from '../../api/timeline';

/** Align with App.tsx BrowserRouter future flags (silences v7 upgrade warnings). */
const memoryRouterFuture = {
  v7_startTransition: true,
  v7_relativeSplatPath: true,
} as const;

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
    render(
      <MemoryRouter future={memoryRouterFuture}>
        <UnknownCard
          detection={detection}
          speciesList={[]}
          onCorrect={() => Promise.resolve()}
          onConfirm={() => Promise.resolve()}
          canEdit={false}
          videoListReturnPath="/timeline?review=1"
          selected={false}
          onToggleSelected={() => {}}
        />
      </MemoryRouter>,
    );

    expect(screen.getByText('Low confidence')).toBeInTheDocument();
  });
});
