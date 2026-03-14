import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import Button from '@mui/material/Button';
import DownloadIcon from '@mui/icons-material/Download';
import dayjs, { Dayjs } from 'dayjs';
import Typography from '@mui/material/Typography';
import Grid from '@mui/material/Grid2';
import Box from '@mui/material/Box';
import CircularProgress from '@mui/material/CircularProgress';
import Paper from '@mui/material/Paper';
import { DatePicker } from '@mui/x-date-pickers/DatePicker';
import { LocalizationProvider } from '@mui/x-date-pickers/LocalizationProvider';
import { AdapterDayjs } from '@mui/x-date-pickers/AdapterDayjs';
import { useQuery } from '@tanstack/react-query';
import { fetchOverviewData, fetchWeather, downloadReportPdf } from '../../api/api';
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
import { overviewHelpConfig } from '../../page-help-config';

const formatHour = (hour: number) => {
  const date = new Date();
  date.setUTCHours(hour, 0, 0, 0);
  return date.toLocaleTimeString([], { hour: 'numeric', hour12: true });
};

export const Overview = () => {
  const { t } = useTranslation();
  const [selectedDay, setSelectedDay] = useState<Dayjs>(dayjs());
  const [downloadingPdf, setDownloadingPdf] = useState(false);

  const {
    data: overviewData,
    isLoading: isLoadingSightings,
    error: errorSightings,
  } = useQuery({
    queryKey: ['overview', selectedDay?.format('YYYY-MM-DD')],
    queryFn: () => fetchOverviewData(selectedDay?.format('YYYY-MM-DD') || ''),
    enabled: !!selectedDay,
  });

  const { data: weather, error: errorWeather } = useQuery({
    queryKey: ['weather'],
    queryFn: () => fetchWeather(),
  });

  if (isLoadingSightings)
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center' }}>
        <CircularProgress />
      </Box>
    );
  if (errorSightings || errorWeather) {
    const err = (errorSightings || errorWeather) as Error;
    return (
      <Box sx={{ p: 2 }}>
        <Typography color="error">{t('overview.errorLoad')}</Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
          {err?.message || String(errorSightings || errorWeather)}
        </Typography>
        <Typography variant="body2" sx={{ mt: 2 }}>{t('overview.checkApi')}</Typography>
      </Box>
    );
  }

  const formatRecordingTime = (seconds: number) => {
    if (seconds < 60) return `${Math.round(seconds)} ${t('time.sec')}`;
    if (seconds < 3600) return `${Math.round(seconds / 60)} ${t('time.min')}`;
    return `${(seconds / 3600).toFixed(1)} ${t('time.hrs')}`;
  };

  return (
    <Box sx={{ pb: 4 }}>
      <Grid
        container
        sx={{ pb: 4 }}
        spacing={3}
        justifyContent="space-between"
        alignItems="center"
      >
        {/* Header */}
        <Grid size={{ xs: 12, sm: 8 }}>
          <PageHelp {...overviewHelpConfig} />
        </Grid>
        <Grid size={{ xs: 12, sm: 4 }}>
          <Box sx={{ display: 'flex', gap: 1, alignItems: 'center', flexWrap: 'wrap' }}>
            <LocalizationProvider dateAdapter={AdapterDayjs}>
              <DatePicker
                label={t('commonLabels.date')}
                value={selectedDay}
                onChange={(newValue) => setSelectedDay(newValue as Dayjs)}
                disableFuture
                format="YYYY-MM-DD"
              />
            </LocalizationProvider>
            <Button
              variant="outlined"
              size="medium"
              startIcon={<DownloadIcon />}
              disabled={downloadingPdf}
              onClick={async () => {
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
          </Box>
        </Grid>
      </Grid>

      <Grid container spacing={2} sx={{ minHeight: '300px' }}>
        {/* Last bird widget */}
        {overviewData?.lastDetection && (
          <Grid size={{ xs: 12 }}>
            <Paper
              sx={{
                p: 2,
                bgcolor: 'primary.main',
                color: 'primary.contrastText',
                display: 'flex',
                alignItems: 'center',
                gap: 2,
              }}
            >
              <BirdIcon size={40} />
              <Box>
                <Typography variant="subtitle2" sx={{ opacity: 0.9 }}>
                  {t('overview.lastBird')}
                </Typography>
                <Typography variant="h6" sx={{ fontWeight: 600 }}>
                  {dayjs(overviewData.lastDetection.start_time).format('HH:mm')} — {overviewData.lastDetection.species_name}
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
              />
            </Grid>
            <Grid size={{ xs: 12, sm: 6, md: 4 }}>
              <StatCard
                icon={VisibilityOutlined}
                title={t('overview.totalVisits')}
                value={overviewData?.stats.totalDetections || 0}
              />
            </Grid>
            <Grid size={{ xs: 12, sm: 6, md: 4 }}>
              <StatCard
                icon={ScheduleOutlined}
                title={t('overview.visitsLastHour')}
                value={overviewData?.stats.lastHourDetections || 0}
              />
            </Grid>
            <Grid size={{ xs: 12, sm: 6, md: 4 }}>
              <StatCard
                icon={TimelapseOutlined}
                title={t('overview.meanDuration')}
                value={`${Math.round(overviewData?.stats.avgVisitDuration || 0)} ${t('time.sec')}`}
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
              />
            </Grid>
            <Grid size={{ xs: 12, sm: 6, md: 4 }}>
              <StatCard
                icon={VideocamOutlined}
                title={t('overview.recordingTime')}
                value={formatRecordingTime(
                  overviewData?.stats.videoDuration || 0,
                )}
              />
            </Grid>
          </Grid>
          {overviewData?.stats.detectionByProvider &&
            Object.keys(overviewData.stats.detectionByProvider).length > 0 && (
              <Paper sx={{ p: 2, mt: 2 }}>
                <Typography variant="subtitle2" gutterBottom color="text.secondary">
                  {t('overview.bySource')}
                </Typography>
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

        {/* Weather Card */}
        <Grid size={{ xs: 12, sm: 6, md: 4 }} sx={{ display: 'flex' }}>
          {weather && <WeatherCard weather={weather} />}
        </Grid>

        {/* Feed Control */}
        <Grid size={{ xs: 12, sm: 6, md: 4 }} sx={{ display: 'flex' }}>
          <FeedCard />
        </Grid>

        {/* Hourly Activity Line Chart */}
        <Grid size={{ xs: 12, md: 8 }} sx={{ display: 'flex' }}>
          <Paper sx={{ p: 2, width: '100%' }}>
            <Typography variant="h6" gutterBottom>
              {t('overview.hourlyActivity')}
            </Typography>
            {overviewData?.topSpecies && overviewData.topSpecies.length > 0 ? (
              <HourlyActivityChart data={overviewData.topSpecies} />
            ) : (
              <Typography color="text.secondary" sx={{ py: 4 }}>
                {t('overview.noData')}
              </Typography>
            )}
          </Paper>
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
              />
            ) : (
              <Typography color="text.secondary" sx={{ py: 4, textAlign: 'center' }}>
                {t('overview.noData')}
              </Typography>
            )}
          </Paper>
        </Grid>

        {/* Species Distribution */}
        <Grid size={{ xs: 12, md: 6 }}>
          <Paper sx={{ p: 2, height: '100%' }}>
            <Typography variant="h6" gutterBottom>
              {t('overview.topSpecies')}
            </Typography>
            {overviewData?.topSpecies && overviewData.topSpecies.length > 0 ? (
              <SpeciesDistributionChart data={overviewData.topSpecies} />
            ) : (
              <Typography color="text.secondary" sx={{ py: 4, textAlign: 'center' }}>
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
