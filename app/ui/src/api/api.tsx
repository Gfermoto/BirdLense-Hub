import axios from 'axios';
import { ApiHttpError, BASE_URL } from './client';

export { BASE_URL, BASE_API_URL, JOB_STATUS_POLL_TIMEOUT_MS } from './client';

/** Текст ошибки из JSON `{ error: string }` или fallback (для мутаций UI). */
export function getApiErrorMessage(err: unknown, fallback: string): string {
  if (axios.isAxiosError(err)) {
    const data = err.response?.data;
    if (data && typeof data === 'object' && data !== null && 'error' in data) {
      const msg = (data as { error?: unknown }).error;
      if (typeof msg === 'string' && msg.trim()) return msg;
    }
    if (err.message) return err.message;
  }
  if (err instanceof ApiHttpError) {
    if (typeof err.message === 'string' && err.message.trim()) return err.message;
  }
  if (err instanceof Error && err.message) return err.message;
  return fallback;
}

/**
 * Resolve image URL for display.
 * - Absolute (http/https) → as-is
 * - data:image/* only (block data:text/html etc. for XSS)
 * - Relative path (data/images/...) → BASE_URL + path
 * Species: Wikipedia returns full URLs. Bird food: relative paths from seed.
 */
export const resolveImageUrl = (
  url: string | null | undefined,
): string | undefined => {
  if (!url) return undefined;
  if (url.startsWith('http://') || url.startsWith('https://')) {
    // Do not proxy Wikimedia: server-side proxy can be rate-limited by shared IP.
    // Keep browser direct-load for Wikimedia and proxy only iNaturalist-hosted links.
    const lower = url.toLowerCase();
    const needsProxy = lower.includes('inaturalist');
    if (!needsProxy) return url;
    const base = BASE_URL || '';
    return `${base ? `${base}` : ''}/api/ui/species-image?url=${encodeURIComponent(url)}`;
  }
  if (url.startsWith('data:')) {
    const m = url.match(/^data:image\/(png|jpeg|jpg|gif|webp);base64,/i);
    return m ? url : undefined;
  }
  const base = BASE_URL || '';
  return base ? `${base}/${url}` : `/${url}`;
};

export {
  exportTimeline,
  exportTimelineForObserverDate,
  fetchTimeline,
  fetchTimelineForObserverDate,
  fetchUnknowns,
  fetchUnknownsForObserverDate,
} from './timeline';
export type { UnknownDetection } from './timeline';

export {
  fetchRegionComparison,
  fetchSunTimes,
  fetchWeather,
  formatSunTimeLocal,
} from './weatherRegion';
export type {
  MigrationCalendarData,
  MigrationCalendarParams,
} from './migrationCalendar';
export { fetchMigrationCalendar } from './migrationCalendar';

export {
  deleteVideo,
  patchVideoFavorite,
  fetchNearestRecordingDay,
  fetchVideo,
  fetchVideoDetectionFrames,
  fetchVideoFusionTrace,
  fetchVideoNeighbors,
  mergeVideoSpecies,
  regenerateTracksForSingleVideo,
} from './video';
export type {
  FusionTraceLine,
  FusionTracePayload,
  FusionTraceStep,
  FusionTraceTrack,
  VideoNeighbors,
} from './video';

export {
  cleanDataset,
  downloadDetectionCropForINaturalist,
  exportDataset,
  retroExportDataset,
} from './dataset';

export {
  addBirdFood,
  dispenseFeed,
  fetchBirdFood,
  fetchFeedInfo,
  postScaleTare,
  toggleBirdFood,
} from './birdFoodFeed';

export type { ReadinessPayload } from './camerasHealth';
export { fetchCameras, fetchReadiness, fetchStatus } from './camerasHealth';

export {
  fetchFileTestFiles,
  fetchFileTestStatus,
  fileTestDeleteFile,
  fileTestRun,
  fileTestStop,
  fileTestUpload,
} from './fileTest';
export type {
  FileTestFileRow,
  FileTestFilesResponse,
  FileTestStatusPayload,
} from './fileTest';

