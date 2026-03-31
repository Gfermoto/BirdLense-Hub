import React, { useState, useRef, useEffect } from 'react';
import { useParams, Link as RouterLink } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import axios from 'axios';
import Button from '@mui/material/Button';
import IconButton from '@mui/material/IconButton';
import Tooltip from '@mui/material/Tooltip';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import StopIcon from '@mui/icons-material/Stop';
import Box from '@mui/material/Box';
import Card from '@mui/material/Card';
import CardContent from '@mui/material/CardContent';
import Typography from '@mui/material/Typography';
import Divider from '@mui/material/Divider';
import Stack from '@mui/material/Stack';
import Paper from '@mui/material/Paper';
import Grid from '@mui/material/Grid2';
import Alert from '@mui/material/Alert';
import Link from '@mui/material/Link';
import { LineChart, ScatterChart } from '@mui/x-charts';
import InfoIcon from '@mui/icons-material/Info';
import AccessTimeIcon from '@mui/icons-material/AccessTime';
import CloudIcon from '@mui/icons-material/Cloud';
import RestaurantIcon from '@mui/icons-material/Restaurant';
import AccessTimeFilledIcon from '@mui/icons-material/AccessTimeFilled';
import { CircularProgress } from '@mui/material';
import { SpeciesSummary } from '../../types';
import {
  fetchSpeciesSummary,
  fetchXenoCantoRecordings,
} from '../../api/api';
import { useTranslation } from 'react-i18next';
import { labelToUniqueHexColor } from '../../util';
import { VisitCard } from '../../components/VisitCard';
import { SpeciesIcon } from '../../components/SpeciesIcon';
import { resolveImageUrl } from '../../api/api';

