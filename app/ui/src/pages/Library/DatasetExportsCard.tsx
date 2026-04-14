import { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useQuery } from '@tanstack/react-query';
import axios from 'axios';
import Alert from '@mui/material/Alert';
import AlertTitle from '@mui/material/AlertTitle';
import Button from '@mui/material/Button';
import Checkbox from '@mui/material/Checkbox';
import FormControlLabel from '@mui/material/FormControlLabel';
import LinearProgress from '@mui/material/LinearProgress';
import Paper from '@mui/material/Paper';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';
import DownloadIcon from '@mui/icons-material/Download';
import FolderOpenIcon from '@mui/icons-material/FolderOpen';
import { DatePicker } from '@mui/x-date-pickers/DatePicker';
import { LocalizationProvider } from '@mui/x-date-pickers/LocalizationProvider';
import { AdapterDayjs } from '@mui/x-date-pickers/AdapterDayjs';
import dayjs, { Dayjs } from 'dayjs';
import { BASE_API_URL, exportDataset, retroExportDataset } from '../../api/api';

interface StorageDay {
  date: string;
  fileCount: number;
  totalSize: number;
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

export function DatasetExportsCard({
  simple = false,
}: {
  simple?: boolean;
}) {
  const { t } = useTranslation();
  const [exportingDataset, setExportingDataset] = useState(false);
  const [retroExporting, setRetroExporting] = useState(false);
  const [readyForTrain, setReadyForTrain] = useState(true);
  const [includeTestSplit, setIncludeTestSplit] = useState(false);
  const [strictQualityExport, setStrictQualityExport] = useState(false);
  const [onlyManuallyCorrected, setOnlyManuallyCorrected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [operationsPeriod, setOperationsPeriod] = useState<{
    start: Dayjs;
    end: Dayjs;
  }>(() => ({
    start: dayjs().subtract(1, 'week'),
    end: dayjs(),
  }));

  const { data: storageStats = [] } = useQuery<StorageDay[]>({
    queryKey: ['storageStats'],
    queryFn: async () => {
      const { data } = await axios.get<StorageDay[]>(
        `${BASE_API_URL}/storage/stats`,
      );
      return data;
    },
  });
  const validStorageStats = useMemo(() => {
    const rows = Array.isArray(storageStats) ? storageStats : [];
    return rows.filter(
      (item): item is StorageDay =>
        typeof item?.date === 'string' &&
        typeof item?.fileCount === 'number' &&
        Number.isFinite(item.fileCount) &&
        typeof item?.totalSize === 'number' &&
        Number.isFinite(item.totalSize),
    );
  }, [storageStats]);

  const storageRange = useMemo(() => {
    if (!validStorageStats.length) return null;
    const sorted = [...validStorageStats].sort((a, b) =>
      a.date.localeCompare(b.date),
    );
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
  }, [validStorageStats]);

  const applyPreset = (preset: 'last7' | 'last30' | 'all') => {
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
    const boundedStart =
      storageRange && rawStart.isBefore(storageRange.start)
        ? storageRange.start
        : rawStart;
    setOperationsPeriod({
      start: boundedStart,
      end: today,
    });
  };

  const handleExportDataset = async () => {
    setExportingDataset(true);
    setError(null);
    setSuccess(null);
    try {
      await exportDataset({
        start_date: operationsPeriod.start.format('YYYY-MM-DD'),
        end_date: operationsPeriod.end.format('YYYY-MM-DD'),
        only_manually_corrected: onlyManuallyCorrected,
        ready_for_train: readyForTrain,
        test_ratio: readyForTrain && includeTestSplit ? 0.1 : undefined,
        strict_quality: readyForTrain && strictQualityExport ? true : undefined,
      });
      setSuccess(t('library.datasetExportStarted'));
    } catch (e) {
      setError(
        e instanceof Error ? e.message : t('storage.datasetExportFailed'),
      );
    } finally {
      setExportingDataset(false);
    }
  };

  const handleRetroExport = async () => {
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
        false,
      );
      setSuccess(
        result.skipped_no_bbox != null
          ? t('storage.retroExportSuccessWithNoBbox', {
              saved: result.saved,
              skipped: result.skipped,
              skipped_no_bbox: result.skipped_no_bbox,
            })
          : t('storage.retroExportSuccess', {
              saved: result.saved,
              skipped: result.skipped,
            }),
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : t('storage.retroExportFailed'));
    } finally {
      setRetroExporting(false);
    }
  };

