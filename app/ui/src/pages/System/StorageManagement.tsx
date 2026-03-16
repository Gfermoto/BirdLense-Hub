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
import { BarChart } from '@mui/x-charts/BarChart';
import dayjs, { Dayjs } from 'dayjs';
import DeleteOutlineIcon from '@mui/icons-material/DeleteOutline';
import FolderOpenIcon from '@mui/icons-material/FolderOpen';
import GraphicEqIcon from '@mui/icons-material/GraphicEq';
import RouteIcon from '@mui/icons-material/Route';
import DownloadIcon from '@mui/icons-material/Download';
import MergeTypeIcon from '@mui/icons-material/MergeType';
import BuildIcon from '@mui/icons-material/Build';
import { BASE_API_URL, exportDataset, retroExportDataset } from '../../api/api';

interface StorageStats {
  date: string;
  fileCount: number;
  totalSize: number;
}

// Update the chart data point type to allow string indexing
interface ChartDataPoint {
  [key: string]: string | number; // This allows for dynamic property access
  date: string;
  size: number;
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
  errors: string[];
}

const formatBytes = (bytes: number): string => {
  if (!Number.isFinite(bytes) || bytes < 0) return '0 B';
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.min(Math.floor(Math.log(bytes) / Math.log(k)), sizes.length - 1);
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(2))} ${sizes[i]}`;
};

export const StorageManagement = () => {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [selectedDate, setSelectedDate] = useState<Dayjs | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<PurgeResponse | RegenerateSpectrogramsResponse | MergeSpeciesResponse | CleanOrphanedResponse | RetroExportResponse | null>(null);
  const [exportingDataset, setExportingDataset] = useState(false);
  const [retroExporting, setRetroExporting] = useState(false);

  const {
    data: storageStats,
    isLoading,
    refetch,
  } = useQuery<StorageStats[]>({
    queryKey: ['storageStats'],
    queryFn: async () => {
      const { data } = await axios.get<StorageStats[]>(
        `${BASE_API_URL}/storage/stats`,
      );
      return data;
    },
  });

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

  const [spectrogramProgress, setSpectrogramProgress] = useState<{ processed: number; total: number } | null>(null);
  const [tracksProgress, setTracksProgress] = useState<{ processed: number; total: number } | null>(null);

  const pollRegenerateStatus = useCallback(async (): Promise<RegenerateSpectrogramsResponse | null> => {
    const { data } = await axios.get<{
      status: string;
      result: RegenerateSpectrogramsResponse | null;
      error: string | null;
      progress?: { processed: number; total: number };
    }>(`${BASE_API_URL}/system/regenerate-spectrograms/status`);
    if (data.progress && data.progress.total > 0) {
      setSpectrogramProgress({ processed: data.progress.processed, total: data.progress.total });
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
  }, []);
  const [operationsPeriod, setOperationsPeriod] = useState<{ start: Dayjs; end: Dayjs }>(() => ({
    start: dayjs().subtract(1, 'week'),
    end: dayjs(),
  }));
  const [onlyManuallyCorrected, setOnlyManuallyCorrected] = useState(false);

  const pollRegenerateTracksStatus = useCallback(async (): Promise<RegenerateSpectrogramsResponse | null> => {
    const { data } = await axios.get<{
      status: string;
      result: RegenerateSpectrogramsResponse | null;
      error: string | null;
      progress?: { processed: number; total: number; generated: number; failed: number; skipped: number };
    }>(`${BASE_API_URL}/system/regenerate-tracks/status`);
    if (data.progress && data.progress.total > 0) {
      setTracksProgress({ processed: data.progress.processed, total: data.progress.total });
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
  }, []);

  const regenerateMutation = useMutation<
    RegenerateSpectrogramsResponse,
    Error,
    { force?: boolean; start_date?: string; end_date?: string }
  >({
    mutationFn: async (params) => {
      await axios.post(`${BASE_API_URL}/system/regenerate-spectrograms`, params || {});
      for (let i = 0; i < 600; i++) {
        await new Promise((r) => setTimeout(r, 2000));
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
      const msg =
        (err as { response?: { data?: { error?: string } } })?.response?.data
          ?.error || (err instanceof Error ? err.message : t('storage.regenerateFailed'));
      setError(msg);
    },
  });

  const regenerateTracksMutation = useMutation<
    RegenerateSpectrogramsResponse,
    Error,
    { force?: boolean; start_date?: string; end_date?: string }
  >({
    mutationFn: async (params) => {
      await axios.post(`${BASE_API_URL}/system/regenerate-tracks`, params || {});
      // Poll up to 60 min (1800 * 2s) — много видео = долго
      for (let i = 0; i < 1800; i++) {
        await new Promise((r) => setTimeout(r, 2000));
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
      setError(
        err instanceof Error ? err.message : t('storage.regenerateTracksFailed'),
      );
    },
  });

  const purgeVideosMutation = useMutation<PurgeResponse, Error, Dayjs>({
    mutationFn: async (date) => {
      const { data } = await axios.post<PurgeResponse>(
        `${BASE_API_URL}/storage/purge`,
        {
          date: date.format('YYYY-MM-DD'),
        },
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
      setError(err instanceof Error ? err.message : t('storage.mergeSpeciesFailed'));
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
      setError(err instanceof Error ? err.message : t('storage.mergeSpeciesFailed'));
    },
  });

  const handlePurge = (): void => {
    if (!selectedDate) return;

    if (
      window.confirm(
        t('storage.purgeConfirm', { date: selectedDate.format('YYYY-MM-DD') }),
      )
    ) {
      setSuccess(null);
      purgeVideosMutation.mutate(selectedDate);
    }
  };

  if (isLoading) {
    return <Typography>{t('storage.loadingStats')}</Typography>;
  }

  const chartData: ChartDataPoint[] =
    storageStats?.map((stat) => ({
      date: dayjs(stat.date).format('MM/DD'),
      size: Number((stat.totalSize / (1024 * 1024)).toFixed(2)),
    })) || [];

  const totalSize: number =
    storageStats?.reduce((acc, stat) => acc + stat.totalSize, 0) || 0;
  const totalFiles: number =
    storageStats?.reduce((acc, stat) => acc + stat.fileCount, 0) || 0;

  return (
    <>
    <Box sx={{ pb: 2 }}>
      <Typography variant="h5" gutterBottom>
        {t('storage.title')}
      </Typography>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
          <AlertTitle>{t('common.error')}</AlertTitle>
          {error}
        </Alert>
      )}

      {(spectrogramProgress || tracksProgress) && (
        <Alert severity="info" sx={{ mb: 2 }}>
          <AlertTitle>
            {spectrogramProgress
              ? t('storage.regeneratingSpectrograms')
              : t('storage.regeneratingTracks')}
          </AlertTitle>
          <Typography variant="body2" sx={{ mb: 1 }}>
            {spectrogramProgress
              ? t('storage.regeneratingProgress', spectrogramProgress)
              : tracksProgress
                ? t('storage.regeneratingProgress', tracksProgress)
                : ''}
          </Typography>
          <LinearProgress
            variant="determinate"
            value={
              spectrogramProgress
                ? (spectrogramProgress.total > 0
                    ? (spectrogramProgress.processed / spectrogramProgress.total) * 100
                    : 0)
                : tracksProgress
                  ? (tracksProgress.total > 0
                      ? (tracksProgress.processed / tracksProgress.total) * 100
                      : 0)
                  : 0
            }
            sx={{ height: 8, borderRadius: 1 }}
          />
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
            ? (success as RetroExportResponse).skipped_no_bbox != null
              ? t('storage.retroExportSuccessWithNoBbox', {
                  saved: (success as RetroExportResponse).saved,
                  skipped: (success as RetroExportResponse).skipped,
                  skipped_no_bbox: (success as RetroExportResponse).skipped_no_bbox,
                })
              : t('storage.retroExportSuccess', {
                  saved: (success as RetroExportResponse).saved,
                  skipped: (success as RetroExportResponse).skipped,
                })
            : 'orphaned' in success
            ? t('storage.cleanOrphanedVisitsSuccess', {
                orphaned: (success as CleanOrphanedResponse).orphaned,
                synced: (success as CleanOrphanedResponse).synced,
              })
            : 'merged' in success
            ? t('storage.mergeSpeciesSuccess', { count: (success as MergeSpeciesResponse).merged })
            : 'generated' in success
            ? ('tracks' in success && success.tracks
                ? ('frames_updated' in success && success.frames_updated
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
                      }))
                : t('storage.regenerateSuccess', {
                    generated: success.generated,
                    failed: success.failed,
                    skipped: success.skipped,
                  }))
            : success.deletedSize > 0
            ? t('storage.deleted', { count: success.deletedCount, size: formatBytes(success.deletedSize) })
            : t('storage.imported', { count: success.deletedCount })}
        </Alert>
      )}

      <Stack spacing={3}>
        <Stack direction="row" spacing={3}>
          <Paper sx={{ p: 2, flex: 1 }}>
            <Stack direction="row" spacing={4}>
              <Box>
                <Typography variant="subtitle2" gutterBottom>
                  {t('storage.totalStorage')}
                </Typography>
                <Typography variant="h5">{formatBytes(totalSize)}</Typography>
              </Box>
              <Box>
                <Typography variant="subtitle2" gutterBottom>
                  {t('storage.totalFiles')}
                </Typography>
                <Typography variant="h5">{totalFiles}</Typography>
              </Box>
            </Stack>
          </Paper>

          <Paper id="recordings" sx={{ p: 2, flex: 1 }}>
            <Typography variant="h6" gutterBottom>
              {t('storage.recordings')}
            </Typography>
            <Stack direction="row" spacing={2} alignItems="center" sx={{ mb: 2 }} flexWrap="wrap">
              <Typography variant="body2" color="text.secondary">
                {t('storage.operationsPeriod')}:
              </Typography>
              <LocalizationProvider dateAdapter={AdapterDayjs}>
                <DatePicker
                  label={t('storage.periodFrom')}
                  value={operationsPeriod.start}
                  onChange={(v) => v && setOperationsPeriod((p) => ({ ...p, start: v }))}
                  maxDate={operationsPeriod.end}
                  slotProps={{ textField: { size: 'small', sx: { width: 140 } } }}
                />
                <DatePicker
                  label={t('storage.periodTo')}
                  value={operationsPeriod.end}
                  onChange={(v) => v && setOperationsPeriod((p) => ({ ...p, end: v }))}
                  minDate={operationsPeriod.start}
                  maxDate={dayjs()}
                  slotProps={{ textField: { size: 'small', sx: { width: 140 } } }}
                />
              </LocalizationProvider>
              <FormControlLabel
                control={
                  <Checkbox
                    checked={onlyManuallyCorrected}
                    onChange={(e) => setOnlyManuallyCorrected(e.target.checked)}
                    size="small"
                  />
                }
                label={t('storage.onlyManuallyCorrected')}
              />
            </Stack>
            <Stack direction="row" spacing={2} sx={{ mb: 2 }} flexWrap="wrap">
              <Button
                variant="outlined"
                disabled={scanMutation.isPending}
                onClick={() => scanMutation.mutate()}
                startIcon={<FolderOpenIcon />}
              >
                {scanMutation.isPending ? t('storage.scanning') : t('storage.scanImport')}
              </Button>
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
              >
                {regenerateMutation.isPending ? t('storage.regenerating') : t('storage.regenerateSpectrograms')}
              </Button>
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
              >
                {regenerateTracksMutation.isPending
                  ? (tracksProgress
                      ? t('storage.regeneratingProgress', tracksProgress)
                      : t('storage.regenerating'))
                  : t('storage.regenerateTracks')}
              </Button>
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
                    setError(e instanceof Error ? e.message : t('storage.datasetExportFailed'));
                  } finally {
                    setExportingDataset(false);
                  }
                }}
                startIcon={<DownloadIcon />}
              >
                {exportingDataset ? t('storage.exporting') : t('storage.exportDataset')}
              </Button>
              <Button
                variant="outlined"
                disabled={retroExporting}
                onClick={async () => {
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
                    );
                    setSuccess(result);
                    refetch();
                  } catch (e) {
                    setError(e instanceof Error ? e.message : t('storage.retroExportFailed'));
                  } finally {
                    setRetroExporting(false);
                  }
                }}
                startIcon={<FolderOpenIcon />}
                title={t('storage.retroExportHint')}
              >
                {retroExporting ? t('storage.retroExporting') : t('storage.retroExport')}
              </Button>
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
              >
                {cleanOrphanedMutation.isPending ? t('storage.merging') : t('storage.cleanOrphanedVisits')}
              </Button>
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
              >
                {mergeSpeciesMutation.isPending ? t('storage.merging') : t('storage.mergeDuplicateSpecies')}
              </Button>
              <Typography variant="body2" color="text.secondary" sx={{ alignSelf: 'center' }}>
                {t('storage.scanHint')}
              </Typography>
            </Stack>
            <Typography variant="subtitle2" gutterBottom>
              {t('storage.purgeOld')}
            </Typography>
            <Stack direction="row" spacing={2}>
              <LocalizationProvider dateAdapter={AdapterDayjs}>
                <DatePicker
                  label={t('storage.deleteBeforeDate')}
                  value={selectedDate}
                  onChange={(newValue: Dayjs | null) =>
                    setSelectedDate(newValue)
                  }
                  maxDate={dayjs()}
                  slotProps={{
                    textField: { size: 'small', sx: { flex: 1 } },
                  }}
                />
              </LocalizationProvider>
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
          </Paper>
        </Stack>

        <Paper sx={{ p: 2 }}>
          <Typography variant="h6" gutterBottom>
            {t('storage.usageOverTime')}
          </Typography>
          {chartData.length > 0 ? (
            <Box sx={{ width: '100%', height: 400 }}>
              <BarChart
                dataset={chartData}
                series={[
                  {
                    dataKey: 'size',
                    label: 'Storage (MB)',
                    color: '#2dd4bf',
                    valueFormatter: (value) => `${value} MB`,
                  },
                ]}
                xAxis={[
                  {
                    dataKey: 'date',
                    scaleType: 'band',
                  },
                ]}
                yAxis={[
                  {
                    label: 'Storage (MB)',
                  },
                ]}
                height={350}
              />
            </Box>
          ) : (
            <Typography color="text.secondary">
              {t('storage.noStorageData')}
            </Typography>
          )}
        </Paper>
      </Stack>
    </Box>

    </>
  );
};
