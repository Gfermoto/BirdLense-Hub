import { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import axios from 'axios';
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Chip from '@mui/material/Chip';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';
import IconButton from '@mui/material/IconButton';
import { alpha, useTheme } from '@mui/material/styles';
import ChevronLeft from '@mui/icons-material/ChevronLeft';
import ChevronRight from '@mui/icons-material/ChevronRight';
import { LocalizationProvider } from '@mui/x-date-pickers/LocalizationProvider';
import { AdapterDayjs } from '@mui/x-date-pickers/AdapterDayjs';
import { StaticDatePicker } from '@mui/x-date-pickers/StaticDatePicker';
import { PickersDay, PickersDayProps } from '@mui/x-date-pickers/PickersDay';
import dayjs, { Dayjs } from 'dayjs';
import { BASE_API_URL } from '../../api/api';
import { queryKeys } from '../../api/queryKeys';
import { LibraryCardShell } from './LibraryCardShell';
import { getDayjsLocale, type StorageDay } from './libraryShared';

interface Level {
  minFiles: number;
  color: string;
  textColor: string;
  label: string;
}

const getLevels = (
  t: (key: string, opts?: Record<string, unknown>) => string,
  successMain: string,
  successLight: string,
): readonly Level[] => [
  {
    minFiles: 16,
    color: successMain,
    textColor: '#fff',
    label: t('library.recordingsLevelHigh'),
  },
  {
    minFiles: 8,
    color: alpha(successMain, 0.82),
    textColor: '#fff',
    label: t('library.recordingsLevelMedium'),
  },
  {
    minFiles: 1,
    color: alpha(successLight, 0.72),
    textColor: 'inherit',
    label: t('library.recordingsLevelLow'),
  },
];

function CalendarDay({
  day,
  days,
  levels,
  emptyColor,
  onOpenDay,
  ...other
}: PickersDayProps<Dayjs> & {
  days: StorageDay[];
  levels: readonly Level[];
  emptyColor: string;
  onOpenDay: (date: string) => void;
}) {
  const formattedDate = day.format('YYYY-MM-DD');
  const info = days.find((item) => item.date === formattedDate);
  const fileCount = info?.fileCount ?? 0;
  const level = levels.find((item) => fileCount >= item.minFiles);
  const bgColor = level?.color ?? emptyColor;
  const textColor = level?.textColor ?? 'text.primary';

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
          bgcolor: 'text.primary',
          color: 'background.paper',
          '&:hover': { bgcolor: 'text.primary' },
        },
        color: textColor,
        fontWeight: fileCount > 0 ? 600 : 400,
        border: '1px solid',
        borderColor: fileCount > 0 ? 'transparent' : 'divider',
      }}
    />
  );
}

export function RecordingsCalendar() {
  const { t, i18n } = useTranslation();
  const theme = useTheme();
  const navigate = useNavigate();
  const [selectedMonth, setSelectedMonth] = useState<Dayjs>(() =>
    dayjs().startOf('month'),
  );
  const levels = getLevels(
    t,
    theme.palette.success.main,
    theme.palette.success.light,
  );
  const emptyDayColor = alpha(theme.palette.action.hover, 0.35);
  const calendarLocale = getDayjsLocale(i18n.language);
  const {
    data: storageStats = [],
    isLoading,
    isError,
  } = useQuery<StorageDay[]>({
    queryKey: queryKeys.storage.stats,
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
      <LibraryCardShell
        title={t('library.recordingsCalendarTitle')}
        description={t('library.recordingsCalendarSubtitle')}
        eyebrow={t('library.sections.archiveTitle')}
      >
        <Stack
          direction={{ xs: 'column', md: 'row' }}
          alignItems={{ xs: 'flex-start', md: 'center' }}
          justifyContent="space-between"
          spacing={2}
          sx={{ mb: 2 }}
        >
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
          <Alert severity="error" variant="outlined">
            {t('library.recordingsLoadFailed')}
          </Alert>
        ) : validStorageStats.length === 0 ? (
          <Alert severity="info" variant="outlined">
            {t('library.recordingsEmptyHint')}
          </Alert>
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
                  {selectedMonth.locale(calendarLocale).format('MMMM YYYY')}
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

            <LocalizationProvider
              dateAdapter={AdapterDayjs}
              adapterLocale={calendarLocale}
            >
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
                      emptyColor={emptyDayColor}
                      onOpenDay={(date) => navigate(`/timeline?date=${date}`)}
                    />
                  ),
                }}
                slotProps={{
                  actionBar: { sx: { display: 'none' } },
                  toolbar: { hidden: true },
                }}
                sx={{
                  width: '100%',
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
                    bgcolor: emptyDayColor,
                    borderRadius: 0.5,
                    border: '1px solid',
                    borderColor: 'divider',
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
      </LibraryCardShell>

      <Alert severity="info" variant="outlined">
        {t('library.recordingsOpenDayHint')}
      </Alert>
    </Stack>
  );
}
