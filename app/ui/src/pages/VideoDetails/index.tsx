import { useTranslation } from 'react-i18next';
import { useQuery } from '@tanstack/react-query';
import { useLocation, useNavigate, useParams } from 'react-router-dom';
import { fetchVideo, fetchVideoNeighbors } from '../../api/api';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Grid from '@mui/material/Grid2';
import CircularProgress from '@mui/material/CircularProgress';
import IconButton from '@mui/material/IconButton';
import Stack from '@mui/material/Stack';
import Tooltip from '@mui/material/Tooltip';
import Typography from '@mui/material/Typography';
import NavigateBeforeIcon from '@mui/icons-material/NavigateBefore';
import NavigateNextIcon from '@mui/icons-material/NavigateNext';
import { Video } from '../../types';
import { VideoInfo } from './VideoInfo';
import { VideoPlayer } from './VideoPlayer';
import { DetectedSpecies } from './DetectedSpecies';
import { PageHelp } from '../../components/PageHelp';
import { videoDetailsHelpConfig } from '../../page-help-config';

export const VideoDetails = () => {
  const { t } = useTranslation();
  const params = useParams();
  const navigate = useNavigate();

  const {
    data: video,
    isLoading,
    error,
    refetch,
  } = useQuery({
    queryKey: ['video', params.id],
    queryFn: () => fetchVideo(params.id as string),
  });

  const { data: neighbors } = useQuery({
    queryKey: ['video-neighbors', params.id],
    queryFn: () => fetchVideoNeighbors(params.id as string),
    enabled: Boolean(params.id),
  });

  if (isLoading)
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center' }}>
        <CircularProgress />
      </Box>
    );
  if (error || !video)
    return (
      <Box sx={{ p: 2 }}>
        <Box component="span" sx={{ color: 'error.main' }}>{t('errors.loadSightings')}</Box>
        <Button variant="outlined" sx={{ mt: 2 }} onClick={() => refetch()}>
          {t('common.retry')}
        </Button>
      </Box>
    );

  return (
    <>
      <PageHelp {...videoDetailsHelpConfig} />
      <Grid container spacing={3}>
        {/* Video Player Column */}
        <Grid size={{ xs: 12, lg: 8 }}>
          {neighbors && neighbors.total > 0 && (
            <Stack
              direction="row"
              alignItems="center"
              spacing={0.5}
              sx={{ mb: 1 }}
            >
              <Tooltip
                title={
                  neighbors.previous_id
                    ? t('video.previousRecording')
                    : t('video.noPreviousRecording')
                }
              >
                <span>
                  <IconButton
                    size="small"
                    aria-label={t('video.previousRecording')}
                    disabled={!neighbors.previous_id}
                    onClick={() =>
                      neighbors.previous_id &&
                      navigate(`/videos/${neighbors.previous_id}`, {
                        state: listReturnState,
                      })
                    }
                  >
                    <NavigateBeforeIcon />
                  </IconButton>
                </span>
              </Tooltip>
              <Typography variant="body2" color="text.secondary" sx={{ px: 0.5 }}>
                {neighbors.index + 1} / {neighbors.total}
              </Typography>
              <Tooltip
                title={
                  neighbors.next_id
                    ? t('video.nextRecording')
                    : t('video.noNextRecording')
                }
              >
                <span>
                  <IconButton
                    size="small"
                    aria-label={t('video.nextRecording')}
                    disabled={!neighbors.next_id}
                    onClick={() =>
                      neighbors.next_id &&
                      navigate(`/videos/${neighbors.next_id}`, {
                        state: listReturnState,
                      })
                    }
                  >
                    <NavigateNextIcon />
                  </IconButton>
                </span>
              </Tooltip>
              <Tooltip title={t('video.neighborsDayHint')}>
                <Typography variant="caption" color="text.disabled" sx={{ ml: 1 }}>
                  {neighbors.day_scope === 'local'
                    ? `${t('video.localDayLabel')} ${neighbors.day_label}`
                    : `UTC ${neighbors.day_label}`}
                </Typography>
              </Tooltip>
            </Stack>
          )}
          <VideoPlayer video={video as Video} />
          <DetectedSpecies species={(video as Video).species} videoId={(video as Video).id} />
        </Grid>
        {/* Video Info Column */}
        <Grid size={{ xs: 12, lg: 4 }}>
          <VideoInfo video={video as Video} />
        </Grid>
      </Grid>
    </>
  );
};
