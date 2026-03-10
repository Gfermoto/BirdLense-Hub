import { useState, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import axios from 'axios';
import Box from '@mui/material/Box';
import Paper from '@mui/material/Paper';
import Typography from '@mui/material/Typography';
import Button from '@mui/material/Button';
import Stack from '@mui/material/Stack';
import Alert from '@mui/material/Alert';
import AlertTitle from '@mui/material/AlertTitle';
import { DatePicker } from '@mui/x-date-pickers/DatePicker';
import { LocalizationProvider } from '@mui/x-date-pickers/LocalizationProvider';
import { AdapterDayjs } from '@mui/x-date-pickers/AdapterDayjs';
import { BarChart } from '@mui/x-charts/BarChart';
import dayjs, { Dayjs } from 'dayjs';
import DeleteOutlineIcon from '@mui/icons-material/DeleteOutline';
import FolderOpenIcon from '@mui/icons-material/FolderOpen';
import GraphicEqIcon from '@mui/icons-material/GraphicEq';
import RouteIcon from '@mui/icons-material/Route';
import { BASE_API_URL } from '../../api/api';

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

const formatBytes = (bytes: number): string => {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(2))} ${sizes[i]}`;
};

export const StorageManagement = () => {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [selectedDate, setSelectedDate] = useState<Dayjs | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<PurgeResponse | RegenerateSpectrogramsResponse | null>(null);

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

  const pollRegenerateStatus = useCallback(async (): Promise<RegenerateSpectrogramsResponse | null> => {
    const { data } = await axios.get<{ status: string; result: RegenerateSpectrogramsResponse | null; error: string | null }>(
      `${BASE_API_URL}/system/regenerate-spectrograms/status`,
    );
    if (data.status === 'done' && data.result) {
      return data.result;
    }
    if (data.status === 'done' && data.error) {
      throw new Error(data.error);
    }
    return null;
  }, []);

  const pollRegenerateTracksStatus = useCallback(async (): Promise<RegenerateSpectrogramsResponse | null> => {
    const { data } = await axios.get<{ status: string; result: RegenerateSpectrogramsResponse | null; error: string | null }>(
      `${BASE_API_URL}/system/regenerate-tracks/status`,
    );
    if (data.status === 'done' && data.result) {
      return data.result;
    }
    if (data.status === 'done' && data.error) {
      throw new Error(data.error);
    }
    return null;
  }, []);

  const regenerateMutation = useMutation<
    RegenerateSpectrogramsResponse,
    Error,
    { force?: boolean }
  >({
    mutationFn: async (params) => {
      await axios.post(`${BASE_API_URL}/system/regenerate-spectrograms`, params || {});
      for (let i = 0; i < 120; i++) {
        await new Promise((r) => setTimeout(r, 2000));
        const result = await pollRegenerateStatus();
        if (result) return result;
      }
      throw new Error(t('storage.regenerateTimeout'));
    },
    onSuccess: (data) => {
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
    onError: (err) => {
      setError(
        err instanceof Error ? err.message : t('storage.regenerateFailed'),
      );
    },
  });

  const regenerateTracksMutation = useMutation<
    RegenerateSpectrogramsResponse,
    Error,
    { force?: boolean }
  >({
    mutationFn: async (params) => {
      await axios.post(`${BASE_API_URL}/system/regenerate-tracks`, params || {});
      for (let i = 0; i < 180; i++) {
        await new Promise((r) => setTimeout(r, 2000));
        const result = await pollRegenerateTracksStatus();
        if (result) return result;
      }
      throw new Error(t('storage.regenerateTimeout'));
    },
    onSuccess: (data) => {
      setSuccess({
        message: data.message || '',
        generated: data.generated,
        failed: data.failed,
        skipped: data.skipped,
        tracks: true,
      });
      refetch();
      queryClient.invalidateQueries({ queryKey: ['videos'] });
      queryClient.invalidateQueries({ queryKey: ['speciesVisits'] });
      setTimeout(() => setSuccess(null), 8000);
    },
    onError: (err) => {
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

      {success && (
        <Alert
          severity="success"
          sx={{ mb: 2 }}
          onClose={() => setSuccess(null)}
        >
          <AlertTitle>{t('common.success')}</AlertTitle>
          {'generated' in success
            ? ('tracks' in success && success.tracks
                ? t('storage.regenerateTracksSuccess', {
                    generated: success.generated,
                    failed: success.failed,
                    skipped: success.skipped,
                  })
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
                onClick={() => regenerateMutation.mutate({})}
                startIcon={<GraphicEqIcon />}
              >
                {regenerateMutation.isPending ? t('storage.regenerating') : t('storage.regenerateSpectrograms')}
              </Button>
              <Button
                variant="outlined"
                disabled={regenerateTracksMutation.isPending}
                onClick={() => regenerateTracksMutation.mutate({})}
                startIcon={<RouteIcon />}
              >
                {regenerateTracksMutation.isPending ? t('storage.regenerating') : t('storage.regenerateTracks')}
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
  );
};
