import { useTranslation } from 'react-i18next';
import { useRef, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import axios from 'axios';
import Box from '@mui/material/Box';
import Paper from '@mui/material/Paper';
import Typography from '@mui/material/Typography';
import Alert from '@mui/material/Alert';
import Button from '@mui/material/Button';
import Stack from '@mui/material/Stack';
import ToggleButton from '@mui/material/ToggleButton';
import ToggleButtonGroup from '@mui/material/ToggleButtonGroup';
import { BarChart } from '@mui/x-charts/BarChart';
import dayjs, { type Dayjs } from 'dayjs';
import { AdapterDayjs } from '@mui/x-date-pickers/AdapterDayjs';
import { LocalizationProvider } from '@mui/x-date-pickers/LocalizationProvider';
import { DatePicker } from '@mui/x-date-pickers/DatePicker';
import { BASE_API_URL } from '../../api/client';
import {
  downloadDbBackup,
  purgeStorageRecordings,
  restoreDbBackup,
} from '../../api/settingsYamlDb';
import { queryKeys } from '../../api/queryKeys';
import { ConfirmDialog } from '../../components/ConfirmDialog';
import { useProtectedArea } from '../../contexts/ProtectedAreaContext';
import { RecordingsNasMirrorCard } from './RecordingsNasMirrorCard';

type PurgeMode = 'before' | 'range';

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

export const StorageOverview = ({ simple = false }: { simple?: boolean }) => {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const { isAdmin } = useProtectedArea();
  const restoreInputRef = useRef<HTMLInputElement | null>(null);
  const [dbMessage, setDbMessage] = useState<string>('');
  const [dbError, setDbError] = useState<string>('');
  const [isDownloadingDb, setIsDownloadingDb] = useState(false);
  const [isRestoringDb, setIsRestoringDb] = useState(false);
  const [pendingRestoreFile, setPendingRestoreFile] = useState<File | null>(
    null,
  );
  const [purgeMode, setPurgeMode] = useState<PurgeMode>('before');
  const [purgeBeforeDate, setPurgeBeforeDate] = useState<Dayjs | null>(() =>
    dayjs().subtract(30, 'day').startOf('day'),
  );
  const [purgeRangeFrom, setPurgeRangeFrom] = useState<Dayjs | null>(() =>
    dayjs().subtract(14, 'day').startOf('day'),
  );
  const [purgeRangeTo, setPurgeRangeTo] = useState<Dayjs | null>(() =>
    dayjs().subtract(7, 'day').startOf('day'),
  );
  const [purgeConfirmOpen, setPurgeConfirmOpen] = useState(false);
  const [purgeRunning, setPurgeRunning] = useState(false);
  const [purgeMessage, setPurgeMessage] = useState<string | null>(null);
  const [purgeError, setPurgeError] = useState<string | null>(null);
  const { data: storageStats, isLoading } = useQuery<StorageStats[]>({
    queryKey: queryKeys.storage.stats,
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
  const validStorageStats = (
    Array.isArray(storageStats) ? storageStats : []
  ).filter(
    (stat): stat is StorageStats =>
      typeof stat?.date === 'string' &&
      typeof stat?.fileCount === 'number' &&
      Number.isFinite(stat.fileCount) &&
      typeof stat?.totalSize === 'number' &&
      Number.isFinite(stat.totalSize),
  );

  const chartData: ChartDataPoint[] = validStorageStats.map((stat) => ({
    date: dayjs(stat.date).format('MM/DD'),
    size: Number((stat.totalSize / (1024 * 1024)).toFixed(2)),
  }));
  const totalSize =
    validStorageStats.reduce((acc, stat) => acc + stat.totalSize, 0) || 0;
  const totalFiles =
    validStorageStats.reduce((acc, stat) => acc + stat.fileCount, 0) || 0;

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

  const handleRestoreFile = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = '';
    if (!file) return;
    setPendingRestoreFile(file);
  };

  const handleRestoreConfirmed = async () => {
    if (!pendingRestoreFile) return;
    const file = pendingRestoreFile;
    setPendingRestoreFile(null);
    setDbError('');
    setDbMessage('');
    setIsRestoringDb(true);
    try {
      const result = await restoreDbBackup(file);
      setDbMessage(result.message || t('storage.dbRestoreDone'));
      await queryClient.invalidateQueries();
    } catch (e) {
      const msg = e instanceof Error ? e.message : t('storage.dbRestoreFailed');
      setDbError(msg);
    } finally {
      setIsRestoringDb(false);
    }
  };

  const purgeRangeValid =
    !!purgeRangeFrom &&
    !!purgeRangeTo &&
    (purgeRangeFrom.isBefore(purgeRangeTo, 'day') ||
      purgeRangeFrom.isSame(purgeRangeTo, 'day'));
  const canStartPurgeDialog =
    purgeMode === 'before' ? !!purgeBeforeDate : purgeRangeValid;

  const handlePurgeConfirmed = async () => {
    setPurgeError(null);
    setPurgeMessage(null);
    setPurgeRunning(true);
    try {
      const body =
        purgeMode === 'before' && purgeBeforeDate
          ? { date: purgeBeforeDate.format('YYYY-MM-DD') }
          : purgeRangeFrom && purgeRangeTo
            ? {
                start_date: purgeRangeFrom.format('YYYY-MM-DD'),
                end_date: purgeRangeTo.format('YYYY-MM-DD'),
              }
            : null;
      if (!body) {
        setPurgeError(t('storage.purgeFailed'));
        return;
      }
      const res = await purgeStorageRecordings(body);
      setPurgeConfirmOpen(false);
      setPurgeMessage(
        t('storage.deleted', {
          count: res.deletedCount,
          size: formatBytes(res.deletedSize),
        }),
      );
      await queryClient.invalidateQueries({
        queryKey: queryKeys.storage.stats,
      });
    } catch (e: unknown) {
      const err = e as {
        response?: { data?: { error?: string } };
        message?: string;
      };
      setPurgeError(
        err.response?.data?.error || err.message || t('storage.purgeFailed'),
      );
    } finally {
      setPurgeRunning(false);
    }
  };

  return (
    <Box>
      <Typography component="h3" variant="h5" sx={{ mb: 3 }}>
        {t('system.storage')}
      </Typography>
      <Box sx={{ display: 'flex', gap: 3, flexWrap: 'wrap', mb: 3 }}>
        <Paper sx={{ p: 2, flex: 1, minWidth: 160 }}>
          <Typography component="p" variant="subtitle2" gutterBottom>
            {t('storage.totalStorage')}
          </Typography>
          <Typography component="p" variant="h5">
            {formatBytes(totalSize)}
          </Typography>
        </Paper>
        <Paper sx={{ p: 2, flex: 1, minWidth: 160 }}>
          <Typography component="p" variant="subtitle2" gutterBottom>
            {t('storage.totalFiles')}
          </Typography>
          <Typography component="p" variant="h5">
            {totalFiles}
          </Typography>
        </Paper>
      </Box>
      <Paper sx={{ p: 2 }}>
        <Typography component="h4" variant="h6" gutterBottom>
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
      {isAdmin ? (
        <Box sx={{ mt: 2 }}>
          <RecordingsNasMirrorCard enabled />
        </Box>
      ) : null}
      {!simple ? (
        <>
          <Paper sx={{ p: 2, mt: 2 }}>
            <Typography component="h4" variant="h6" gutterBottom>
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
                {isDownloadingDb
                  ? t('storage.dbBackingUp')
                  : t('storage.dbBackupAction')}
              </Button>
              <Button
                color="warning"
                variant="outlined"
                onClick={handleRestorePick}
                disabled={isDownloadingDb || isRestoringDb}
              >
                {isRestoringDb
                  ? t('storage.dbRestoring')
                  : t('storage.dbRestoreAction')}
              </Button>
              <input
                ref={restoreInputRef}
                type="file"
                accept=".db,.sqlite,.sqlite3,application/octet-stream"
                style={{ display: 'none' }}
                onChange={handleRestoreFile}
              />
            </Stack>
            {dbMessage && (
              <Alert severity="success" variant="outlined" sx={{ mt: 2 }}>
                {dbMessage}
              </Alert>
            )}
            {dbError && (
              <Alert severity="error" variant="outlined" sx={{ mt: 2 }}>
                {dbError}
              </Alert>
            )}
          </Paper>

          {isAdmin && (
            <Paper sx={{ p: 2, mt: 2 }}>
              <Typography component="h4" variant="h6" gutterBottom>
                {t('storage.purgeOld')}
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                {t('storage.purgeHint')}
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                {t('storage.purgeSkipsFavorites')}
              </Typography>
              <ToggleButtonGroup
                value={purgeMode}
                exclusive
                onChange={(_, value: PurgeMode | null) => {
                  if (value) setPurgeMode(value);
                }}
                size="small"
                sx={{ mb: 2 }}
              >
                <ToggleButton value="before">
                  {t('storage.purgeModeBefore')}
                </ToggleButton>
                <ToggleButton value="range">
                  {t('storage.purgeModeRange')}
                </ToggleButton>
              </ToggleButtonGroup>
              <LocalizationProvider dateAdapter={AdapterDayjs}>
                <Stack
                  direction={{ xs: 'column', sm: 'row' }}
                  spacing={2}
                  alignItems={{ xs: 'stretch', sm: 'center' }}
                  sx={{ mb: 2 }}
                >
                  {purgeMode === 'before' ? (
                    <DatePicker
                      label={t('storage.deleteBeforeDate')}
                      value={purgeBeforeDate}
                      onChange={(v) => setPurgeBeforeDate(v)}
                      maxDate={dayjs()}
                      slotProps={{ textField: { size: 'small' } }}
                    />
                  ) : (
                    <>
                      <DatePicker
                        label={t('storage.periodFrom')}
                        value={purgeRangeFrom}
                        onChange={(v) => setPurgeRangeFrom(v)}
                        maxDate={purgeRangeTo ?? dayjs()}
                        slotProps={{ textField: { size: 'small' } }}
                      />
                      <DatePicker
                        label={t('storage.periodTo')}
                        value={purgeRangeTo}
                        onChange={(v) => setPurgeRangeTo(v)}
                        minDate={purgeRangeFrom ?? undefined}
                        maxDate={dayjs()}
                        slotProps={{ textField: { size: 'small' } }}
                      />
                    </>
                  )}
                </Stack>
              </LocalizationProvider>
              <Button
                color="error"
                variant="outlined"
                disabled={!canStartPurgeDialog || purgeRunning}
                onClick={() => {
                  setPurgeError(null);
                  setPurgeConfirmOpen(true);
                }}
              >
                {t('storage.purge')}
              </Button>
              {purgeMessage && (
                <Alert severity="success" variant="outlined" sx={{ mt: 2 }}>
                  {purgeMessage}
                </Alert>
              )}
              {purgeError && (
                <Alert severity="error" variant="outlined" sx={{ mt: 2 }}>
                  {purgeError}
                </Alert>
              )}
            </Paper>
          )}
        </>
      ) : null}

      {!simple ? (
        <>
          <ConfirmDialog
            open={pendingRestoreFile !== null}
            title={t('storage.dbRestoreTitle')}
            description={t('storage.dbRestoreConfirm', {
              name: pendingRestoreFile?.name ?? '',
            })}
            confirmLabel={t('storage.dbRestoreAction')}
            cancelLabel={t('common.cancel')}
            confirmColor="error"
            onConfirm={handleRestoreConfirmed}
            onCancel={() => setPendingRestoreFile(null)}
          />

          <ConfirmDialog
            open={purgeConfirmOpen}
            title={t('storage.purgeOld')}
            description={
              purgeMode === 'before' && purgeBeforeDate
                ? t('storage.purgeConfirm', {
                    date: purgeBeforeDate.format('YYYY-MM-DD'),
                  })
                : purgeRangeFrom && purgeRangeTo
                  ? t('storage.purgeConfirmRange', {
                      start: purgeRangeFrom.format('YYYY-MM-DD'),
                      end: purgeRangeTo.format('YYYY-MM-DD'),
                    })
                  : ''
            }
            confirmLabel={t('storage.purge')}
            cancelLabel={t('common.cancel')}
            confirmColor="error"
            onConfirm={() => void handlePurgeConfirmed()}
            onCancel={() => setPurgeConfirmOpen(false)}
          />
        </>
      ) : null}
    </Box>
  );
};
