import { useState, useCallback, useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import axios from 'axios';
import Box from '@mui/material/Box';
import Paper from '@mui/material/Paper';
import Typography from '@mui/material/Typography';
import Button from '@mui/material/Button';
import Checkbox from '@mui/material/Checkbox';
import FormControlLabel from '@mui/material/FormControlLabel';
import Stack from '@mui/material/Stack';
import Chip from '@mui/material/Chip';
import ToggleButton from '@mui/material/ToggleButton';
import ToggleButtonGroup from '@mui/material/ToggleButtonGroup';
import Alert from '@mui/material/Alert';
import AlertTitle from '@mui/material/AlertTitle';
import LinearProgress from '@mui/material/LinearProgress';
import Tooltip from '@mui/material/Tooltip';
import Autocomplete from '@mui/material/Autocomplete';
import TextField from '@mui/material/TextField';
import { DatePicker } from '@mui/x-date-pickers/DatePicker';
import { LocalizationProvider } from '@mui/x-date-pickers/LocalizationProvider';
import { AdapterDayjs } from '@mui/x-date-pickers/AdapterDayjs';
import dayjs, { Dayjs } from 'dayjs';
import DeleteOutlineIcon from '@mui/icons-material/DeleteOutline';
import FolderOpenIcon from '@mui/icons-material/FolderOpen';
import GraphicEqIcon from '@mui/icons-material/GraphicEq';
import RouteIcon from '@mui/icons-material/Route';
import DownloadIcon from '@mui/icons-material/Download';
import MergeTypeIcon from '@mui/icons-material/MergeType';
import BuildIcon from '@mui/icons-material/Build';
import {
  BASE_API_URL,
  JOB_STATUS_POLL_TIMEOUT_MS,
  exportDataset,
  retroExportDataset,
  cleanDataset,
  fetchTrackRegenSpeciesOptions,
} from '../../api/api';

interface StorageStats {
  date: string;
  fileCount: number;
  totalSize: number;
}

interface PurgeResponse {
  message: string;
  deletedCount: number;
  deletedSize: number;
}

interface ScanResponse {
  imported: number;
  message: string;
  spectrogramRegenerationStarted?: boolean;
}

interface TrackRegenParams {
  frame_step: number;
  lores_px: number;
  detection_strategy: string;
  max_runtime_sec: number;
  species_ids?: number[];
  species_partial_regen?: boolean;
  ignore_regional_species?: boolean;
}

interface RegenerateSpectrogramsResponse {
  generated: number;
  failed: number;
  skipped: number;
  message: string;
  frames_updated?: number;
  tracks?: boolean;
  regen_params?: TrackRegenParams;
  precise_rerun_candidate_count?: number;
  precise_rerun_candidates?: Array<{
    video_id: number;
    video_path: string | null;
    reason: string;
  }>;
}

interface MergeSpeciesResponse {
  merged: number;
  details?: string[];
  message: string;
}

interface CleanOrphanedResponse {
  orphaned: number;
  synced: number;
  message: string;
}

interface RetroExportResponse {
  saved: number;
  skipped: number;
  skipped_no_bbox?: number;
  deleted?: number;
  errors: string[];
}

interface CleanDatasetResponse {
  deleted_fullframe: number;
  deleted_orphaned: number;
  errors: string[];
  dry_run: boolean;
}

const formatBytes = (bytes: number): string => {
  if (!Number.isFinite(bytes) || bytes < 0) return '0 B';
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.min(
    Math.floor(Math.log(bytes) / Math.log(k)),
    sizes.length - 1,
  );
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(2))} ${sizes[i]}`;
};

export const RecordingsAndDataset = () => {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [selectedDate, setSelectedDate] = useState<Dayjs | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<
    | PurgeResponse
    | RegenerateSpectrogramsResponse
    | MergeSpeciesResponse
    | CleanOrphanedResponse
    | RetroExportResponse
    | CleanDatasetResponse
    | null
  >(null);
  const [exportingDataset, setExportingDataset] = useState(false);
  const [readyForTrain, setReadyForTrain] = useState(true);
  const [includeTestSplit, setIncludeTestSplit] = useState(false);
  const [strictQualityExport, setStrictQualityExport] = useState(false);
  const [retroExporting, setRetroExporting] = useState(false);
  const [cleanDatasetLoading, setCleanDatasetLoading] = useState(false);
  const [retroRebuild, setRetroRebuild] = useState(false);
  const [spectrogramProgress, setSpectrogramProgress] = useState<{
    processed: number;
    total: number;
  } | null>(null);
  const [tracksProgress, setTracksProgress] = useState<{
    processed: number;
    total: number;
    current_video?: string | null;
    regen_params?: TrackRegenParams;
  } | null>(null);
  const [preciseRerunCandidates, setPreciseRerunCandidates] = useState<Array<{
    video_id: number;
    video_path: string | null;
    reason: string;
  }>>([]);
  const [preciseRerunFilter, setPreciseRerunFilter] = useState<'all' | 'problematic' | 'manual'>('all');
  const [trackRegenPreset, setTrackRegenPreset] = useState<'accurate' | 'fast'>('fast');
  const [trackRegenSpeciesIds, setTrackRegenSpeciesIds] = useState<number[]>([]);
  const [operationsPeriod, setOperationsPeriod] = useState<{
    start: Dayjs;
    end: Dayjs;
  }>(() => ({
    start: dayjs().subtract(1, 'week'),
    end: dayjs(),
  }));
  const [onlyManuallyCorrected, setOnlyManuallyCorrected] = useState(false);
  const POLL_INTERVAL_MS = 2000;
  const POLL_TIMEOUT_MS = 2 * 60 * 60 * 1000; // 2h for large historical batches
  const problematicReasons = new Set([
    'processing_failed',
    'video_file_missing',
    'missing_video_path',
    'no_detections_fast_run',
    'no_detections_for_selected_species',
  ]);
  const manualReasons = new Set(['has_manual_corrections']);

  const preciseCandidatesByReason = useMemo(() => {
    const acc: Record<string, number> = {};
    for (const c of preciseRerunCandidates) {
      const key = c.reason || 'unknown';
      acc[key] = (acc[key] || 0) + 1;
    }
    return Object.entries(acc).sort((a, b) => b[1] - a[1]);
  }, [preciseRerunCandidates]);

  const filteredPreciseCandidates = useMemo(() => {
    if (preciseRerunFilter === 'problematic') {
      return preciseRerunCandidates.filter((c) => problematicReasons.has(c.reason));
    }
    if (preciseRerunFilter === 'manual') {
      return preciseRerunCandidates.filter((c) => manualReasons.has(c.reason));
    }
    return preciseRerunCandidates;
  }, [preciseRerunCandidates, preciseRerunFilter]);

  const { data: storageStats = [], refetch } = useQuery<StorageStats[]>({
    queryKey: ['storageStats'],
    queryFn: async () => {
      const { data } = await axios.get<StorageStats[]>(
        `${BASE_API_URL}/storage/stats`,
      );
      return data;
    },
  });

  const { data: trackRegenSpeciesOptions = [] } = useQuery({
    queryKey: ['species', 'track-regen-options'],
    queryFn: fetchTrackRegenSpeciesOptions,
    staleTime: 60_000,
  });

  const storageRange = useMemo(() => {
    if (!storageStats.length) return null;
    const sorted = [...storageStats].sort((a, b) => a.date.localeCompare(b.date));
    const first = sorted[0]?.date;
    const last = sorted[sorted.length - 1]?.date;
    if (!first || !last) return null;
    return {
      start: dayjs(first),
      end: dayjs(last),
      recordedDays: sorted.length,
      spanDays: dayjs(last).diff(dayjs(first), 'day') + 1,
      totalFiles: sorted.reduce((sum, item) => sum + (item.fileCount || 0), 0),
      totalSize: sorted.reduce((sum, item) => sum + (item.totalSize || 0), 0),
    };
  }, [storageStats]);

  /** With species filter, regen queue joins VideoSpecies — use full library span from stats
   *  so rare clips outside the default «last week» are not dropped. */
  const trackRegenDateRange = useMemo(() => {
    if (trackRegenSpeciesIds.length > 0 && storageRange) {
      return { start: storageRange.start, end: storageRange.end };
    }
    return { start: operationsPeriod.start, end: operationsPeriod.end };
  }, [
    trackRegenSpeciesIds.length,
    storageRange,
    operationsPeriod.start,
    operationsPeriod.end,
  ]);

  const applyPreset = useCallback(
    (preset: 'last7' | 'last30' | 'all') => {
      const today = storageRange?.end || dayjs();
      if (preset === 'all' && storageRange) {
        setOperationsPeriod({
          start: storageRange.start,
          end: storageRange.end,
        });
        return;
      }
      const days = preset === 'last30' ? 30 : 7;
      const rawStart = today.subtract(days - 1, 'day');
      const boundedStart = storageRange && rawStart.isBefore(storageRange.start)
        ? storageRange.start
        : rawStart;
      setOperationsPeriod({
        start: boundedStart,
        end: today,
      });
    },
    [storageRange],
  );

  const pollRegenerateStatus = useCallback(
    async (): Promise<RegenerateSpectrogramsResponse | null> => {
      const { data } = await axios.get<{
        status: string;
        result: RegenerateSpectrogramsResponse | null;
        error: string | null;
        progress?: { processed: number; total: number };
      }>(`${BASE_API_URL}/system/regenerate-spectrograms/status`, {
        timeout: JOB_STATUS_POLL_TIMEOUT_MS,
      });
      if (data.progress && data.progress.total > 0) {
        setSpectrogramProgress({
          processed: data.progress.processed,
          total: data.progress.total,
        });
      }
      if (data.status === 'done' && data.result) {
        setSpectrogramProgress(null);
        return data.result;
      }
      if (data.status === 'done' && data.error) {
        setSpectrogramProgress(null);
        throw new Error(data.error);
      }
      return null;
    },
    [],
  );

  const pollRegenerateTracksStatus = useCallback(
    async (): Promise<RegenerateSpectrogramsResponse | null> => {
      const { data } = await axios.get<{
        status: string;
        result: RegenerateSpectrogramsResponse | null;
        error: string | null;
        progress?: {
          processed: number;
          total: number;
          generated: number;
          failed: number;
          skipped: number;
          current_video?: string | null;
          regen_params?: TrackRegenParams;
        };
      }>(`${BASE_API_URL}/system/regenerate-tracks/status`, {
        timeout: JOB_STATUS_POLL_TIMEOUT_MS,
      });
      if (data.progress && data.progress.total > 0) {
        setTracksProgress({
          processed: data.progress.processed,
          total: data.progress.total,
          current_video: data.progress.current_video || null,
          regen_params: data.progress.regen_params,
        });
      }
      if (data.status === 'done' && data.result) {
        setTracksProgress(null);
        return data.result;
      }
      if (data.status === 'done' && data.error) {
        setTracksProgress(null);
        throw new Error(data.error);
      }
      return null;
    },
    [],
  );

  const scanMutation = useMutation<ScanResponse, Error, void>({
    mutationFn: async () => {
      const { data } = await axios.post<ScanResponse>(
        `${BASE_API_URL}/system/recordings/scan`,
      );
      return data;
    },
    onSuccess: (data) => {
      const msg = data.spectrogramRegenerationStarted
        ? `${data.message}. ${t('storage.spectrogramRegenStarted')}`
        : data.message;
      setSuccess({
        message: msg,
        deletedCount: data.imported,
        deletedSize: 0,
      });
      refetch();
      queryClient.invalidateQueries({ queryKey: ['speciesVisits'] });
      queryClient.invalidateQueries({ queryKey: ['overview'] });
      setTimeout(() => setSuccess(null), 5000);
    },
    onError: (err) => {
      setError(
        err instanceof Error ? err.message : t('storage.scanFailed'),
      );
    },
  });

  const regenerateMutation = useMutation<
    RegenerateSpectrogramsResponse,
    Error,
    { force?: boolean; start_date?: string; end_date?: string }
  >({
    mutationFn: async (params) => {
      try {
        await axios.post(`${BASE_API_URL}/system/regenerate-spectrograms`, params || {}, {
          timeout: JOB_STATUS_POLL_TIMEOUT_MS,
        });
      } catch (e) {
        // 409 means a batch is already running; attach to its status stream.
        if (!(axios.isAxiosError(e) && e.response?.status === 409)) {
          throw e;
        }
      }
      const deadline = Date.now() + POLL_TIMEOUT_MS;
      while (Date.now() < deadline) {
        await new Promise((r) => setTimeout(r, POLL_INTERVAL_MS));
        const result = await pollRegenerateStatus();
        if (result) return result;
      }
      throw new Error(t('storage.regenerateTimeout'));
    },
    onSuccess: (data) => {
      setSpectrogramProgress(null);
      setSuccess({
        message: data.message || '',
        generated: data.generated,
        failed: data.failed,
        skipped: data.skipped,
      });
      refetch();
      queryClient.invalidateQueries({ queryKey: ['videos'] });
      queryClient.invalidateQueries({ queryKey: ['speciesVisits'] });
      setTimeout(() => setSuccess(null), 8000);
    },
    onError: (err: unknown) => {
      setSpectrogramProgress(null);
      const msg = axios.isAxiosError(err)
        ? (err.response?.data as { error?: string } | undefined)?.error ||
          err.message
        : (err instanceof Error ? err.message : t('storage.regenerateFailed'));
      setError(msg);
    },
  });

  const regenerateTracksMutation = useMutation<
    RegenerateSpectrogramsResponse,
    Error,
    {
      force?: boolean;
      start_date?: string;
      end_date?: string;
      frame_step?: number;
      video_ids?: number[];
      species_ids?: number[];
    }
  >({
    mutationFn: async (params) => {
      try {
        await axios.post(`${BASE_API_URL}/system/regenerate-tracks`, params || {}, {
          timeout: JOB_STATUS_POLL_TIMEOUT_MS,
        });
      } catch (e) {
        // 409 means a batch is already running; attach to in-progress batch.
        if (!(axios.isAxiosError(e) && e.response?.status === 409)) {
          throw e;
        }
      }
      const deadline = Date.now() + POLL_TIMEOUT_MS;
      while (Date.now() < deadline) {
        await new Promise((r) => setTimeout(r, POLL_INTERVAL_MS));
        const result = await pollRegenerateTracksStatus();
        if (result) return result;
      }
      throw new Error(t('storage.regenerateTimeout'));
    },
    onSuccess: (data) => {
      setTracksProgress(null);
      setSuccess({
        message: data.message || '',
        generated: data.generated,
        failed: data.failed,
        skipped: data.skipped,
        frames_updated: data.frames_updated,
        precise_rerun_candidate_count: data.precise_rerun_candidate_count,
        precise_rerun_candidates: data.precise_rerun_candidates,
        tracks: true,
      });
      setPreciseRerunCandidates(data.precise_rerun_candidates || []);
      refetch();
      queryClient.invalidateQueries({ queryKey: ['videos'] });
      queryClient.invalidateQueries({ queryKey: ['speciesVisits'] });
      setTimeout(() => setSuccess(null), 8000);
    },
    onError: (err) => {
      setTracksProgress(null);
      const msg = axios.isAxiosError(err)
        ? (err.response?.data as { error?: string } | undefined)?.error ||
          err.message
        : (err instanceof Error ? err.message : t('storage.regenerateTracksFailed'));
      setError(msg);
    },
  });

  const purgeVideosMutation = useMutation<PurgeResponse, Error, Dayjs>({
    mutationFn: async (date) => {
      const { data } = await axios.post<PurgeResponse>(
        `${BASE_API_URL}/storage/purge`,
        { date: date.format('YYYY-MM-DD') },
      );
      return data;
    },
    onSuccess: (data) => {
      setSelectedDate(null);
      setSuccess(data);
      refetch();
      setTimeout(() => setSuccess(null), 5000);
    },
    onError: (error) => {
      setError(
        error instanceof Error ? error.message : t('storage.purgeFailed'),
      );
    },
  });

  const mergeSpeciesMutation = useMutation<MergeSpeciesResponse, Error, void>({
    mutationFn: async () => {
      const { data } = await axios.post<MergeSpeciesResponse>(
        `${BASE_API_URL}/system/merge-duplicate-species`,
      );
      return data;
    },
    onSuccess: (data) => {
      setSuccess(data);
      refetch();
      queryClient.invalidateQueries({ queryKey: ['speciesVisits'] });
      queryClient.invalidateQueries({ queryKey: ['overview'] });
      queryClient.invalidateQueries({ queryKey: ['migration-calendar'] });
      queryClient.invalidateQueries({ queryKey: ['bird-directory'] });
      setTimeout(() => setSuccess(null), 6000);
    },
    onError: (err) => {
      setError(
        err instanceof Error ? err.message : t('storage.mergeSpeciesFailed'),
      );
    },
  });

  const cleanOrphanedMutation = useMutation<CleanOrphanedResponse, Error, void>({
    mutationFn: async () => {
      const { data } = await axios.post<CleanOrphanedResponse>(
        `${BASE_API_URL}/system/clean-orphaned-visits`,
      );
      return data;
    },
    onSuccess: (data) => {
      setSuccess(data);
      refetch();
      queryClient.invalidateQueries({ queryKey: ['speciesVisits'] });
      queryClient.invalidateQueries({ queryKey: ['overview'] });
      queryClient.invalidateQueries({ queryKey: ['migration-calendar'] });
      queryClient.invalidateQueries({ queryKey: ['bird-directory'] });
      setTimeout(() => setSuccess(null), 6000);
    },
    onError: (err) => {
      setError(
        err instanceof Error ? err.message : t('storage.mergeSpeciesFailed'),
      );
    },
  });

  const handlePurge = (): void => {
    if (!selectedDate) return;
    if (
      window.confirm(
        t('storage.purgeConfirm', {
          date: selectedDate.format('YYYY-MM-DD'),
        }),
      )
    ) {
      setSuccess(null);
      purgeVideosMutation.mutate(selectedDate);
    }
  };

  return (
    <Box>
      <Typography variant="h5" sx={{ mb: 3 }}>
        {t('library.recordingsAndDataset')}
      </Typography>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
          <AlertTitle>{t('common.error')}</AlertTitle>
          {error}
        </Alert>
      )}

      {success && (
        <Alert
          severity="success"
          sx={{ mb: 2 }}
          onClose={() => setSuccess(null)}
        >
          <AlertTitle>{t('common.success')}</AlertTitle>
          {'saved' in success && 'skipped' in success
            ? 'deleted' in success && (success as RetroExportResponse).deleted != null
              ? t('storage.retroExportSuccessRebuild', {
                  saved: (success as RetroExportResponse).saved,
                  deleted: (success as RetroExportResponse).deleted,
                })
              : (success as RetroExportResponse).skipped_no_bbox != null
                ? t('storage.retroExportSuccessWithNoBbox', {
                    saved: (success as RetroExportResponse).saved,
                    skipped: (success as RetroExportResponse).skipped,
                    skipped_no_bbox: (success as RetroExportResponse)
                      .skipped_no_bbox,
                  })
                : t('storage.retroExportSuccess', {
                    saved: (success as RetroExportResponse).saved,
                    skipped: (success as RetroExportResponse).skipped,
                  })
            : 'deleted_fullframe' in success
              ? (success as CleanDatasetResponse).dry_run
                ? t('storage.cleanDatasetDryRun', {
                    fullframe: (success as CleanDatasetResponse).deleted_fullframe,
                    orphaned: (success as CleanDatasetResponse).deleted_orphaned,
                  })
                : t('storage.cleanDatasetSuccess', {
                    fullframe: (success as CleanDatasetResponse).deleted_fullframe,
                    orphaned: (success as CleanDatasetResponse).deleted_orphaned,
                  })
              : 'orphaned' in success
                ? t('storage.cleanOrphanedVisitsSuccess', {
                    orphaned: (success as CleanOrphanedResponse).orphaned,
                    synced: (success as CleanOrphanedResponse).synced,
                  })
              : 'merged' in success
                ? t('storage.mergeSpeciesSuccess', {
                    count: (success as MergeSpeciesResponse).merged,
                  })
                : 'generated' in success
                  ? 'tracks' in success && success.tracks
                    ? 'frames_updated' in success && success.frames_updated
                      ? t('storage.regenerateTracksSuccessWithFrames', {
                          generated: success.generated,
                          failed: success.failed,
                          skipped: success.skipped,
                          frames_updated: success.frames_updated,
                        })
                      : t('storage.regenerateTracksSuccess', {
                          generated: success.generated,
                          failed: success.failed,
                          skipped: success.skipped,
                        })
                    : t('storage.regenerateSuccess', {
                        generated: success.generated,
                        failed: success.failed,
                        skipped: success.skipped,
                      })
                  : success.deletedSize > 0
                    ? t('storage.deleted', {
                        count: success.deletedCount,
                        size: formatBytes(success.deletedSize),
                      })
                    : t('storage.imported', { count: success.deletedCount })}
          {'tracks' in success &&
            success.tracks &&
            (success.precise_rerun_candidate_count || 0) > 0 && (
              <Typography variant="body2" sx={{ mt: 0.75 }}>
                {t('storage.regenerateTracksPreciseCandidatesFound', {
                  count: success.precise_rerun_candidate_count || 0,
                })}
              </Typography>
            )}
        </Alert>
      )}

      <LocalizationProvider dateAdapter={AdapterDayjs}>
        <Stack spacing={3} id="recordings">
          {/* Период для операций — общий блок */}
          <Paper sx={{ p: 2 }}>
            <Typography variant="subtitle1" fontWeight={600} gutterBottom>
              {t('storage.operationsPeriod')}
            </Typography>
            <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap sx={{ mb: 2 }}>
              <Button size="small" variant="outlined" onClick={() => applyPreset('last7')}>
                {t('storage.presetLast7Days')}
              </Button>
              <Button size="small" variant="outlined" onClick={() => applyPreset('last30')}>
                {t('storage.presetLast30Days')}
              </Button>
              <Button
                size="small"
                variant="contained"
                onClick={() => applyPreset('all')}
                disabled={!storageRange}
              >
                {t('storage.presetAllTime')}
              </Button>
            </Stack>
            <Stack direction="row" spacing={2} alignItems="center" flexWrap="wrap">
              <DatePicker
                label={t('storage.periodFrom')}
                value={operationsPeriod.start}
                onChange={(v) =>
                  v && setOperationsPeriod((p) => ({ ...p, start: v }))
                }
                minDate={storageRange?.start}
                maxDate={operationsPeriod.end}
                slotProps={{ textField: { size: 'small', sx: { width: 160 } } }}
              />
              <DatePicker
                label={t('storage.periodTo')}
                value={operationsPeriod.end}
                onChange={(v) =>
                  v && setOperationsPeriod((p) => ({ ...p, end: v }))
                }
                minDate={operationsPeriod.start}
                maxDate={storageRange?.end || dayjs()}
                slotProps={{ textField: { size: 'small', sx: { width: 160 } } }}
              />
              <FormControlLabel
                control={
                  <Checkbox
                    checked={onlyManuallyCorrected}
                    onChange={(e) =>
                      setOnlyManuallyCorrected(e.target.checked)
                    }
                    size="small"
                  />
                }
                label={t('storage.onlyManuallyCorrected')}
              />
            </Stack>
            <Typography variant="caption" color="text.secondary" display="block" sx={{ mt: 1 }}>
              {storageRange
                ? t('storage.archiveRangeSummary', {
                    start: storageRange.start.format('YYYY-MM-DD'),
                    end: storageRange.end.format('YYYY-MM-DD'),
                    spanDays: storageRange.spanDays,
                    recordedDays: storageRange.recordedDays,
                    files: storageRange.totalFiles,
                    size: formatBytes(storageRange.totalSize),
                  })
                : t('storage.archiveRangeUnavailable')}
            </Typography>
          </Paper>

          <Alert severity="info" sx={{ '& ol': { m: 0, pl: 2.5 } }}>
            <AlertTitle>{t('library.datasetFlowTitle')}</AlertTitle>
            <Typography variant="body2" color="inherit" sx={{ mb: 1 }}>
              {t('library.datasetFlowIntro')}
            </Typography>
            <ol>
              <li>{t('library.datasetFlowStep1')}</li>
              <li>{t('library.datasetFlowStep2')}</li>
              <li>{t('library.datasetFlowStep3')}</li>
              <li>{t('library.datasetFlowStep4')}</li>
            </ol>
          </Alert>

          <Alert severity="warning" sx={{ '& ul': { m: 0, pl: 2.5 } }}>
            <AlertTitle>{t('storage.heavyOpsTitle')}</AlertTitle>
            <Typography variant="body2" color="inherit" sx={{ mb: 1 }}>
              {t('storage.heavyOpsIntro')}
            </Typography>
            <ul>
              <li>{t('storage.heavyOpsSpectrograms')}</li>
              <li>{t('storage.heavyOpsTracks')}</li>
              <li>{t('storage.heavyOpsDataset')}</li>
            </ul>
          </Alert>

          {/* 1. Импорт */}
          <Paper sx={{ p: 2 }}>
            <Typography variant="subtitle1" fontWeight={600} gutterBottom>
              {t('library.sectionImport')}
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
              {t('storage.scanHint')}
            </Typography>
            <Button
              variant="outlined"
              disabled={scanMutation.isPending}
              onClick={() => scanMutation.mutate()}
              startIcon={<FolderOpenIcon />}
              fullWidth
            >
              {scanMutation.isPending
                ? t('storage.scanning')
                : t('storage.scanImport')}
            </Button>
            {scanMutation.isPending && (
              <LinearProgress sx={{ mt: 1, height: 4, borderRadius: 2 }} />
            )}
          </Paper>

          {/* 2. Регенерация */}
          <Paper sx={{ p: 2 }}>
            <Typography variant="subtitle1" fontWeight={600} gutterBottom>
              {t('library.sectionRegenerate')}
            </Typography>
            <Stack spacing={2}>
              <Box>
                <Button
                  variant="outlined"
                  color="error"
                  disabled={regenerateMutation.isPending}
                  onClick={() =>
                    regenerateMutation.mutate({
                      start_date: operationsPeriod.start.format('YYYY-MM-DD'),
                      end_date: operationsPeriod.end.format('YYYY-MM-DD'),
                    })
                  }
                  startIcon={<GraphicEqIcon />}
                  fullWidth
                >
                  {regenerateMutation.isPending
                    ? t('storage.regenerating')
                    : t('storage.regenerateSpectrograms')}
                </Button>
                {(regenerateMutation.isPending || spectrogramProgress) && (
                  <Box sx={{ mt: 1 }}>
                    <LinearProgress
                      variant={
                        spectrogramProgress?.total
                          ? 'determinate'
                          : 'indeterminate'
                      }
                      value={
                        spectrogramProgress?.total
                          ? (spectrogramProgress.processed /
                              spectrogramProgress.total) *
                            100
                          : undefined
                      }
                      sx={{ height: 6, borderRadius: 2 }}
                    />
                    {spectrogramProgress?.total && (
                      <Typography variant="caption" color="text.secondary">
                        {t('storage.regeneratingProgress', spectrogramProgress)}
                      </Typography>
                    )}
                  </Box>
                )}
              </Box>
              <Box>
                <Autocomplete
                  multiple
                  options={trackRegenSpeciesOptions}
                  getOptionLabel={(o) => o.name}
                  isOptionEqualToValue={(a, b) => a.id === b.id}
                  value={trackRegenSpeciesOptions.filter((o) =>
                    trackRegenSpeciesIds.includes(o.id),
                  )}
                  onChange={(_, v) => setTrackRegenSpeciesIds(v.map((x) => x.id))}
                  renderInput={(params) => (
                    <TextField
                      {...params}
                      label={t('storage.trackRegenSpeciesLabel')}
                      placeholder={t('storage.trackRegenSpeciesPlaceholder')}
                      size="small"
                    />
                  )}
                  sx={{ mb: 1 }}
                />
                <Typography variant="caption" color="text.secondary" display="block" sx={{ mb: 1 }}>
                  {t('storage.trackRegenSpeciesHint')}
                </Typography>
                {trackRegenSpeciesIds.length > 0 && (
                  <Typography variant="caption" color="text.secondary" display="block" sx={{ mb: 1 }}>
                    {storageRange
                      ? t('storage.trackRegenSpeciesPeriodNote')
                      : t('storage.trackRegenSpeciesPeriodNoStats')}
                  </Typography>
                )}
                <Stack spacing={1} sx={{ mb: 1 }}>
                  <Typography variant="caption" color="text.secondary">
                    {t('storage.regenerateTracksPresetLabel')}
                  </Typography>
                  <ToggleButtonGroup
                    size="small"
                    exclusive
                    value={trackRegenPreset}
                    onChange={(_, value) => {
                      if (value) setTrackRegenPreset(value);
                    }}
                    aria-label={t('storage.regenerateTracksPresetLabel')}
                  >
                    <ToggleButton value="accurate">
                      {t('storage.regenerateTracksPresetAccurate')}
                    </ToggleButton>
                    <ToggleButton value="fast">
                      {t('storage.regenerateTracksPresetFast')}
                    </ToggleButton>
                  </ToggleButtonGroup>
                </Stack>
                <Button
                  variant="outlined"
                  color="error"
                  disabled={regenerateTracksMutation.isPending}
                  onClick={() =>
                    regenerateTracksMutation.mutate({
                      start_date: trackRegenDateRange.start.format('YYYY-MM-DD'),
                      end_date: trackRegenDateRange.end.format('YYYY-MM-DD'),
                      frame_step: trackRegenPreset === 'fast' ? 6 : 1,
                      ...(trackRegenSpeciesIds.length
                        ? { species_ids: [...trackRegenSpeciesIds] }
                        : {}),
                    })
                  }
                  startIcon={<RouteIcon />}
                  fullWidth
                >
                  {regenerateTracksMutation.isPending
                    ? tracksProgress
                      ? t('storage.regeneratingProgress', tracksProgress)
                      : t('storage.regenerating')
                    : t('storage.regenerateTracks')}
                </Button>
                {(regenerateTracksMutation.isPending || tracksProgress) && (
                  <Box sx={{ mt: 1 }}>
                    <LinearProgress
                      variant={
                        tracksProgress?.total ? 'determinate' : 'indeterminate'
                      }
                      value={
                        tracksProgress?.total
                          ? (tracksProgress.processed / tracksProgress.total) *
                            100
                          : undefined
                      }
                      sx={{ height: 6, borderRadius: 2 }}
                    />
                    {tracksProgress?.total && (
                      <Typography variant="caption" color="text.secondary">
                        {t('storage.regeneratingProgress', tracksProgress)}
                      </Typography>
                    )}
                    {tracksProgress?.current_video && (
                      <Typography variant="caption" color="text.secondary" display="block">
                        {t('storage.regeneratingCurrentVideo', {
                          video: tracksProgress.current_video,
                        })}
                      </Typography>
                    )}
                    {tracksProgress?.regen_params && (
                      <>
                        <Typography variant="caption" color="text.secondary" display="block">
                          {t('storage.regenerateTracksEffectiveParams', {
                            step: tracksProgress.regen_params.frame_step,
                            px: tracksProgress.regen_params.lores_px,
                            strategy: tracksProgress.regen_params.detection_strategy,
                            timeout: tracksProgress.regen_params.max_runtime_sec,
                          })}
                        </Typography>
                        {(tracksProgress.regen_params.species_ids?.length || 0) > 0 && (
                          <Typography variant="caption" color="text.secondary" display="block">
                            {t('storage.regenerateTracksSpeciesFilterActive', {
                              count: tracksProgress.regen_params.species_ids!.length,
                            })}
                          </Typography>
                        )}
                        {tracksProgress.regen_params.ignore_regional_species && (
                          <Typography variant="caption" color="text.secondary" display="block">
                            {t('storage.regenerateTracksFullClassScope')}
                          </Typography>
                        )}
                      </>
                    )}
                  </Box>
                )}
                {preciseRerunCandidates.length > 0 && (
                  <Stack spacing={1}>
                    <Typography variant="caption" color="text.secondary">
                      {t('storage.regenerateTracksPreciseCandidatesFound', {
                        count: preciseRerunCandidates.length,
                      })}
                    </Typography>
                    <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
                      <Button
                        size="small"
                        variant={preciseRerunFilter === 'all' ? 'contained' : 'outlined'}
                        onClick={() => setPreciseRerunFilter('all')}
                      >
                        {t('common.all')}
                      </Button>
                      <Button
                        size="small"
                        variant={preciseRerunFilter === 'problematic' ? 'contained' : 'outlined'}
                        onClick={() => setPreciseRerunFilter('problematic')}
                      >
                        {t('storage.preciseFilterProblematic')}
                      </Button>
                      <Button
                        size="small"
                        variant={preciseRerunFilter === 'manual' ? 'contained' : 'outlined'}
                        onClick={() => setPreciseRerunFilter('manual')}
                      >
                        {t('storage.preciseFilterManual')}
                      </Button>
                    </Stack>
                    <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
                      {preciseCandidatesByReason.map(([reason, count]) => (
                        <Chip
                          key={reason}
                          size="small"
                          label={`${reason}: ${count}`}
                          variant="outlined"
                        />
                      ))}
                    </Stack>
                    <Button
                      variant="text"
                      color="error"
                      disabled={
                        regenerateTracksMutation.isPending ||
                        filteredPreciseCandidates.length === 0
                      }
                      onClick={() =>
                        regenerateTracksMutation.mutate({
                          frame_step: 1,
                          video_ids: filteredPreciseCandidates.map((x) => x.video_id),
                          ...(trackRegenSpeciesIds.length
                            ? { species_ids: [...trackRegenSpeciesIds] }
                            : {}),
                        })
                      }
                      fullWidth
                    >
                      {t('storage.regenerateTracksRunPreciseCandidates', {
                        count: filteredPreciseCandidates.length,
                      })}
                    </Button>
                    <Button
                      variant="outlined"
                      size="small"
                      onClick={() => {
                        const blob = new Blob(
                          [
                            JSON.stringify(
                              {
                                generated_at: new Date().toISOString(),
                                filter: preciseRerunFilter,
                                candidates: filteredPreciseCandidates,
                              },
                              null,
                              2,
                            ),
                          ],
                          { type: 'application/json' },
                        );
                        const url = URL.createObjectURL(blob);
                        const a = document.createElement('a');
                        a.href = url;
                        a.download = 'track_regen_precise_candidates.json';
                        a.click();
                        URL.revokeObjectURL(url);
                      }}
                    >
                      {t('storage.downloadPreciseCandidates')}
                    </Button>
                  </Stack>
                )}
              </Box>
            </Stack>
          </Paper>

          {/* 3. Датасет */}
          <Paper sx={{ p: 2 }}>
            <Typography variant="subtitle1" fontWeight={600} gutterBottom>
              {t('library.sectionDataset')}
            </Typography>
            <Stack spacing={2}>
              <Button
                variant="outlined"
                disabled={exportingDataset}
                onClick={async () => {
                  setExportingDataset(true);
                  setError(null);
                  try {
                    await exportDataset({
                      start_date: operationsPeriod.start.format('YYYY-MM-DD'),
                      end_date: operationsPeriod.end.format('YYYY-MM-DD'),
                      only_manually_corrected: onlyManuallyCorrected,
                      ready_for_train: readyForTrain,
                      test_ratio:
                        readyForTrain && includeTestSplit ? 0.1 : undefined,
                      strict_quality:
                        readyForTrain && strictQualityExport ? true : undefined,
                    });
                  } catch (e) {
                    setError(
                      e instanceof Error
                        ? e.message
                        : t('storage.datasetExportFailed'),
                    );
                  } finally {
                    setExportingDataset(false);
                  }
                }}
                startIcon={<DownloadIcon />}
                fullWidth
              >
                {exportingDataset
                  ? t('storage.exporting')
                  : t('storage.exportDataset')}
              </Button>
              {exportingDataset && (
                <LinearProgress sx={{ height: 4, borderRadius: 2 }} />
              )}
              <FormControlLabel
                control={
                  <Checkbox
                    checked={readyForTrain}
                    onChange={(e) => setReadyForTrain(e.target.checked)}
                    size="small"
                  />
                }
                label={t('storage.readyForTrain')}
                sx={{ alignSelf: 'flex-start' }}
              />
              <FormControlLabel
                control={
                  <Checkbox
                    checked={includeTestSplit}
                    onChange={(e) => setIncludeTestSplit(e.target.checked)}
                    disabled={!readyForTrain}
                    size="small"
                  />
                }
                label={t('storage.includeTestSplit')}
                sx={{ alignSelf: 'flex-start' }}
              />
              <FormControlLabel
                control={
                  <Checkbox
                    checked={strictQualityExport}
                    onChange={(e) => setStrictQualityExport(e.target.checked)}
                    disabled={!readyForTrain}
                    size="small"
                  />
                }
                label={t('storage.strictQualityExport')}
                sx={{ alignSelf: 'flex-start' }}
              />
              <FormControlLabel
                control={
                  <Checkbox
                    checked={retroRebuild}
                    onChange={(e) => setRetroRebuild(e.target.checked)}
                    size="small"
                    color="error"
                  />
                }
                label={t('storage.retroExportRebuild')}
                sx={{
                  alignSelf: 'flex-start',
                  '& .MuiFormControlLabel-label': retroRebuild
                    ? { color: 'error.main', fontWeight: 600 }
                    : undefined,
                }}
              />
              <Tooltip
                title={
                  retroRebuild
                    ? t('storage.retroExportRebuildHint')
                    : t('storage.retroExportHint')
                }
              >
                <span>
                  <Button
                    variant="outlined"
                    color={retroRebuild ? 'error' : 'primary'}
                    disabled={retroExporting}
                    onClick={async () => {
                      if (
                        retroRebuild &&
                        !window.confirm(t('storage.retroExportRebuildConfirm'))
                      ) {
                        return;
                      }
                      setRetroExporting(true);
                      setError(null);
                      setSuccess(null);
                      try {
                        const result = await retroExportDataset(
                          0,
                          {
                            start_date: operationsPeriod.start.format('YYYY-MM-DD'),
                            end_date: operationsPeriod.end.format('YYYY-MM-DD'),
                          },
                          onlyManuallyCorrected,
                          retroRebuild,
                        );
                        setSuccess(result);
                        refetch();
                      } catch (e) {
                        setError(
                          e instanceof Error
                            ? e.message
                            : t('storage.retroExportFailed'),
                        );
                      } finally {
                        setRetroExporting(false);
                      }
                    }}
                    startIcon={<FolderOpenIcon />}
                    fullWidth
                  >
                    {retroExporting
                      ? t('storage.retroExporting')
                      : retroRebuild
                        ? t('storage.retroExportRebuild')
                        : t('storage.retroExport')}
                  </Button>
                </span>
              </Tooltip>
              {retroExporting && (
                <LinearProgress sx={{ height: 4, borderRadius: 2 }} />
              )}
              <Tooltip title={t('storage.cleanDatasetHint')}>
                <span>
                  <Button
                    variant="outlined"
                    color="error"
                    disabled={cleanDatasetLoading}
                    onClick={async () => {
                      if (!window.confirm(t('storage.cleanDatasetConfirm'))) return;
                      setCleanDatasetLoading(true);
                      setError(null);
                      setSuccess(null);
                      try {
                        const result = await cleanDataset({
                          dry_run: false,
                          remove_fullframe: true,
                          remove_orphaned: false,
                        });
                        setSuccess(result);
                        refetch();
                      } catch (e) {
                        setError(
                          e instanceof Error
                            ? e.message
                            : t('storage.retroExportFailed'),
                        );
                      } finally {
                        setCleanDatasetLoading(false);
                      }
                    }}
                    startIcon={<BuildIcon />}
                    fullWidth
                  >
                    {cleanDatasetLoading
                      ? t('storage.cleanDatasetLoading')
                      : t('storage.cleanDataset')}
                  </Button>
                </span>
              </Tooltip>
              {cleanDatasetLoading && (
                <LinearProgress sx={{ height: 4, borderRadius: 2 }} />
              )}
            </Stack>
          </Paper>

          {/* 4. Управление БД */}
          <Paper sx={{ p: 2 }}>
            <Typography variant="subtitle1" fontWeight={600} gutterBottom>
              {t('library.sectionDb')}
            </Typography>
            <Stack spacing={2}>
              <Tooltip title={t('storage.cleanOrphanedVisitsHint')}>
                <span>
                  <Button
                    variant="outlined"
                    color="error"
                    disabled={cleanOrphanedMutation.isPending}
                    onClick={() => {
                      if (window.confirm(t('storage.cleanOrphanedVisitsConfirm'))) {
                        setError(null);
                        cleanOrphanedMutation.mutate();
                      }
                    }}
                    startIcon={<BuildIcon />}
                    fullWidth
                  >
                    {cleanOrphanedMutation.isPending
                      ? t('storage.merging')
                      : t('storage.cleanOrphanedVisits')}
                  </Button>
                </span>
              </Tooltip>
              {cleanOrphanedMutation.isPending && (
                <LinearProgress sx={{ height: 4, borderRadius: 2 }} />
              )}
              <Button
                variant="outlined"
                color="error"
                disabled={mergeSpeciesMutation.isPending}
                onClick={() => {
                  if (window.confirm(t('storage.mergeSpeciesConfirm'))) {
                    setError(null);
                    mergeSpeciesMutation.mutate();
                  }
                }}
                startIcon={<MergeTypeIcon />}
                fullWidth
              >
                {mergeSpeciesMutation.isPending
                  ? t('storage.merging')
                  : t('storage.mergeDuplicateSpecies')}
              </Button>
              {mergeSpeciesMutation.isPending && (
                <LinearProgress sx={{ height: 4, borderRadius: 2 }} />
              )}
            </Stack>
          </Paper>

          {/* 5. Удаление */}
          <Paper sx={{ p: 2 }}>
            <Typography variant="subtitle1" fontWeight={600} gutterBottom>
              {t('storage.purgeOld')}
            </Typography>
            <Stack direction="row" spacing={2} alignItems="center">
              <DatePicker
                label={t('storage.deleteBeforeDate')}
                value={selectedDate}
                onChange={(newValue: Dayjs | null) => setSelectedDate(newValue)}
                maxDate={dayjs()}
                slotProps={{
                  textField: { size: 'small', sx: { flex: 1 } },
                }}
              />
              <Button
                variant="contained"
                color="error"
                disabled={!selectedDate || purgeVideosMutation.isPending}
                onClick={handlePurge}
                startIcon={<DeleteOutlineIcon />}
              >
                {t('storage.purge')}
              </Button>
            </Stack>
            {purgeVideosMutation.isPending && (
              <LinearProgress sx={{ mt: 1, height: 4, borderRadius: 2 }} />
            )}
          </Paper>
        </Stack>
      </LocalizationProvider>
    </Box>
  );
};
