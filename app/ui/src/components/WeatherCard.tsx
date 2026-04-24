import { useTranslation } from 'react-i18next';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Chip from '@mui/material/Chip';
import Paper from '@mui/material/Paper';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';
import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import WeatherIcon from '@mui/icons-material/WbSunny';
import TempIcon from '@mui/icons-material/Thermostat';
import HumidityIcon from '@mui/icons-material/Opacity';
import CloudIcon from '@mui/icons-material/Cloud';
import WindIcon from '@mui/icons-material/Air';
import SettingsIcon from '@mui/icons-material/Settings';
import { Weather } from '../types';
import { fetchSunTimes } from '../api/weatherRegion';
import { queryKeys } from '../api/queryKeys';
import { SunHorizon, type SunTimes } from './SunHorizon';
import { formatLocalDateTime } from '../util';
import { useProtectedArea } from '../contexts/ProtectedAreaContext';

interface WeatherCardProps {
  weather: Weather;
  /** Date for sun times (YYYY-MM-DD). If provided, shows sunrise/sunset arc. */
  date?: string | null;
}

export const WeatherCard = ({ weather, date }: WeatherCardProps) => {
  const { t } = useTranslation();
  const { isAdmin } = useProtectedArea();
  const isConfigured = Object.keys(weather).length > 0;
  const weatherMeta = (() => {
    if (!weather.source && !weather.fetched_at) return null;
    const weatherSourceLabel =
      weather.source === 'homeassistant'
        ? t('weather.sourceHomeAssistant')
        : t('weather.sourceOpenWeather');
    return weather.fetched_at
      ? t('weather.metaWithTime', {
          time: formatLocalDateTime(weather.fetched_at),
          source: weatherSourceLabel,
        })
      : t('weather.metaNoTime', { source: weatherSourceLabel });
  })();

  const { data: sunTimes } = useQuery({
    queryKey: queryKeys.weather.sunTimes(date || ''),
    queryFn: () => fetchSunTimes(date!),
    enabled: !!date && isConfigured,
    staleTime: 1000 * 60 * 60,
  });

  if (!isConfigured) {
    return (
      <Paper sx={{ padding: 2 }}>
        <Stack spacing={2} alignItems="center">
          <Typography variant="h6" sx={{ width: '100%' }}>
            {t('weather.title')}
          </Typography>
          <Box sx={{ textAlign: 'center', py: 2 }}>
            <Typography color="text.secondary" paragraph>
              {t('weather.notConfigured')}
            </Typography>
            {isAdmin ? (
              <Button
                component={Link}
                to="/settings"
                startIcon={<SettingsIcon />}
                variant="contained"
                color="primary"
              >
                {t('weather.configureSettings')}
              </Button>
            ) : null}
          </Box>
        </Stack>
      </Paper>
    );
  }

  return (
    <Paper
      sx={{
        padding: 1.5,
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        minHeight: 0,
      }}
    >
      <Stack spacing={1} sx={{ flex: 1, minHeight: 0 }}>
        <Box>
          <Typography variant="h6">{t('weather.title')}</Typography>
          {weatherMeta && (
            <Typography variant="caption" color="text.secondary">
              {weatherMeta}
            </Typography>
          )}
        </Box>
        <Box
          sx={{
            display: 'flex',
            flexWrap: 'wrap',
            gap: 1,
            '& .MuiChip-root': {
              minWidth: 110,
              height: 32,
              '& .MuiChip-label': { fontSize: '0.875rem' },
            },
          }}
        >
          <Chip
            icon={<WeatherIcon sx={{ fontSize: 20 }} />}
            label={weather.main}
            title={weather.description}
          />
          <Chip
            icon={<CloudIcon sx={{ fontSize: 20 }} />}
            label={`${weather.clouds}%`}
          />
          <Chip
            icon={<TempIcon sx={{ fontSize: 20 }} />}
            label={`${Math.round(weather.temp)}°C`}
          />
          <Chip
            icon={<HumidityIcon sx={{ fontSize: 20 }} />}
            label={`${weather.humidity}%`}
          />
          <Chip
            icon={<WindIcon sx={{ fontSize: 20 }} />}
            label={`${weather.wind_speed} m/s`}
          />
        </Box>
        {sunTimes && (
          <Box sx={{ pt: 0.75, borderTop: 1, borderColor: 'divider' }}>
            <SunHorizon
              sunTimes={
                {
                  dawn: sunTimes.dawn ?? '',
                  sunrise: sunTimes.sunrise ?? '',
                  noon: sunTimes.noon ?? '',
                  sunset: sunTimes.sunset ?? '',
                  dusk: sunTimes.dusk ?? '',
                } satisfies SunTimes
              }
            />
          </Box>
        )}
      </Stack>
    </Paper>
  );
};
