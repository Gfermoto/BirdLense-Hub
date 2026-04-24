/** Central React Query keys (#296, #343) — invalidate via queryKeys.* for stable contracts. */

import type { MigrationCalendarParams } from './migrationCalendar';

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
    byDay: (date: string) => ['overview', date] as const,
  },
  weather: {
    widget: ['weather'] as const,
    sunTimes: (date: string) => ['sun-times', date] as const,
  },
  storage: {
    stats: ['storageStats'] as const,
  },
  calendar: {
    /** Кэш вкладок/виджетов, привязанных к строке «timeline». */
    timelineTab: ['timeline'] as const,
    migration: ['migration-calendar'] as const,
    migrationData: (params: MigrationCalendarParams) =>
      ['migration-calendar', params] as const,
    regionComparison: ['region-comparison'] as const,
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
  video: {
    /** Префикс для сброса кэша по всем роликам. */
    all: ['video'] as const,
    detail: (id: string) => ['video', id] as const,
    neighbors: (id: string) => ['video-neighbors', id] as const,
    neighborsAll: ['video-neighbors'] as const,
    detectionFrames: (id: string) => ['video-detection-frames', id] as const,
    listAll: ['videos'] as const,
    trackRegenStatusUi: (videoId: number | null, nonce: number) =>
      ['track-regen-status-ui', videoId, nonce] as const,
    specRegenStatusUi: (videoId: number | null, nonce: number) =>
      ['spec-regen-status-ui', videoId, nonce] as const,
  },
  birdDirectory: {
    all: ['bird-directory'] as const,
  },
  speciesSummary: {
    all: ['speciesSummary'] as const,
  },
} as const;
