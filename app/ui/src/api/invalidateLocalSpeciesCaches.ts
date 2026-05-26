import type { QueryClient } from '@tanstack/react-query';

import { queryKeys } from './queryKeys';

/** Ключи, которые зависят от правки вида на видео (согласовано с VideoInfo при удалении). */
const AFTER_LOCAL_SPECIES_EDIT_KEYS = [
  queryKeys.unknowns.all,
  queryKeys.timeline.unknownsCountAll,
  queryKeys.timeline.speciesVisitsAll,
  queryKeys.overview.all,
  queryKeys.calendar.timelineTab,
  queryKeys.calendar.migration,
  queryKeys.birdDirectory.all,
  queryKeys.species.directory,
  queryKeys.speciesDirectory.list,
  queryKeys.speciesSummary.all,
] as const;

/**
 * Сброс кэшей после локальной правки вида детекции / merge на странице видео.
 */
export function invalidateLocalSpeciesEditCaches(
  queryClient: QueryClient,
  videoId: string | number | null | undefined,
): void {
  if (videoId != null) {
    queryClient.invalidateQueries({
      queryKey: queryKeys.video.detail(String(videoId)),
    });
    queryClient.invalidateQueries({
      queryKey: queryKeys.video.reidMatch(String(videoId)),
    });
  }
  for (const key of AFTER_LOCAL_SPECIES_EDIT_KEYS) {
    queryClient.invalidateQueries({ queryKey: [...key] });
  }
}