export type {
  CheckAccessResult,
  EbirdMappingSuggestion,
  EbirdMappingSuggestionsResponse,
  RequiresPasswordResult,
  VerifyPasswordResult,
} from './settingsSession';
export {
  checkSettingsAccess,
  fetchEbirdMappingSuggestions,
  fetchSettings,
  fetchSettingsRequiresPassword,
  logoutSettingsSession,
  patchSettings,
  updateSettings,
  verifySettingsPassword,
} from './settingsSession';

export type { ConfigAudit } from './systemAuditMetrics';
export type {
  ObservabilityPayload,
  ProcessorLogsResponse,
  SystemMetricsHistoryResponse,
  SystemMetricsHistorySample,
  SystemMetricsLive,
  SystemVisitorStats,
} from './systemAuditMetrics';
export {
  fetchConfigAudit,
  fetchObservability,
  fetchProcessorLogs,
  fetchSystemMetricsHistory,
  fetchSystemMetricsLive,
  fetchSystemVisitors,
  trackSiteVisitor,
} from './systemAuditMetrics';

export {
  fetchVapidPublicKey,
  refreshTelegramProxy,
  restartProcessor,
  sendTestNotification,
  subscribePush,
} from './notificationsProcessor';

export type { PurgeStorageBody } from './settingsYamlDb';
export {
  downloadDbBackup,
  downloadSettingsYamlFull,
  downloadSettingsYamlSafe,
  fetchCoordinatesByZip,
  importSettingsYaml,
  purgeStorageRecordings,
  restoreDbBackup,
} from './settingsYamlDb';

export type {
  BirdnetFifoDialogSnapshot,
  BirdnetFifoPayload,
  BirdnetSpeciesFifoRow,
  CatalogCardsCoverageSnapshot,
  CatalogCoverageMetrics,
  CatalogRepairStatus,
  ClassifierDatasetAlignmentReport,
  RecognitionImprovementSummary,
  SpeciesDataQualityReport,
  SystemJobStatus,
} from './speciesRegistryHub';
export {
  backfillSpeciesRegistry,
  downloadLatestFusionEvalReport,
  downloadLatestFusionExport,
  enrichSpeciesRegistryMetadata,
  fetchBirdnetFifoSnapshot,
  fetchCatalogCoverageMetrics,
  fetchCatalogRepairStatus,
  fetchClassifierDatasetAlignment,
  fetchFusionEvalStatus,
  fetchFusionExportStatus,
  fetchRecognitionImprovementSummary,
  fetchRecognitionImprovementTrainStatus,
  fetchSpeciesDataQuality,
  materializeSpeciesAllowlist,
  mergeDuplicateSpecies,
  previewBrokenVideosPurge,
  previewNoSpeciesVideosPurge,
  purgeBrokenVideosBatch,
  purgeNoSpeciesVideosBatch,
  PURGE_CONFIRM_PHRASE_BROKEN_VIDEOS_BATCH,
  PURGE_CONFIRM_PHRASE_NO_SPECIES_VIDEOS_BATCH,
  reconcileSpeciesCatalog,
  rollbackRecognitionImprovement,
  seedSpeciesRegistry,
  startCatalogRepair,
  startFusionEval,
  startFusionExport,
  startRecognitionImprovementTrain,
} from './speciesRegistryHub';

export type {
  CorrectionHistoryEntry,
  RefreshSpeciesMetadataResponse,
  ReviewQueueDeletePreview,
  ReviewQueueDeletePreviewVideo,
  TrackRegenProgress,
  TrackRegenerationJobStatus,
  TuningTargetEntry,
  TuningTargetsResponse,
  XenoCantoRecording,
} from './speciesOverviewDetections';
export {
  confirmDetection,
  deleteReviewQueueVideos,
  downloadReportPdf,
  fetchBirdDirectory,
  fetchObservedSpecies,
  fetchOverviewData,
  fetchRecentCorrections,
  fetchSpeciesSummary,
  fetchTrackRegenSpeciesOptions,
  fetchTrackRegenerationStatus,
  fetchTuningTargets,
  fetchTuningTargetsExport,
  fetchXenoCantoRecordings,
  previewReviewQueueDelete,
  refreshSpeciesMetadata,
  setSpeciesTuningTarget,
  updateDetectionSpecies,
} from './speciesOverviewDetections';