  return (
    <LocalizationProvider dateAdapter={AdapterDayjs}>
      <Paper sx={{ p: 2.5 }}>
        <Stack spacing={2.5}>
          <div>
            <Typography variant="h5">
              {t('library.datasetToolsTitle')}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              {t('library.datasetToolsSubtitle')}
            </Typography>
          </div>

          {error && (
            <Alert severity="error" onClose={() => setError(null)}>
              <AlertTitle>{t('common.error')}</AlertTitle>
              {error}
            </Alert>
          )}

          {success && (
            <Alert severity="success" onClose={() => setSuccess(null)}>
              <AlertTitle>{t('common.success')}</AlertTitle>
              {success}
            </Alert>
          )}

          <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
            <Button
              size="small"
              variant="outlined"
              onClick={() => applyPreset('last7')}
            >
              {t('storage.presetLast7Days')}
            </Button>
            <Button
              size="small"
              variant="outlined"
              onClick={() => applyPreset('last30')}
            >
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

          <Stack
            direction={{ xs: 'column', md: 'row' }}
            spacing={2}
            alignItems={{ md: 'center' }}
          >
            <DatePicker
              label={t('storage.periodFrom')}
              value={operationsPeriod.start}
              onChange={(value) =>
                value &&
                setOperationsPeriod((period) => ({ ...period, start: value }))
              }
              minDate={storageRange?.start}
              maxDate={operationsPeriod.end}
              slotProps={{ textField: { size: 'small', sx: { width: 180 } } }}
            />
            <DatePicker
              label={t('storage.periodTo')}
              value={operationsPeriod.end}
              onChange={(value) =>
                value &&
                setOperationsPeriod((period) => ({ ...period, end: value }))
              }
              minDate={operationsPeriod.start}
              maxDate={storageRange?.end || dayjs()}
              slotProps={{ textField: { size: 'small', sx: { width: 180 } } }}
            />
            <FormControlLabel
              control={
                <Checkbox
                  checked={onlyManuallyCorrected}
                  onChange={(event) =>
                    setOnlyManuallyCorrected(event.target.checked)
                  }
                  size="small"
                />
              }
              label={t('storage.onlyManuallyCorrected')}
            />
          </Stack>

          <Typography variant="caption" color="text.secondary">
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

          <Stack spacing={1}>
            <Button
              variant="outlined"
              disabled={exportingDataset || !storageRange}
              onClick={handleExportDataset}
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

            {!simple ? (
              <>
                <FormControlLabel
                  control={
                    <Checkbox
                      checked={readyForTrain}
                      onChange={(event) => setReadyForTrain(event.target.checked)}
                      size="small"
                    />
                  }
                  label={t('storage.readyForTrain')}
                />
                <FormControlLabel
                  control={
                    <Checkbox
                      checked={includeTestSplit}
                      onChange={(event) =>
                        setIncludeTestSplit(event.target.checked)
                      }
                      disabled={!readyForTrain}
                      size="small"
                    />
                  }
                  label={t('storage.includeTestSplit')}
                />
                <FormControlLabel
                  control={
                    <Checkbox
                      checked={strictQualityExport}
                      onChange={(event) =>
                        setStrictQualityExport(event.target.checked)
                      }
                      disabled={!readyForTrain}
                      size="small"
                    />
                  }
                  label={t('storage.strictQualityExport')}
                />
              </>
            ) : null}
          </Stack>

          {!simple ? (
            <Stack spacing={1}>
              <Button
                variant="outlined"
                disabled={retroExporting || !storageRange}
                onClick={handleRetroExport}
                startIcon={<FolderOpenIcon />}
                fullWidth
              >
                {retroExporting
                  ? t('storage.retroExporting')
                  : t('storage.retroExport')}
              </Button>
              {retroExporting && (
                <LinearProgress sx={{ height: 4, borderRadius: 2 }} />
              )}
            </Stack>
          ) : null}

          <Alert severity="info">{t('library.datasetToolsLibraryHint')}</Alert>
        </Stack>
      </Paper>
    </LocalizationProvider>
  );
}
