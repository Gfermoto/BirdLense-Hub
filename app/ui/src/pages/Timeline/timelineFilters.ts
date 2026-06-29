import type { SpeciesVisit } from '../../types';
import type { BirdProfile } from '../../api/speciesOverviewDetections';

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

export function visitMatchesCameras(
  visit: SpeciesVisit,
  cameraIds: string[],
): boolean {
  if (!cameraIds.length) return true;
  const cam = String(visit.camera_id || '').trim();
  if (!cam) return false;
  return cameraIds.includes(cam);
}

export function parseCameraIdsFromSearchParams(
  params: URLSearchParams,
): string[] {
  const raw = params.get('camera_ids') || params.get('camera_id') || '';
  return raw
    .split(',')
    .map((part) => part.trim())
    .filter(Boolean);
}
