import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import Stack from '@mui/material/Stack';
import IconButton from '@mui/material/IconButton';
import ChevronLeft from '@mui/icons-material/ChevronLeft';
import ChevronRight from '@mui/icons-material/ChevronRight';
import { LocalizationProvider } from '@mui/x-date-pickers/LocalizationProvider';
import { AdapterDayjs } from '@mui/x-date-pickers/AdapterDayjs';
import { StaticDatePicker } from '@mui/x-date-pickers/StaticDatePicker';
import { PickersDay, PickersDayProps } from '@mui/x-date-pickers/PickersDay';
import dayjs, { Dayjs } from 'dayjs';
import axios from 'axios';
import { useQuery } from '@tanstack/react-query';
import { BASE_API_URL } from '../../api/api';

interface ActivityDay {
  date: string;
  totalUptime: number;
}

interface ActivityLevel {
  threshold: number;
  color: string;
  label: string;
}

const getActivityLevels = (t: (k: string) => string): readonly ActivityLevel[] => [
  { threshold: 12, color: '#2e7d32', label: t('library.activityOver12h') },
  { threshold: 8, color: '#43a047', label: t('library.activity8to12h') },
  { threshold: 4, color: '#ff9800', label: t('library.activity4to8h') },
  { threshold: 2, color: '#fdd835', label: t('library.activity2to4h') },
  { threshold: 0.001, color: '#d32f2f', label: t('library.activityUnder2h') },
];

const defaultColor = '#f5f5f5';

const getActivityColor = (
  hours: number,
  levels: readonly ActivityLevel[],
): string => {
  const level = levels.find((l) => hours >= l.threshold);
  return level?.color ?? defaultColor;
};

interface ActivityDayProps extends PickersDayProps<Dayjs> {
  activityDays?: ActivityDay[];
}

interface ActivityDayPropsWithLevels extends ActivityDayProps {
  activityLevels: readonly ActivityLevel[];
}

const ActivityDay = ({
  day,
  activityDays,
  activityLevels,
  ...other
}: ActivityDayPropsWithLevels) => {
  const formattedDate = day.format('YYYY-MM-DD');
  const dayData = activityDays?.find((d) => d.date === formattedDate);
  const uptimeHours = dayData?.totalUptime ?? 0;
  const bgColor = getActivityColor(uptimeHours, activityLevels);

  return (
    <PickersDay
      {...other}
      day={day}
      sx={{
        bgcolor: bgColor,
        '&:hover': {
          bgcolor: bgColor,
        },
        '&.Mui-selected': {
          bgcolor: 'gray',
          '&:hover': {
            bgcolor: 'gray',
          },
        },
        color: uptimeHours > 4 ? 'white' : 'black',
      }}
    />
  );
};

const Legend = ({
  levels,
}: {
  levels: readonly ActivityLevel[];
}) => (
  <Stack
    direction="row"
    spacing={2}
    justifyContent="center"
    sx={{ mt: 2, pb: 1 }}
  >
    {levels.map(({ color, label }) => (
      <Stack key={label} direction="row" spacing={1} alignItems="center">
        <Box
          sx={{ width: 12, height: 12, bgcolor: color, borderRadius: 0.5 }}
        />
        <Typography variant="caption" color="text.secondary">
          {label}
        </Typography>
      </Stack>
    ))}
  </Stack>
);

export const SystemActivity = () => {
  const { t } = useTranslation();
  const [selectedMonth, setSelectedMonth] = useState<Dayjs>(() => dayjs());
  const activityLevels = getActivityLevels(t);
  const { data: activityDays } = useQuery({
    queryKey: ['activity', selectedMonth.format('YYYY-MM')],
    queryFn: async () => {
      const { data } = await axios.get<ActivityDay[]>(
        `${BASE_API_URL}/system/activity`,
        {
          params: { month: selectedMonth.format('YYYY-MM') },
        },
      );
      return data;
    },
  });

  const canGoNext = selectedMonth.isBefore(dayjs(), 'month');
  const canGoPrev = selectedMonth.isAfter(dayjs('2020-01'), 'month');

  return (
    <>
      <Box display="flex" alignItems="center" justifyContent="space-between" sx={{ mb: 2 }}>
        <Typography variant="h5">
          {t('library.activity')}
        </Typography>
        <Stack direction="row" alignItems="center" spacing={0}>
          <IconButton
            size="small"
            onClick={() => setSelectedMonth((m) => m.subtract(1, 'month'))}
            disabled={!canGoPrev}
            aria-label={t('library.prevMonth')}
          >
            <ChevronLeft />
          </IconButton>
          <Typography variant="body1" sx={{ minWidth: 140, textAlign: 'center' }}>
            {selectedMonth.format('MMMM YYYY')}
          </Typography>
          <IconButton
            size="small"
            onClick={() => setSelectedMonth((m) => m.add(1, 'month'))}
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
          readOnly
          displayStaticWrapperAs="desktop"
          slots={{
            day: (props) => (
              <ActivityDay
                {...props}
                activityDays={activityDays}
                activityLevels={activityLevels}
              />
            ),
          }}
          slotProps={{
            actionBar: { sx: { display: 'none' } },
            toolbar: { hidden: true },
          }}
        />
      </LocalizationProvider>

      <Legend levels={activityLevels} />
    </>
  );
};
