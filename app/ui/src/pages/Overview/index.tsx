import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import Button from '@mui/material/Button';
import DownloadIcon from '@mui/icons-material/Download';
import dayjs, { Dayjs } from 'dayjs';
import Typography from '@mui/material/Typography';
import Grid from '@mui/material/Grid2';
import Box from '@mui/material/Box';
import Paper from '@mui/material/Paper';
import Skeleton from '@mui/material/Skeleton';
import { DatePicker } from '@mui/x-date-pickers/DatePicker';
import { LocalizationProvider } from '@mui/x-date-pickers/LocalizationProvider';
import { AdapterDayjs } from '@mui/x-date-pickers/AdapterDayjs';
import { useQuery } from '@tanstack/react-query';
import {
  fetchOverviewData,
  fetchWeather,
  downloadReportPdf,
} from '../../api/speciesOverviewDetections';
import { queryKeys } from '../../api/queryKeys';
import { WeatherCard } from '../../components/WeatherCard';
import { FeedCard } from '../../components/FeedCard';
import { StatCard } from '../../components/StatCard';
import DailyPatternChart from './DailyPatternChart';
import { SpeciesDistributionChart } from './SpeciesDistributionChart';
import { HourlyActivityChart } from './HourlyActivityChart';
import VisibilityOutlined from '@mui/icons-material/VisibilityOutlined';
import TimelapseOutlined from '@mui/icons-material/TimelapseOutlined';
import ScheduleOutlined from '@mui/icons-material/ScheduleOutlined';
import WbSunnyOutlined from '@mui/icons-material/WbSunnyOutlined';
import VideocamOutlined from '@mui/icons-material/VideocamOutlined';
import { BirdIcon } from '../../components/icons/BirdIcon';
import { PageHelp } from '../../components/PageHelp';
import { PageLoadingState, PageMessageState } from '../../components/PageState';
import { overviewHelpConfig } from '../../page-help-config';
import { useProtectedArea } from '../../contexts/ProtectedAreaContext';
import { useDocumentTitle } from '../../hooks/useDocumentTitle';
import Tooltip from '@mui/material/Tooltip';
import type { Weather } from '../../types';

const formatHour = (hour: number) => {
  return `${String(hour).padStart(2, '0')}:00`;
};

