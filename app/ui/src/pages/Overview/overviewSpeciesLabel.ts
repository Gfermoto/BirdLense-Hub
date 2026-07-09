import type { TFunction } from 'i18next';
import type { OverviewTopSpecies } from '../../types';

export function overviewSpeciesLabel(
  t: TFunction,
  species: Pick<OverviewTopSpecies, 'name' | 'unidentified'>,
): string {
  if (species.unidentified) {
    if (species.name === 'Rodent') return t('overview.unidentifiedRodent');
    return t('overview.unidentifiedBird');
  }
  return species.name;
}

export function overviewLastDetectionLabel(
  t: TFunction,
  speciesName: string,
  unidentified?: boolean,
): string {
  if (!unidentified) return speciesName;
  if (speciesName === 'Rodent') return t('overview.lastRodentUnknown');
  return t('overview.lastBirdUnknown');
}
