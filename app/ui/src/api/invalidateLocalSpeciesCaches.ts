import type { QueryClient } from '@tanstack/react-query';

/** Ключи, которые зависят от правки вида на видео (согласовано с VideoInfo при удалении). */
const AFTER_LOCAL_SPECIES_EDIT_KEYS = [
  ['unknowns'],
  ['unknowns-count'],
  ['speciesVisits'],
  ['overview'],
  ['timeline'],
  ['migration-calendar'],
  ['bird-directory'],
  ['species'],
  ['speciesSummary'],
] as const;

/**
 * Сброс кэшей после локальной правки вида детекции / merge на странице видео.
 */
export function invalidateLocalSpeciesEditCaches(
  queryClient: QueryClient,
  videoId: string | number | null | undefined,
): void {
  if (videoId != null) {
    queryClient.invalidateQueries({ queryKey: ['video', String(videoId)] });
  }
  for (const key of AFTER_LOCAL_SPECIES_EDIT_KEYS) {
    queryClient.invalidateQueries({ queryKey: [...key] });
  }
}
