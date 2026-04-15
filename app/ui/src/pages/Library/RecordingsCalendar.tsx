import { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import axios from 'axios';
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Chip from '@mui/material/Chip';
import Paper from '@mui/material/Paper';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';
import IconButton from '@mui/material/IconButton';
import ChevronLeft from '@mui/icons-material/ChevronLeft';
import ChevronRight from '@mui/icons-material/ChevronRight';
import { LocalizationProvider } from '@mui/x-date-pickers/LocalizationProvider';
import { AdapterDayjs } from '@mui/x-date-pickers/AdapterDayjs';
import { StaticDatePicker } from '@mui/x-date-pickers/StaticDatePicker';
import { PickersDay, PickersDayProps } from '@mui/x-date-pickers/PickersDay';
import dayjs, { Dayjs } from 'dayjs';
import { BASE_API_URL } from '../../api/api';

interface StorageDay {
  date: string;
  fileCount: number;
  totalSize: number;
}

interface Level {
  minFiles: number;
  color: string;
  label: string;
}

const defaultColor = '#f5f5f5';

const getLevels = (
  t: (key: string, opts?: Record<string, unknown>) => string,
): readonly Level[] => [
  { minFiles: 16, color: '#2e7d32', label: t('library.recordingsLevelHigh') },
  { minFiles: 8, color: '#43a047', label: t('library.recordingsLevelMedium') },
  { minFiles: 1, color: '#81c784', label: t('library.recordingsLevelLow') },
];

function getDayColor(fileCount: number, levels: readonly Level[]): string {
  return (
    levels.find((level) => fileCount >= level.minFiles)?.color ?? defaultColor
  );
}

function CalendarDay({
  day,
  days,
  levels,
  onOpenDay,
  ...other
}: PickersDayProps<Dayjs> & {
  days: StorageDay[];
  levels: readonly Level[];
  onOpenDay: (date: string) => void;
}) {
  const formattedDate = day.format('YYYY-MM-DD');
  const info = days.find((item) => item.date === formattedDate);
  const fileCount = info?.fileCount ?? 0;
  const bgColor = getDayColor(fileCount, levels);

  return (
    <PickersDay
      {...other}
      day={day}
      title={fileCount > 0 ? `${formattedDate}: ${fileCount}` : formattedDate}
      onClick={(e) => {
        other.onClick?.(e);
        if (fileCount > 0) onOpenDay(formattedDate);
      }}
      sx={{
        bgcolor: bgColor,
        '&:hover': { bgcolor: bgColor },
        '&.Mui-selected': {
          bgcolor: 'grey.700',
          '&:hover': { bgcolor: 'grey.700' },
        },
        color: fileCount >= 8 ? 'white' : 'black',
        fontWeight: fileCount > 0 ? 600 : 400,
      }}
    />
  );
}

export function RecordingsCalendar() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [selectedMonth, setSelectedMonth] = useState<Dayjs>(() =>
    dayjs().startOf('month'),
  );
  const levels = getLevels(t);
  const {
    data: storageStats = [],
    isLoading,
    isError,
  } = useQuery<StorageDay[]>({
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

  const statsRange = useMemo(() => {
    if (validStorageStats.length === 0) return null;
    const sorted = [...validStorageStats].sort((a, b) =>
      a.date.localeCompare(b.date),
    );
    return {
      first: sorted[0]?.date ?? null,
      last: sorted[sorted.length - 1]?.date ?? null,
    };
  }, [validStorageStats]);

  const monthPrefix = selectedMonth.format('YYYY-MM-');
  const monthStats = useMemo(
    () => validStorageStats.filter((item) => item.date.startsWith(monthPrefix)),
    [validStorageStats, monthPrefix],
  );
  const recordedDays = monthStats.length;
  const totalFiles = monthStats.reduce((sum, item) => sum + item.fileCount, 0);

  const earliestMonth = statsRange?.first
    ? dayjs(statsRange.first).startOf('month')
    : dayjs('2020-01-01');
  const latestMonth = statsRange?.last
    ? dayjs(statsRange.last).startOf('month')
    : dayjs();
  const canGoPrev = selectedMonth.isAfter(earliestMonth, 'month');
  const canGoNext = selectedMonth.isBefore(latestMonth, 'month');

  return (
    <Stack spacing={2}>
      <Paper sx={{ p: 2.5 }}>
        <Stack
          direction={{ xs: 'column', md: 'row' }}
          alignItems={{ xs: 'flex-start', md: 'center' }}
          justifyContent="space-between"
          spacing={2}
          sx={{ mb: 2 }}
        >
          <Box>
            <Typography variant="h5">
              {t('library.recordingsCalendarTitle')}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              {t('library.recordingsCalendarSubtitle')}
            </Typography>
          </Box>
          <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
            <Chip
              size="small"
              color="success"
              label={t('library.recordingsDaysChip', { count: recordedDays })}
            />
            <Chip
              size="small"
              variant="outlined"
              label={t('library.recordingsFilesChip', { count: totalFiles })}
            />
          </Stack>
        </Stack>

        {isLoading ? (
          <Typography color="text.secondary">
            {t('library.recordingsLoading')}
          </Typography>
        ) : isError ? (
          <Alert severity="error">{t('library.recordingsLoadFailed')}</Alert>
        ) : validStorageStats.length === 0 ? (
          <Alert severity="info">{t('library.recordingsEmptyHint')}</Alert>
        ) : (
          <>
            <Box
              display="flex"
              alignItems="center"
              justifyContent="space-between"
              sx={{ mb: 1 }}
            >
              <Typography variant="subtitle1">
                {t('library.recordingsCalendarMonth')}
              </Typography>
              <Stack direction="row" alignItems="center" spacing={0}>
                <IconButton
                  size="small"
                  onClick={() =>
                    setSelectedMonth((month) =>
                      month.subtract(1, 'month').startOf('month'),
                    )
                  }
                  disabled={!canGoPrev}
                  aria-label={t('library.prevMonth')}
                >
                  <ChevronLeft />
                </IconButton>
                <Typography
                  variant="body1"
                  sx={{ minWidth: 140, textAlign: 'center' }}
                >
                  {selectedMonth.format('MMMM YYYY')}
                </Typography>
                <IconButton
                  size="small"
                  onClick={() =>
                    setSelectedMonth((month) =>
                      month.add(1, 'month').startOf('month'),
                    )
                  }
                  disabled={!canGoNext}
                  aria-label={t('library.nextMonth')}
                >
                  <ChevronRight />
                </IconButton>
              </Stack>
            </Box>

            <LocalizationProvider dateAdapter={AdapterDayjs}>
              <StaticDatePicker
                value={selectedMonth}
                onChange={() => {}}
                onMonthChange={(month) => {
                  const nextMonth = month.startOf('month');
                  setSelectedMonth((currentMonth) =>
                    currentMonth.isSame(nextMonth, 'month')
                      ? currentMonth
                      : nextMonth,
                  );
                }}
                readOnly
                displayStaticWrapperAs="desktop"
                slots={{
                  day: (props) => (
                    <CalendarDay
                      {...props}
                      days={validStorageStats}
                      levels={levels}
                      onOpenDay={(date) => navigate(`/timeline?date=${date}`)}
                    />
                  ),
                }}
                slotProps={{
                  actionBar: { sx: { display: 'none' } },
                  toolbar: { hidden: true },
                }}
                sx={{
                  '& .MuiPickersCalendarHeader-root': {
                    display: 'none',
                  },
                }}
              />
            </LocalizationProvider>

            <Stack
              direction="row"
              spacing={2}
              justifyContent="center"
              sx={{ mt: 2, flexWrap: 'wrap' }}
              useFlexGap
            >
              <Stack direction="row" spacing={1} alignItems="center">
                <Box
                  sx={{
                    width: 12,
                    height: 12,
                    bgcolor: defaultColor,
                    borderRadius: 0.5,
                  }}
                />
                <Typography variant="caption" color="text.secondary">
                  {t('library.recordingsLevelNone')}
                </Typography>
              </Stack>
              {levels.map((level) => (
                <Stack
                  key={level.label}
                  direction="row"
                  spacing={1}
                  alignItems="center"
                >
                  <Box
                    sx={{
                      width: 12,
                      height: 12,
                      bgcolor: level.color,
                      borderRadius: 0.5,
                    }}
                  />
                  <Typography variant="caption" color="text.secondary">
                    {level.label}
                  </Typography>
                </Stack>
              ))}
            </Stack>
          </>
        )}
      </Paper>

      <Alert severity="info">{t('library.recordingsOpenDayHint')}</Alert>
    </Stack>
  );
}
