/** Central React Query keys (#296, #343) — invalidate via queryKeys.* for stable contracts. */

export const queryKeys = {
  settings: {
    all: ['settings'] as const,
    /** Must match useQuery keys in ProtectedAreaProvider (session gate). */
    requiresPassword: ['settings-requires-password'] as const,
    checkAccess: ['settings-check-access'] as const,
  },
  species: {
    observed: ['species', 'observed'] as const,
    /** Справочник видов (Unknowns picker и др.). */
    directory: ['species'] as const,
  },
  overview: {
    all: ['overview'] as const,
  },
  calendar: {
    /** Кэш вкладок/виджетов, привязанных к строке «timeline». */
    timelineTab: ['timeline'] as const,
    migration: ['migration-calendar'] as const,
  },
  system: {
    readiness: ['system', 'readiness'] as const,
    metricsLive: ['system', 'metrics', 'live'] as const,
    metricsHistory: (hours: number) =>
      ['system', 'metrics', 'history', hours] as const,
    visitors: (days: number) => ['system', 'visitors', days] as const,
    processorLogs: (lines: number) =>
      ['system', 'processorLogs', lines] as const,
  },
  /** Таймлайн + счётчик unknowns на той же дате (#343). */
  timeline: {
    observerTimezone: ['timeline-observer-timezone'] as const,
    speciesVisits: (
      date: string,
      timeOfDay: string,
      filterHour: number | null,
    ) => ['speciesVisits', date, timeOfDay, filterHour] as const,
    /** Префикс для invalidateQueries — все окна таймлайна. */
    speciesVisitsAll: ['speciesVisits'] as const,
    unknownsCount: (
      date: string,
      timeOfDay: string,
      filterHour: number | null,
    ) => ['unknowns-count', date, timeOfDay, filterHour] as const,
    unknownsCountAll: ['unknowns-count'] as const,
  },
  unknowns: {
    list: (date: string, timeOfDay: string) =>
      ['unknowns', date, timeOfDay] as const,
    all: ['unknowns'] as const,
  },
  corrections: {
    recent: ['corrections-recent'] as const,
  },
} as const;
