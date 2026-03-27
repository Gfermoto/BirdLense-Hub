import { useState, useCallback } from 'react';
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
import Alert from '@mui/material/Alert';
import AlertTitle from '@mui/material/AlertTitle';
import LinearProgress from '@mui/material/LinearProgress';
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
  exportDataset,
  retroExportDataset,
  cleanDataset,
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

interface RegenerateSpectrogramsResponse {
  generated: number;
  failed: number;
  skipped: number;
  message: string;
  frames_updated?: number;
  tracks?: boolean;
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
  } | null>(null);
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

  const { refetch } = useQuery<StorageStats[]>({
    queryKey: ['storageStats'],
    queryFn: async () => {
      const { data } = await axios.get<StorageStats[]>(
        `${BASE_API_URL}/storage/stats`,
      );
      return data;
    },
  });

  const pollRegenerateStatus = useCallback(
    async (): Promise<RegenerateSpectrogramsResponse | null> => {
      const { data } = await axios.get<{
        status: string;
        result: RegenerateSpectrogramsResponse | null;
        error: string | null;
        progress?: { processed: number; total: number };
      }>(`${BASE_API_URL}/system/regenerate-spectrograms/status`);
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
        };
      }>(`${BASE_API_URL}/system/regenerate-tracks/status`);
      if (data.progress && data.progress.total > 0) {
        setTracksProgress({
          processed: data.progress.processed,
          total: data.progress.total,
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
        await axios.post(`${BASE_API_URL}/system/regenerate-spectrograms`, params || {});
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
    { force?: boolean; start_date?: string; end_date?: string }
  >({
    mutationFn: async (params) => {
      try {
        await axios.post(`${BASE_API_URL}/system/regenerate-tracks`, params || {});
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
        tracks: true,
      });
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
        </Alert>
      )}

      <LocalizationProvider dateAdapter={AdapterDayjs}>
        <Stack spacing={3} id="recordings">
          {/* Период для операций — общий блок */}
          <Paper sx={{ p: 2 }}>
            <Typography variant="subtitle1" fontWeight={600} gutterBottom>
              {t('storage.operationsPeriod')}
            </Typography>
            <Stack direction="row" spacing={2} alignItems="center" flexWrap="wrap">
              <DatePicker
                label={t('storage.periodFrom')}
                value={operationsPeriod.start}
                onChange={(v) =>
                  v && setOperationsPeriod((p) => ({ ...p, start: v }))
                }
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
                maxDate={dayjs()}
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
                <Button
                  variant="outlined"
                  disabled={regenerateTracksMutation.isPending}
                  onClick={() =>
                    regenerateTracksMutation.mutate({
                      start_date: operationsPeriod.start.format('YYYY-MM-DD'),
                      end_date: operationsPeriod.end.format('YYYY-MM-DD'),
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
                  </Box>
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
                    checked={retroRebuild}
                    onChange={(e) => setRetroRebuild(e.target.checked)}
                    size="small"
                  />
                }
                label={t('storage.retroExportRebuild')}
                sx={{ alignSelf: 'flex-start' }}
              />
              <Button
                variant="outlined"
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
                title={
                  retroRebuild
                    ? t('storage.retroExportRebuildHint')
                    : t('storage.retroExportHint')
                }
                fullWidth
              >
                {retroExporting
                  ? t('storage.retroExporting')
                  : retroRebuild
                    ? t('storage.retroExportRebuild')
                    : t('storage.retroExport')}
              </Button>
              {retroExporting && (
                <LinearProgress sx={{ height: 4, borderRadius: 2 }} />
              )}
              <Button
                variant="outlined"
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
                title={t('storage.cleanDatasetHint')}
                fullWidth
              >
                {cleanDatasetLoading
                  ? t('storage.cleanDatasetLoading')
                  : t('storage.cleanDataset')}
              </Button>
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
              <Button
                variant="outlined"
                disabled={cleanOrphanedMutation.isPending}
                onClick={() => {
                  if (window.confirm(t('storage.cleanOrphanedVisitsConfirm'))) {
                    setError(null);
                    cleanOrphanedMutation.mutate();
                  }
                }}
                startIcon={<BuildIcon />}
                title={t('storage.cleanOrphanedVisitsHint')}
                fullWidth
              >
                {cleanOrphanedMutation.isPending
                  ? t('storage.merging')
                  : t('storage.cleanOrphanedVisits')}
              </Button>
              {cleanOrphanedMutation.isPending && (
                <LinearProgress sx={{ height: 4, borderRadius: 2 }} />
              )}
              <Button
                variant="outlined"
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
