/** Central React Query keys (#296, #343, #359) — в UI только `queryKeys.*`; сырой `queryKey: ['…']` запрещён ESLint. */

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
    retentionConfig: ['system', 'retention-config'] as const,
    qualityTimeseries: (bucket: 'hour' | 'day') =>
      ['system', 'quality-timeseries', bucket] as const,
    qualityHealth: (hours: number) =>
      ['system', 'quality-health', hours] as const,
    yoloDetectorHealth: (hours: number) =>
      ['system', 'yolo-detector-health', hours] as const,
    triggerGraph: (hours: number) => ['system', 'trigger-graph', hours] as const,
  },
  /** Карточки страницы «Система» с плоскими ключами кэша (legacy-строки). */
  systemPanels: {
    configAudit: ['config-audit'] as const,
    observability: ['system-observability'] as const,
    catalogRepairStatus: ['catalog-repair-status'] as const,
    recognitionImprovementSummary: ['recognition-improvement-summary'] as const,
    recognitionImprovementTrainStatus: [
      'recognition-improvement-train-status',
    ] as const,
    speciesDataQuality: ['species-data-quality'] as const,
    catalogCoverageMetrics: ['catalog-coverage-metrics'] as const,
    classifierDatasetAlignment: ['classifier-dataset-alignment'] as const,
    mlRuntimeStatus: ['ml-runtime-status'] as const,
    classifierCalibrationReport: ['classifier-calibration-report'] as const,
    tuningWorkbench: ['tuning-workbench'] as const,
    feedbackLoopStatus: ['feedback-loop-status'] as const,
    fusionExportStatus: ['fusion-export-status'] as const,
    fusionEvalStatus: ['fusion-eval-status'] as const,
    domainHealth: ['system-domain-health'] as const,
    birdnetFifo: ['system-birdnet-fifo'] as const,
  },
  feed: {
    info: ['feed-info'] as const,
  },
  /** Polling `/api/ui/status` в шапке/футере. */
  health: {
    status: ['status'] as const,
  },
  live: {
    cameras: ['cameras'] as const,
    overlays: (cameraId: string) => ['live-overlays', cameraId] as const,
  },
  birdFood: {
    all: ['birdFood'] as const,
  },
  fileTest: {
    status: ['file-test-status'] as const,
    files: ['file-test-files'] as const,
  },
  /** Страница каталога видов (отдельно от `bird-directory`). */
  speciesDirectory: {
    list: ['species-directory'] as const,
  },
  favorites: {
    bySpecies: ['favorites', 'by-species'] as const,
  },
  /** Таймлайн + счётчик unknowns на той же дате (#343). */
  timeline: {
    observerTimezone: ['timeline-observer-timezone'] as const,
    speciesVisits: (
      date: string,
      timeOfDay: string,
      filterHour: number | null,
      favoritesOnly: boolean,
      triggerSource: string,
    ) =>
      [
        'speciesVisits',
        date,
        timeOfDay,
        filterHour,
        favoritesOnly ? 1 : 0,
        triggerSource,
      ] as const,
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
    list: (date: string, timeOfDay: string, queue: string = 'default', reviewReason: string = 'all') =>
      ['unknowns', date, timeOfDay, queue, reviewReason] as const,
    all: ['unknowns'] as const,
  },
  labelling: {
    cases: (
      status: 'pending' | 'approved' | 'rejected' | 'semantic_review_required' | 'all',
      withMediaOnly = true,
    ) => ['labelling-cases', status, withMediaOnly ? 'media-only' : 'all-cases'] as const,
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
    reidMatch: (id: string) => ['video-reid-match', id] as const,
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
    bySpecies: (speciesId: string) => ['speciesSummary', speciesId] as const,
  },
} as const;
