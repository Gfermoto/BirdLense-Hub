import type { SpeciesVisit } from '../../types';
import type { BirdProfile } from '../../api/speciesOverviewDetections';

export function getVisitBehaviorLabels(visit: SpeciesVisit): string[] {
  return [
    ...new Set(
      (visit.behavior_events ?? [])
        .map((event) => String(event.label || '').trim().toLowerCase())
        .filter((label) => Boolean(label)),
    ),
  ];
}

export function getVisitNickname(visit: SpeciesVisit): string {
  return String(visit.individual_nickname || '').trim();
}

export function getVisitBirdProfileId(visit: SpeciesVisit): number | null {
  if (visit.bird_profile_id != null) {
    return Number(visit.bird_profile_id);
  }
  for (const detection of visit.detections ?? []) {
    if (detection.bird_profile_id != null) {
      return Number(detection.bird_profile_id);
    }
  }
  return null;
}

export function visitMatchesBirdProfile(
  visit: SpeciesVisit,
  profileId: number | null,
  profilesById: Map<number, BirdProfile>,
): boolean {
  if (!profileId) return true;
  const visitProfileId = getVisitBirdProfileId(visit);
  if (visitProfileId === profileId) return true;
  const profile = profilesById.get(profileId);
  if (!profile) return false;
  const nickname = getVisitNickname(visit).toLowerCase();
  return nickname.length > 0 && nickname === profile.display_name.trim().toLowerCase();
}

export function getVisitBehaviorSortValue(visit: SpeciesVisit): string {
  return getVisitBehaviorLabels(visit).join(', ');
}

export function visitMatchesBehavior(
  visit: SpeciesVisit,
  behaviorValue: string,
): boolean {
  const normalized = behaviorValue.trim().toLowerCase();
  if (!normalized) return true;
  return getVisitBehaviorLabels(visit).includes(normalized);
}