export const Overview = () => {
  const { t } = useTranslation();
  useDocumentTitle(t('nav.dashboard'));
  const { canEdit, unlocked, requiresPassword, role } = useProtectedArea();
  /** Подсказка про волонтёров — только для гостей, не после входа админа/оператора. */
  const showVolunteerDataLabelingHint =
    !unlocked ||
    !requiresPassword ||
    (role !== 'admin' && role !== 'contributor');
  const [selectedDay, setSelectedDay] = useState<Dayjs>(dayjs());
  const [downloadingPdf, setDownloadingPdf] = useState(false);

  const {
    data: overviewData,
    isLoading: isLoadingSightings,
    error: errorSightings,
    refetch: refetchOverview,
  } = useQuery({
    queryKey: queryKeys.overview.byDay(selectedDay?.format('YYYY-MM-DD') || ''),
    queryFn: () => fetchOverviewData(selectedDay?.format('YYYY-MM-DD') || ''),
    enabled: !!selectedDay,
  });

  const {
    data: weather,
    error: errorWeather,
    isPending: isWeatherPending,
    isFetching: isWeatherFetching,
    refetch: refetchWeather,
  } = useQuery({
    queryKey: queryKeys.weather.widget,
    queryFn: () => fetchWeather(),
  });

  /** Пока overview ждёт только sightings; погода грузится отдельно — иначе ячейка пустая и «пропадает» карточка. */
  const weatherAwaitingFirstPaint =
    (isWeatherPending || isWeatherFetching) && weather === undefined;

  if (isLoadingSightings)
    return <PageLoadingState label={t('common.loading')} />;
  if (errorSightings) {
    const err = errorSightings as Error;
    return (
      <PageMessageState
        title={t('nav.dashboard')}
        message={`${t('overview.errorLoad')} ${err?.message || String(errorSightings)} ${t('overview.checkApi')}`}
        severity="error"
        action={
          <Button
            variant="outlined"
            onClick={() => {
              refetchOverview();
              refetchWeather();
            }}
          >
            {t('common.retry')}
          </Button>
        }
      />
    );
  }

  const formatRecordingTime = (seconds: number) => {
    const s = Math.max(0, seconds);
    if (s < 60) return `${Math.round(s)} ${t('time.sec')}`;
    if (s < 3600) return `${Math.round(s / 60)} ${t('time.min')}`;
    return `${(s / 3600).toFixed(1)} ${t('time.hrs')}`;
  };

  return (
    <Box sx={{ pb: 4 }}>
      <Box sx={{ mb: 4 }}>
        <PageHelp
          {...overviewHelpConfig}
          actions={
            <Box
              sx={{
                display: 'flex',
                gap: 1,
                alignItems: 'center',
                flexWrap: 'wrap',
              }}
            >
              <LocalizationProvider dateAdapter={AdapterDayjs}>
                <DatePicker
                  value={selectedDay}
                  onChange={(newValue) => setSelectedDay(newValue as Dayjs)}
                  disableFuture
                  format="YYYY-MM-DD"
                  slotProps={{
                    textField: {
                      size: 'small',
                      'aria-label': t('commonLabels.date'),
                    },
                  }}
                />
              </LocalizationProvider>
              <Tooltip
                title={
                  !canEdit ? t('common.loginRequiredForExport') : undefined
                }
              >
                <span>
                  <Button
                    variant="outlined"
                    size="medium"
                    startIcon={<DownloadIcon />}
                    disabled={downloadingPdf || !canEdit}
                    onClick={async () => {
                      if (!canEdit) return;
                      setDownloadingPdf(true);
                      try {
                        await downloadReportPdf(selectedDay.format('YYYY-MM'));
                      } catch (err) {
                        console.error('PDF download failed:', err);
                      } finally {
                        setDownloadingPdf(false);
                      }
                    }}
                  >
                    {downloadingPdf ? '...' : t('overview.downloadPdf')}
                  </Button>
                </span>
              </Tooltip>
            </Box>
          }
        />
      </Box>

      <Grid container spacing={2} sx={{ minHeight: '300px' }}>
        {/* Last bird widget */}
        {overviewData?.lastDetection && (
          <Grid size={{ xs: 12 }}>
            <Paper
              sx={{
                p: 2,
                bgcolor: 'primary.dark',
                color: 'primary.contrastText',
                display: 'flex',
                alignItems: 'center',
                gap: 2,
              }}
            >
              <BirdIcon sx={{ fontSize: 40 }} />
              <Box>
                <Typography
                  variant="subtitle2"
                  sx={{ color: 'rgba(255,255,255,0.92)' }}
                >
                  {t('overview.lastBird')}
                </Typography>
                <Typography
                  variant="h6"
                  sx={{ fontWeight: 600, color: '#ffffff' }}
                >
                  {dayjs(
                    overviewData.lastDetection.start_time ?? undefined,
                  ).isValid()
                    ? dayjs(overviewData.lastDetection.start_time).format(
                        'HH:mm',
                      )
                    : '—'}{' '}
                  —{' '}
                  {overviewData.lastDetection.species_name === 'Bird'
                    ? t('overview.lastBirdUnknown')
                    : overviewData.lastDetection.species_name}
                </Typography>
              </Box>
            </Paper>
          </Grid>
        )}

        {/* Stats Cards */}
        <Grid size={{ xs: 12, md: 8 }}>
          <Grid container spacing={2}>
            <Grid size={{ xs: 12, sm: 6, md: 4 }}>
              <StatCard
                icon={BirdIcon}
                title={t('overview.uniqueSpecies')}
                value={overviewData?.stats.uniqueSpecies || 0}
                hint={t('overview.uniqueSpeciesHint')}
              />
            </Grid>
            <Grid size={{ xs: 12, sm: 6, md: 4 }}>
              <StatCard
                icon={VisibilityOutlined}
                title={t('overview.totalVisits')}
                value={overviewData?.stats.totalDetections || 0}
                hint={t('overview.totalVisitsHint')}
              />
            </Grid>
            <Grid size={{ xs: 12, sm: 6, md: 4 }}>
              <StatCard
                icon={ScheduleOutlined}
                title={t('overview.visitsLastHour')}
                value={overviewData?.stats.lastHourDetections || 0}
                hint={t('overview.visitsLastHourHint')}
              />
            </Grid>
            <Grid size={{ xs: 12, sm: 6, md: 4 }}>
              <StatCard
                icon={TimelapseOutlined}
                title={t('overview.meanDuration')}
                value={`${Math.round(overviewData?.stats.avgVisitDuration || 0)} ${t('time.sec')}`}
                hint={t('overview.meanDurationHint')}
              />
            </Grid>
            <Grid size={{ xs: 12, sm: 6, md: 4 }}>
              <StatCard
                icon={WbSunnyOutlined}
                title={t('overview.busiestHour')}
                value={
                  (overviewData?.stats.totalDetections ?? 0) > 0
                    ? formatHour(overviewData?.stats.busiestHour ?? 0)
                    : t('common.na')
                }
                hint={t('overview.busiestHourHint')}
              />
            </Grid>
            <Grid size={{ xs: 12, sm: 6, md: 4 }}>
              <StatCard
                icon={VideocamOutlined}
                title={t('overview.recordingTime')}
                value={formatRecordingTime(
                  Math.max(0, overviewData?.stats.videoDuration ?? 0),
                )}
                hint={t('overview.recordingTimeHint')}
              />
            </Grid>
          </Grid>
          {overviewData?.stats.detectionByProvider &&
            Object.keys(overviewData.stats.detectionByProvider).length > 0 && (
              <Paper sx={{ p: 2, mt: 2 }}>
                <Typography
                  variant="subtitle2"
                  gutterBottom
                  color="text.secondary"
                >
                  {t('overview.bySource')}
                </Typography>
                <Typography
                  variant="caption"
                  color="text.secondary"
                  display="block"
                  sx={{ mb: 1 }}
                >
                  {t('overview.bySourceHint')}
                </Typography>
                {showVolunteerDataLabelingHint && (
                  <Typography
                    variant="body2"
                    sx={{
                      mb: 1.5,
                      color: 'info.main',
                      fontWeight: 500,
                      bgcolor: (theme) =>
                        theme.palette.mode === 'dark'
                          ? 'rgba(2, 136, 209, 0.12)'
                          : 'rgba(2, 136, 209, 0.08)',
                      px: 1.25,
                      py: 0.75,
                      borderRadius: 1,
                      border: 1,
                      borderColor: 'info.light',
                    }}
                  >
                    {t('overview.volunteerDataLabelingHint')}
                  </Typography>
                )}
                <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1.5 }}>
                  {Object.entries(overviewData.stats.detectionByProvider).map(
                    ([provider, count]) => (
                      <Typography key={provider} variant="body2">
                        <strong>
                          {provider === 'yolo'
                            ? 'YOLO'
                            : provider === 'frigate'
                              ? 'Frigate'
                              : provider === 'birdnet_mqtt'
                                ? 'BirdNET (MQTT)'
                                : provider}
                        </strong>
                        : {count}
                      </Typography>
                    ),
                  )}
                </Box>
              </Paper>
            )}
        </Grid>

        {/* Weather Card — высота как две StatCard слева */}
        <Grid
          size={{ xs: 12, sm: 6, md: 4 }}
          sx={{ display: 'flex', alignItems: 'stretch' }}
        >
          {errorWeather && weather === undefined ? (
            <Paper sx={{ p: 2, width: '100%' }}>
              <Typography variant="subtitle2" color="error" gutterBottom>
                {t('overview.weatherLoadError')}
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                {(errorWeather as Error)?.message || String(errorWeather)}
              </Typography>
              <Button
                size="small"
                variant="outlined"
                onClick={() => refetchWeather()}
              >
                {t('common.retry')}
              </Button>
            </Paper>
          ) : weatherAwaitingFirstPaint ? (
            <Paper sx={{ p: 2, width: '100%', height: '100%', minHeight: 200 }}>
              <Typography variant="h6" gutterBottom>
                {t('weather.title')}
              </Typography>
              <Skeleton variant="rounded" height={36} sx={{ mb: 1 }} />
              <Skeleton variant="rounded" height={36} sx={{ mb: 1 }} />
              <Skeleton variant="rounded" width="55%" height={32} />
            </Paper>
          ) : weather &&
            typeof weather === 'object' &&
            Object.keys(weather as object).length > 0 ? (
            <WeatherCard
              weather={weather as Weather}
              date={selectedDay?.format('YYYY-MM-DD')}
            />
          ) : (
            <Paper sx={{ p: 2, width: '100%' }}>
              <Typography variant="body2" color="text.secondary">
                {t('weather.notConfigured')}
              </Typography>
            </Paper>
          )}
        </Grid>

        {/* Feed Control + Hourly Activity — в одной строке без зазора */}
        <Grid size={12}>
          <Box
            sx={{
              display: 'grid',
              gridTemplateColumns: {
                xs: '1fr',
                sm: 'minmax(280px, 320px) 1fr',
              },
              gap: 2,
              alignItems: 'stretch',
              width: '100%',
            }}
          >
            <Box>
              <FeedCard />
            </Box>
            <Paper sx={{ p: 2, minWidth: 0 }}>
              <Typography variant="h6" gutterBottom>
                {t('overview.hourlyActivity')}
              </Typography>
              {overviewData?.topSpecies &&
              overviewData.topSpecies.length > 0 ? (
                <HourlyActivityChart data={overviewData.topSpecies} />
              ) : (
                <Typography color="text.secondary" sx={{ py: 4 }}>
                  {t('overview.noData')}
                </Typography>
              )}
            </Paper>
          </Box>
        </Grid>
      </Grid>

      <Grid container spacing={2} sx={{ mt: 2 }}>
        {/* Daily Pattern Chart */}
        <Grid size={{ xs: 12, md: 6 }}>
          <Paper sx={{ p: 1, overflow: 'hidden' }}>
            <Typography variant="h6" sx={{ px: 1 }} gutterBottom>
              {t('overview.dailyPattern')}
            </Typography>
            {overviewData?.topSpecies && overviewData.topSpecies.length > 0 ? (
              <DailyPatternChart
                data={overviewData.topSpecies}
                date={selectedDay}
                size={450}
                observerTimezone={overviewData.observer_timezone}
              />
            ) : (
              <Typography
                color="text.secondary"
                sx={{ py: 4, textAlign: 'center' }}
              >
                {t('overview.noData')}
              </Typography>
            )}
          </Paper>
        </Grid>

        {/* Species Distribution */}
        <Grid size={{ xs: 12, md: 6 }}>
          <Paper sx={{ p: 1, overflow: 'hidden', minWidth: 0 }}>
            <Typography variant="h6" sx={{ px: 1 }} gutterBottom>
              {t('overview.topSpecies')}
            </Typography>
            {overviewData?.topSpecies && overviewData.topSpecies.length > 0 ? (
              <SpeciesDistributionChart
                data={overviewData.topSpecies}
                date={selectedDay}
                size={450}
              />
            ) : (
              <Typography
                color="text.secondary"
                sx={{ py: 4, textAlign: 'center' }}
              >
                {t('overview.noData')}
              </Typography>
            )}
          </Paper>
        </Grid>
      </Grid>
    </Box>
  );
};

export default Overview;
