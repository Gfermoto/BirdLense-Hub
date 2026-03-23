import { useTranslation } from 'react-i18next';
import { useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import axios from 'axios';
import Box from '@mui/material/Box';
import Paper from '@mui/material/Paper';
import Typography from '@mui/material/Typography';
import Alert from '@mui/material/Alert';
import Button from '@mui/material/Button';
import Stack from '@mui/material/Stack';
import { BarChart } from '@mui/x-charts/BarChart';
import dayjs from 'dayjs';
import { BASE_API_URL, downloadDbBackup, restoreDbBackup } from '../../api/api';

interface StorageStats {
  date: string;
  fileCount: number;
  totalSize: number;
}

interface ChartDataPoint {
  [key: string]: string | number;
  date: string;
  size: number;
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

export const StorageOverview = () => {
  const { t } = useTranslation();
  const restoreInputRef = useRef<HTMLInputElement | null>(null);
  const [dbMessage, setDbMessage] = useState<string>('');
  const [dbError, setDbError] = useState<string>('');
  const [isDownloadingDb, setIsDownloadingDb] = useState(false);
  const [isRestoringDb, setIsRestoringDb] = useState(false);
  const { data: storageStats, isLoading } = useQuery<StorageStats[]>({
    queryKey: ['storageStats'],
    queryFn: async () => {
      const { data } = await axios.get<StorageStats[]>(
        `${BASE_API_URL}/storage/stats`,
      );
      return data;
    },
  });

  if (isLoading) {
    return <Typography>{t('storage.loadingStats')}</Typography>;
  }

  const chartData: ChartDataPoint[] =
    storageStats?.map((stat) => ({
      date: dayjs(stat.date).format('MM/DD'),
      size: Number((stat.totalSize / (1024 * 1024)).toFixed(2)),
    })) || [];
  const totalSize =
    storageStats?.reduce((acc, stat) => acc + stat.totalSize, 0) || 0;
  const totalFiles =
    storageStats?.reduce((acc, stat) => acc + stat.fileCount, 0) || 0;

  const handleDownloadDb = async () => {
    setDbError('');
    setDbMessage('');
    setIsDownloadingDb(true);
    try {
      await downloadDbBackup();
      setDbMessage(t('storage.dbBackupDone'));
    } catch (e) {
      const msg = e instanceof Error ? e.message : t('storage.dbBackupFailed');
      setDbError(msg);
    } finally {
      setIsDownloadingDb(false);
    }
  };

  const handleRestorePick = () => {
    restoreInputRef.current?.click();
  };

  const handleRestoreFile = async (
    event: React.ChangeEvent<HTMLInputElement>,
  ) => {
    const file = event.target.files?.[0];
    event.target.value = '';
    if (!file) return;
    if (!window.confirm(t('storage.dbRestoreConfirm'))) return;
    setDbError('');
    setDbMessage('');
    setIsRestoringDb(true);
    try {
      const result = await restoreDbBackup(file);
      setDbMessage(result.message || t('storage.dbRestoreDone'));
    } catch (e) {
      const msg = e instanceof Error ? e.message : t('storage.dbRestoreFailed');
      setDbError(msg);
    } finally {
      setIsRestoringDb(false);
    }
  };

  return (
    <Box>
      <Typography variant="h5" sx={{ mb: 3 }}>
        {t('system.storage')}
      </Typography>
      <Box sx={{ display: 'flex', gap: 3, flexWrap: 'wrap', mb: 3 }}>
        <Paper sx={{ p: 2, flex: 1, minWidth: 160 }}>
          <Typography variant="subtitle2" gutterBottom>
            {t('storage.totalStorage')}
          </Typography>
          <Typography variant="h5">{formatBytes(totalSize)}</Typography>
        </Paper>
        <Paper sx={{ p: 2, flex: 1, minWidth: 160 }}>
          <Typography variant="subtitle2" gutterBottom>
            {t('storage.totalFiles')}
          </Typography>
          <Typography variant="h5">{totalFiles}</Typography>
        </Paper>
      </Box>
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
                  label: t('storage.storageMb'),
                  color: '#2dd4bf',
                  valueFormatter: (value) => `${value} MB`,
                },
              ]}
              xAxis={[{ dataKey: 'date', scaleType: 'band' }]}
              yAxis={[{ label: t('storage.storageMb') }]}
              height={350}
            />
          </Box>
        ) : (
          <Typography color="text.secondary">
            {t('storage.noStorageData')}
          </Typography>
        )}
      </Paper>
      <Paper sx={{ p: 2, mt: 2 }}>
        <Typography variant="h6" gutterBottom>
          {t('storage.dbBackupRestore')}
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          {t('storage.dbBackupRestoreHint')}
        </Typography>
        <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.5}>
          <Button
            variant="outlined"
            onClick={handleDownloadDb}
            disabled={isDownloadingDb || isRestoringDb}
          >
            {isDownloadingDb ? t('storage.dbBackingUp') : t('storage.dbBackupAction')}
          </Button>
          <Button
            color="warning"
            variant="outlined"
            onClick={handleRestorePick}
            disabled={isDownloadingDb || isRestoringDb}
          >
            {isRestoringDb ? t('storage.dbRestoring') : t('storage.dbRestoreAction')}
          </Button>
          <input
            ref={restoreInputRef}
            type="file"
            accept=".db,.sqlite,.sqlite3,application/octet-stream"
            style={{ display: 'none' }}
            onChange={handleRestoreFile}
          />
        </Stack>
        {dbMessage && <Alert severity="success" sx={{ mt: 2 }}>{dbMessage}</Alert>}
        {dbError && <Alert severity="error" sx={{ mt: 2 }}>{dbError}</Alert>}
      </Paper>
    </Box>
  );
};
