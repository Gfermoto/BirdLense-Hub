import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { Timeline } from './Timeline';
import type { SpeciesVisit } from '../../types';

vi.mock('@mui/material/useMediaQuery', () => ({
  default: () => false,
}));

vi.mock('../../components/VisitCard', () => ({
  VisitCard: ({ visit }: { visit: SpeciesVisit }) => (
    <div data-testid={`visit-card-${visit.id}`}>{visit.species.name}</div>
  ),
}));

const visits: SpeciesVisit[] = [
  {
    id: 101,
    start_time: '2026-04-15T08:00:00Z',
    end_time: '2026-04-15T08:05:00Z',
    max_simultaneous: 1,
    species: { id: 1, name: 'Great Tit' },
    detections: [],
  },
  {
    id: 102,
    start_time: '2026-04-15T09:00:00Z',
    end_time: '2026-04-15T09:05:00Z',
    max_simultaneous: 2,
    species: { id: 2, name: 'Eurasian Magpie' },
    detections: [],
  },
];

describe('Timeline', () => {
  it('keeps desktop visit card shells full width on both sides of the rail', () => {
    render(<Timeline visits={visits} />);

    const leftShell = screen.getByTestId('timeline-card-shell-101');
    const rightShell = screen.getByTestId('timeline-card-shell-102');

    expect(leftShell).toHaveStyle({ width: '100%' });
    expect(rightShell).toHaveStyle({ width: '100%' });
  });
});
