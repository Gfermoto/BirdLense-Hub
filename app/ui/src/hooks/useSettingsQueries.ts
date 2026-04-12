import { useQuery } from '@tanstack/react-query';
import { fetchObservedSpecies, fetchSettings } from '../api/api';
import { queryKeys } from '../api/queryKeys';

export function useSettingsQuery(enabled: boolean) {
  return useQuery({
    queryKey: queryKeys.settings.all,
    queryFn: fetchSettings,
    enabled,
    retry: false,
  });
}

export function useObservedSpeciesQuery() {
  return useQuery({
    queryKey: queryKeys.species.observed,
    queryFn: fetchObservedSpecies,
    staleTime: 5 * 60 * 1000,
  });
}