const BirdSongButton = ({
  speciesId,
  playingRecording,
  setPlayingRecording,
  audioRef,
}: {
  speciesId: number;
  playingRecording: string | null;
  setPlayingRecording: (url: string | null) => void;
  audioRef: React.MutableRefObject<HTMLAudioElement | null>;
}) => {
  const { t } = useTranslation();
  const [recordings, setRecordings] = useState<{ file: string; en?: string; type?: string }[]>([]);
  const [searchUrl, setSearchUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handlePlay = async () => {
    if (playingRecording) {
      audioRef.current?.pause();
      setPlayingRecording(null);
      return;
    }
    if (recordings.length === 0 && !searchUrl) {
      setLoading(true);
      try {
        const res = await fetchXenoCantoRecordings(speciesId);
        setRecordings(res.recordings);
        setSearchUrl(res.xeno_canto_search_url ?? null);
        if (res.recordings.length > 0) {
          const url = res.recordings[0].file;
          const audio = new Audio(url);
          audioRef.current = audio;
          audio.onended = () => setPlayingRecording(null);
          audio.play().catch(() => setPlayingRecording(null));
          setPlayingRecording(url);
        } else if (res.xeno_canto_search_url) {
          window.open(res.xeno_canto_search_url, '_blank');
        }
      } catch {
        // ignore
      } finally {
        setLoading(false);
      }
    } else if (recordings.length > 0) {
      const url = recordings[0].file;
      const audio = new Audio(url);
      audioRef.current = audio;
      audio.onended = () => setPlayingRecording(null);
      audio.play().catch(() => setPlayingRecording(null));
      setPlayingRecording(url);
    } else if (searchUrl) {
      window.open(searchUrl, '_blank');
    }
  };

  return (
    <Tooltip title={t('speciesSummary.playSong')}>
      <span>
        <IconButton
          color="primary"
          onClick={handlePlay}
          disabled={loading}
          aria-label={t('speciesSummary.playSong')}
          sx={{
            bgcolor: playingRecording ? 'primary.main' : 'action.hover',
            color: playingRecording ? 'primary.contrastText' : 'primary.main',
            '&:hover': {
              bgcolor: playingRecording ? 'primary.dark' : 'action.selected',
            },
          }}
        >
          {playingRecording ? (
            <StopIcon fontSize="small" />
          ) : (
            <PlayArrowIcon fontSize="small" />
          )}
        </IconButton>
      </span>
    </Tooltip>
  );
};

const StatCard = ({
  icon,
  title,
  children,
}: {
  icon: React.ReactNode;
  title: string;
  children: React.ReactNode;
}) => (
  <Card elevation={2} sx={{ height: '100%', bgcolor: 'background.paper' }}>
    <CardContent>
      <Stack spacing={2}>
        <Stack direction="row" spacing={1} alignItems="center">
          {icon}
          <Typography variant="h6" color="primary">
            {title}
          </Typography>
        </Stack>
        <Divider />
        {children}
      </Stack>
    </CardContent>
  </Card>
);

const SpeciesSummaryPage = () => {
  const { t } = useTranslation();
  const { id } = useParams<{ id: string }>();
  const speciesId =
    id && /^\d+$/.test(id) ? parseInt(id, 10) : undefined;
  const speciesIdValid = speciesId !== undefined && speciesId > 0;
  const [playingRecording, setPlayingRecording] = useState<string | null>(null);
  const [imageLoadFailed, setImageLoadFailed] = useState(false);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  const { data, isLoading, error, refetch } = useQuery<SpeciesSummary>({
    queryKey: ['speciesSummary', speciesId],
    queryFn: () => fetchSpeciesSummary(speciesId!),
    enabled: speciesIdValid,
  });

  useEffect(() => {
    return () => {
      audioRef.current?.pause();
    };
  }, []);

  useEffect(() => {
    setImageLoadFailed(false);
  }, [speciesId]);

  if (!speciesIdValid) {
    return (
      <Box sx={{ p: 2 }}>
        <Alert severity="warning" sx={{ mb: 2 }}>
          {t('speciesSummary.invalidId')}
        </Alert>
        <Button variant="contained" component={RouterLink} to="/migration-calendar">
          {t('speciesSummary.openDirectory')}
        </Button>
      </Box>
    );
  }

  if (isLoading)
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center' }}>
        <CircularProgress />
      </Box>
    );
  if (error || !data) {
    const notFound = axios.isAxiosError(error) && error.response?.status === 404;
    return (
      <Box sx={{ p: 2 }}>
        <Alert severity={notFound ? 'info' : 'error'} sx={{ mb: 2 }}>
          {notFound ? t('speciesSummary.notFound') : t('speciesSummary.errorLoad')}
        </Alert>
        <Button variant="outlined" sx={{ mr: 1 }} onClick={() => refetch()}>
          {t('common.retry')}
        </Button>
        <Button variant="contained" component={RouterLink} to="/migration-calendar">
          {t('speciesSummary.openDirectory')}
        </Button>
      </Box>
    );
  }

  const hours = Array.from(
    { length: 24 },
    (_, i) => `${i.toString().padStart(2, '0')}:00`,
  );

  // Adjust timezone for activity data
  const tzOffset = new Date().getTimezoneOffset() / 60;
  const adjustTimeZone = (activity: number[]) =>
    activity.map((_, idx) => {
      let localIdx = idx + tzOffset;
      if (localIdx < 0) localIdx += 24;
      if (localIdx >= 24) localIdx -= 24;
      return activity[Math.floor(localIdx)];
    });

  const hourly =
    Array.isArray(data.stats.hourlyActivity) && data.stats.hourlyActivity.length === 24
      ? data.stats.hourlyActivity
      : Array.from({ length: 24 }, () => 0);
  const localActivity = adjustTimeZone(hourly);
  const subspeciesActivities = data.subspecies.map((sub) => ({
    name: sub.species.name,
    data: adjustTimeZone(
      Array.isArray(sub.stats.hourlyActivity) && sub.stats.hourlyActivity.length === 24
        ? sub.stats.hourlyActivity
        : Array.from({ length: 24 }, () => 0),
    ),
  }));

  return (
    <Box pb={4}>
      {/* Show parent link if species is not active */}
      {!data.species.active && data.species.parent && (
        <Alert
          severity="info"
          sx={{ mb: 3 }}
          action={
            <Link
              component={RouterLink}
              to={`/species/${data.species.parent.id}`}
              sx={{
                display: 'flex',
                alignItems: 'center',
                height: '100%',
                color: 'primary.main',
                textDecoration: 'none',
                '&:hover': {
                  textDecoration: 'underline',
                },
              }}
            >
              {t('speciesSummary.viewParent', { name: data.species.parent.name })}
            </Link>
          }
        >
          {t('speciesSummary.subspeciesOf', { name: data.species.parent.name })}
        </Alert>
      )}
      {/* Header Section */}
      <Paper elevation={0} sx={{ mb: 4, bgcolor: 'background.default' }}>
        <Grid container spacing={4} alignItems="center">
          <Grid size={{ xs: 12, md: 4 }}>
            <Box
              sx={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                minHeight: 200,
                bgcolor: 'action.hover',
                borderRadius: 2,
                overflow: 'hidden',
              }}
            >
              {data.species.image_url && !imageLoadFailed ? (
                <img
                  src={resolveImageUrl(data.species.image_url)}
                  alt={data.species.name}
                  onError={() => setImageLoadFailed(true)}
                  style={{
                    width: '100%',
                    height: 'auto',
                    borderRadius: '8px',
                    boxShadow: '0 4px 6px rgba(0, 0, 0, 0.1)',
                  }}
                />
              ) : (
                <SpeciesIcon speciesName={data.species.name} size={120} />
              )}
            </Box>
          </Grid>
          <Grid size={{ xs: 12, md: 8 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap', mb: 1 }}>
              <Typography variant="h4" color="primary">
                {data.species.name}
              </Typography>
              <BirdSongButton
                speciesId={speciesId as number}
                playingRecording={playingRecording}
                setPlayingRecording={setPlayingRecording}
                audioRef={audioRef}
              />
            </Box>
            <Typography
              variant="body1"
              color="text.secondary"
              textAlign="justify"
              sx={{ mb: 2 }}
            >
              {data.species.description || t('speciesSummary.noDescription')}
            </Typography>
            {data.species.metadata_source_url && (
              <Typography variant="caption" color="text.secondary">
                Source:{' '}
                <a
                  href={data.species.metadata_source_url}
                  target="_blank"
                  rel="noreferrer"
                >
                  {data.species.metadata_source || data.species.metadata_source_url}
                </a>
              </Typography>
            )}
          </Grid>
        </Grid>
      </Paper>

      {/* Stats Grid */}
      <Grid container spacing={3}>
        {/* Detection Stats */}
        <Grid size={{ xs: 12, md: 4 }}>
          <StatCard
            icon={<InfoIcon fontSize="small" color="primary" />}
            title={t('speciesSummary.totalDetectionStats')}
          >
            <Stack spacing={1.5}>
              <Typography variant="body1">
                {t('speciesSummary.last24h')}:{' '}
                <strong>{data.stats.detections.detections_24h}</strong>
              </Typography>
              <Typography variant="body1">
                {t('speciesSummary.last7d')}:{' '}
                <strong>{data.stats.detections.detections_7d}</strong>
              </Typography>
              <Typography variant="body1">
                {t('speciesSummary.last30d')}:{' '}
                <strong>{data.stats.detections.detections_30d}</strong>
              </Typography>
              {data.subspecies.length > 0 && (
                <>
                  <Divider />
                  {data.subspecies.map((sub) => (
                    <Box key={sub.species.id}>
                      <Link
                        variant="subtitle2"
                        color="primary"
                        component={RouterLink}
                        to={`/species/${sub.species.id}`}
                      >
                        {sub.species.name}
                      </Link>
                      <Typography variant="body2">
                        24h: {sub.stats.detections.detections_24h} | 7d:{' '}
                        {sub.stats.detections.detections_7d} | 30d:{' '}
                        {sub.stats.detections.detections_30d}
                      </Typography>
                    </Box>
                  ))}
                </>
              )}
              <Divider />
              {data.stats.timeRange.first_sighting && (
                <Typography variant="body2" color="text.secondary">
                  {t('speciesSummary.firstSeen')}:{' '}
                  {new Date(
                    data.stats.timeRange.first_sighting,
                  ).toLocaleDateString()}
                </Typography>
              )}
              {data.stats.timeRange.last_sighting && (
                <Typography variant="body2" color="text.secondary">
                  {t('speciesSummary.lastSeen')}:{' '}
                  {new Date(
                    data.stats.timeRange.last_sighting,
                  ).toLocaleDateString()}
                </Typography>
              )}
            </Stack>
          </StatCard>
        </Grid>

        {/* Daily Activity Pattern */}
        <Grid size={{ xs: 12, md: 8 }}>
          <StatCard
            icon={<AccessTimeIcon fontSize="small" color="primary" />}
            title={t('speciesSummary.dailyActivityPattern')}
          >
            <Box sx={{ width: '100%', height: 300 }}>
              <LineChart
                xAxis={[
                  {
                    data: hours,
                    scaleType: 'band',
                    tickLabelStyle: {
                      angle: 45,
                      textAnchor: 'start',
                      fontSize: 12,
                    },
                  },
                ]}
                series={[
                  {
                    data: localActivity,
                    // area: true,
                    color: labelToUniqueHexColor(data.species.name as string),
                    label: t('speciesSummary.total'),
                  },
                  ...subspeciesActivities.map((sub) => ({
                    data: sub.data,
                    color: labelToUniqueHexColor(sub.name as string),
                    label: sub.name,
                  })),
                ]}
                height={300}
              />
            </Box>
          </StatCard>
        </Grid>

        {/* Weather Preferences */}
        <Grid size={{ xs: 12, md: 6 }}>
          <StatCard
            icon={<CloudIcon fontSize="small" color="primary" />}
            title={t('speciesSummary.weatherPreferences')}
          >
            <Box sx={{ width: '100%', height: 300 }}>
              {data.stats.weather && data.stats.weather.length > 0 ? (
                <ScatterChart
                  height={300}
                  series={[
                    {
                      data: data.stats.weather.map((stat, index) => ({
                        id: index,
                        x: stat.temp,
                        y: stat.clouds,
                        size: Math.min(20, Math.max(5, stat.count / 5)),
                      })),
                      label: 'Total Sightings',
                    },
                  ]}
                  xAxis={[{ label: 'Temperature (°C)' }]}
                  yAxis={[{ label: 'Cloudiness (%)' }]}
                />
              ) : (
                <Typography variant="body2" color="text.secondary" sx={{ py: 4 }}>
                  {t('speciesSummary.noWeatherData')}
                </Typography>
              )}
            </Box>
          </StatCard>
        </Grid>

        {/* Food Preferences */}
        <Grid size={{ xs: 12, md: 6 }}>
          <StatCard
            icon={<RestaurantIcon fontSize="small" color="primary" />}
            title={t('speciesSummary.commonFoodDuringSightings')}
          >
            <Stack spacing={2}>
              {(data.stats.food ?? []).map((food) => (
                <Box
                  key={food.name}
                  sx={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                  }}
                >
                  <Typography variant="body1">{food.name}</Typography>
                  <Typography variant="body1" color="primary.main">
                    {food.count} {t('speciesSummary.sightings')}
                  </Typography>
                </Box>
              ))}
            </Stack>
          </StatCard>
        </Grid>
      </Grid>

      <Box mt={4}>
        <Stack>
          <Stack direction="row" spacing={1} alignItems="center">
            <AccessTimeFilledIcon fontSize="small" color="primary" />
            <Typography variant="h6" color="primary">
              {t('speciesSummary.recentVisits')}
            </Typography>
          </Stack>
          <Divider sx={{ my: 2 }} />
          <Stack spacing={2}>
            {data.recentVisits.map((visit) => (
              <Box key={visit.id}>
                <VisitCard visit={visit} compact showDateTime />
              </Box>
            ))}
          </Stack>
        </Stack>
      </Box>
    </Box>
  );
};

export default SpeciesSummaryPage;
