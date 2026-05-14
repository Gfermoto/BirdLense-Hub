import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';
import type { SpeciesVisit } from '../types';
import { VisitCard } from './VisitCard';
import '../i18n';

const memoryRouterFuture = {
  v7_startTransition: true,
  v7_relativeSplatPath: true,
} as const;

const protectedAreaState = vi.hoisted(() => ({
  canEdit: true,
}));

vi.mock('../contexts/ProtectedAreaContext', () => ({
  useProtectedArea: () => protectedAreaState,
}));

describe('VisitCard', () => {
  it('renders nickname and behavior labels when present', () => {
    const qc = new QueryClient();
    const visit: SpeciesVisit = {
      id: 1,
      start_time: '2026-03-25T15:00:00Z',
      end_time: '2026-03-25T15:05:00Z',
      max_simultaneous: 1,
      timeline_kind: 'visit',
      species: {
        id: 10,
        name: 'Great Tit',
      },
      individual_nickname: 'Nova',
      behavior_events: [
        { label: 'feeding' },
      ],
      detections: [
        {
          id: 100,
          video_id: 200,
          start_time: '2026-03-25T15:00:01Z',
          end_time: '2026-03-25T15:00:04Z',
          confidence: 0.88,
          source: 'video',
        },
      ],
    };

    render(
      <QueryClientProvider client={qc}>
        <MemoryRouter future={memoryRouterFuture}>
          <VisitCard visit={visit} />
        </MemoryRouter>
      </QueryClientProvider>,
    );

    expect(screen.getByText(/Nova/)).toBeInTheDocument();
    expect(
      screen.getByText(/(feeding|кормление)/i),
    ).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: /(Set nickname|Задать кличку)/i }),
    ).toBeInTheDocument();
  });
});
