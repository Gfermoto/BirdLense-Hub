import { describe, expect, it } from 'vitest';
import type { SpeciesVisit } from '../../types';
import {
  getVisitBirdProfileId,
  visitMatchesBehavior,
  visitMatchesBirdProfile,
} from './timelineFilters';

const baseVisit = (overrides: Partial<SpeciesVisit> = {}): SpeciesVisit =>
  ({
    id: 1,
    start_time: '2026-01-01T10:00:00Z',
    end_time: '2026-01-01T10:05:00Z',
    max_simultaneous: 1,
    species: { id: 10, name: 'Great Tit' },
    detections: [],
    ...overrides,
  }) as SpeciesVisit;

describe('timelineFilters', () => {
  it('matches bird profile by visit id or nickname fallback', () => {
    const profiles = new Map([
      [
        7,
        {
          id: 7,
          display_name: 'Zorro',
          species_id: 10,
          avatar_url: null,
          status: 'active',
        },
      ],
    ]);
    expect(
      visitMatchesBirdProfile(
        baseVisit({ bird_profile_id: 7 }),
        7,
        profiles,
      ),
    ).toBe(true);
    expect(
      visitMatchesBirdProfile(
        baseVisit({ individual_nickname: 'Zorro' }),
        7,
        profiles,
      ),
    ).toBe(true);
    expect(
      visitMatchesBirdProfile(
        baseVisit({ individual_nickname: 'Other' }),
        7,
        profiles,
      ),
    ).toBe(false);
  });

  it('reads bird profile id from detections', () => {
    const visit = baseVisit({
      detections: [
        {
          id: 99,
          video_id: 5,
          start_time: '2026-01-01T10:00:00Z',
          end_time: '2026-01-01T10:01:00Z',
          confidence: 0.9,
          source: 'video',
          bird_profile_id: 12,
        },
      ],
    });
    expect(getVisitBirdProfileId(visit)).toBe(12);
  });

  it('matches behavior by exact label', () => {
    const visit = baseVisit({
      behavior_events: [{ label: 'feeding' }],
    });
    expect(visitMatchesBehavior(visit, 'feeding')).toBe(true);
    expect(visitMatchesBehavior(visit, 'flying')).toBe(false);
    expect(visitMatchesBehavior(visit, '')).toBe(true);
  });
});
