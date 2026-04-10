import { useEffect, useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import type { TFunction } from 'i18next';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useLocation, useNavigate, useParams } from 'react-router-dom';
import axios from 'axios';
import {
  fetchVideo,
  fetchVideoNeighbors,
  fetchVideoDetectionFrames,
  fetchTrackRegenerationStatus,
  fetchSpectrogramRegenerationStatus,
  regenerateTracksForSingleVideo,
  regenerateSpectrogramForSingleVideo,
  type TrackRegenerationJobStatus,
  type SpectrogramRegenerationJobStatus,
} from '../../api/api';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Grid from '@mui/material/Grid2';
import CircularProgress from '@mui/material/CircularProgress';
import IconButton from '@mui/material/IconButton';
import Stack from '@mui/material/Stack';
import Tooltip from '@mui/material/Tooltip';
import Typography from '@mui/material/Typography';
import Alert from '@mui/material/Alert';
import NavigateBeforeIcon from '@mui/icons-material/NavigateBefore';
import NavigateNextIcon from '@mui/icons-material/NavigateNext';
import GraphicEqIcon from '@mui/icons-material/GraphicEq';
import { Video } from '../../types';
import { VideoInfo } from './VideoInfo';
import { VideoPlayer } from './VideoPlayer';
import { DetectedSpecies } from './DetectedSpecies';
import { PageHelp } from '../../components/PageHelp';
import { videoDetailsHelpConfig } from '../../page-help-config';
import { useProtectedArea } from '../../contexts/ProtectedAreaContext';

function summarizeTrackRegenJob(
  st: TrackRegenerationJobStatus | undefined,
  videoId: number,
  t: TFunction,
): { severity: 'success' | 'warning' | 'error'; message: string } | null {
  if (!st) return null;
  if (st.status === 'running') return null;
  if (st.error) {
    return { severity: 'error', message: st.error };
  }
  const r = st.result as {
    generated?: number;
    skipped?: number;
    failed?: number;
    frames_updated?: number;
    precise_rerun_candidates?: Array<{ video_id?: number; reason?: string }>;
    single_video_regen?: {
      track_count?: number;
      decision_reasons?: Record<string, number>;
    };
  } | null | undefined;
  if (!r && st.status === 'done') {
    return { severity: 'warning', message: t('video.regenDoneNoPayload') };
  }
  if (!r) {
    return { severity: 'warning', message: t('video.regenResultTimeout') };
  }
  const gen = Number(r.generated ?? 0);
  const skip = Number(r.skipped ?? 0);
  const fail = Number(r.failed ?? 0);
  const framesUpdated = Number(r.frames_updated ?? 0);
  const candidates = r.precise_rerun_candidates ?? [];
  const mine = candidates.find((c) => c.video_id === videoId);
  let message = t('video.regenResultSummary', {
    generated: gen,
    skipped: skip,
    failed: fail,
  });
  if (mine?.reason) {
    message += ` ${t('video.regenResultThisVideoReason', { reason: mine.reason })}`;
  } else if (gen === 0) {
    message += ` ${t('video.regenResultCheckLogs')}`;
  }
  if (framesUpdated > 0) {
    message += ` ${t('video.regenFramesUpdatedSummary', { count: framesUpdated })}`;
  }
  const sv = r.single_video_regen;
  if (
    sv &&
    typeof sv.track_count === 'number' &&
    sv.decision_reasons &&
    Object.keys(sv.decision_reasons).length > 0
  ) {
    const reasons = Object.entries(sv.decision_reasons)
      .map(([k, v]) => `${k}=${v}`)
      .join(', ');
    message += ` ${t('video.regenSingleVideoSummary', { count: sv.track_count, reasons })}`;
  }
  const severity: 'success' | 'warning' =
    fail > 0 || (gen === 0 && skip > 0) ? 'warning' : 'success';
  return { severity, message };
}

function summarizeSpecRegenJob(
  st: SpectrogramRegenerationJobStatus | undefined,
  t: TFunction,
): { severity: 'success' | 'warning' | 'error'; message: string } | null {
  if (!st) return null;
  if (st.status === 'running') return null;
  if (st.error) return { severity: 'error', message: st.error };
  if (st.status === 'done') {
    return { severity: 'success', message: t('video.specRegenDone') };
  }
  return { severity: 'warning', message: t('video.regenResultTimeout') };
}

export const VideoDetails = () => {
  const { t } = useTranslation();
  const params = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const queryClient = useQueryClient();
  const { isAdmin } = useProtectedArea();

  /** Preserve return path when stepping prev/next. */
  const neighborNavigationState = (() => {
    const s = location.state;
    if (s && typeof s === 'object') {
      const from = (s as { from?: unknown }).from;
      const state: { from?: string } = {};
      if (
        typeof from === 'string' &&
        from.startsWith('/') &&
        !from.startsWith('//')
      ) {
        state.from = from;
      }
      if (state.from) {
        return state;
      }
    }
    return undefined;
  })();

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

  const { data: detectionFrames, isPending: detectionFramesPending, error: detectionFramesError } = useQuery({
    queryKey: ['video-detection-frames', params.id],
    queryFn: () => fetchVideoDetectionFrames(params.id as string),
    enabled: Boolean(params.id),
  });

  const displayVideo = useMemo((): Video | undefined => {
    if (!video) return undefined;
    const tracks = detectionFrames?.tracks;
    if (!tracks?.length) return video as Video;
    const byDetId = new Map(tracks.map((t) => [t.id, t.frames]));
    return {
      ...(video as Video),
      species: (video as Video).species.map((s) => {
        const detId = s.id;
        if (detId === undefined) return s;
        const frames = byDetId.get(detId);
        return frames ? { ...s, frames } : s;
      }),
    };
  }, [video, detectionFrames]);

  const showTracksRegenHint = useMemo(() => {
    if (!video || detectionFramesPending || detectionFramesError) return false;
    const merged = displayVideo ?? video;
    const anyFrames = merged.species.some(
      (s) => s.source === 'video' && Array.isArray(s.frames) && s.frames.length > 0,
    );
    return Boolean(video.video_path) && !anyFrames;
  }, [video, displayVideo, detectionFramesPending, detectionFramesError]);
  const canRegenTracks = Boolean(isAdmin && video?.video_path);

  const videoIdNum = Number(params.id);

  const trackRegenMutation = useMutation({
    mutationFn: async (): Promise<TrackRegenerationJobStatus> => {
      await regenerateTracksForSingleVideo(videoIdNum);
      let last: TrackRegenerationJobStatus = { status: 'running' };
      for (let i = 0; i < 90; i++) {
        await new Promise((r) => setTimeout(r, 1500));
        last = await fetchTrackRegenerationStatus();
        if (last.status !== 'running') {
          return last;
        }
      }
      return last;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['video', params.id] });
      queryClient.invalidateQueries({ queryKey: ['video-detection-frames', params.id] });
      queryClient.invalidateQueries({ queryKey: ['speciesVisits'] });
    },
  });

  const specRegenMutation = useMutation({
    mutationFn: async (): Promise<SpectrogramRegenerationJobStatus> => {
      await regenerateSpectrogramForSingleVideo(videoIdNum);
      let last: SpectrogramRegenerationJobStatus = { status: 'running' };
      for (let i = 0; i < 90; i++) {
        await new Promise((r) => setTimeout(r, 1500));
        last = await fetchSpectrogramRegenerationStatus();
        if (last.status !== 'running') {
          return last;
        }
      }
      return last;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['video', params.id] });
      queryClient.invalidateQueries({ queryKey: ['speciesVisits'] });
    },
  });

  useEffect(() => {
    trackRegenMutation.reset();
    specRegenMutation.reset();
  }, [params.id, trackRegenMutation, specRegenMutation]);

  const trackJobSummary = useMemo(
    () => summarizeTrackRegenJob(trackRegenMutation.data, videoIdNum, t),
    [trackRegenMutation.data, videoIdNum, t],
  );

  const specJobSummary = useMemo(
    () => summarizeSpecRegenJob(specRegenMutation.data, t),
    [specRegenMutation.data, t],
  );

  const trackRegenErrorMessage = (() => {
    const err = trackRegenMutation.error;
    if (!err) return null;
    if (axios.isAxiosError(err) && err.response?.data && typeof err.response.data === 'object') {
      const d = err.response.data as { error?: string };
      if (d.error) return d.error;
    }
    return t('video.regenerateTracksThisVideoFailed');
  })();

  const specRegenErrorMessage = (() => {
    const err = specRegenMutation.error;
    if (!err) return null;
    if (axios.isAxiosError(err) && err.response?.data && typeof err.response.data === 'object') {
      const d = err.response.data as { error?: string };
      if (d.error) return d.error;
    }
    return t('video.regenerateSpectrogramThisVideoFailed');
  })();

  if (isLoading)
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center' }}>
        <CircularProgress />
      </Box>
    );
  if (error || !video)
    return (
      <Box sx={{ p: 2 }}>
        <Box component="span" sx={{ color: 'error.main' }}>
          {t('errors.loadSightings')}
        </Box>
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
                        state: neighborNavigationState,
                      })
                    }
                  >
                    <NavigateBeforeIcon />
                  </IconButton>
                </span>
              </Tooltip>
              <Typography
                variant="body2"
                color="text.secondary"
                sx={{ px: 0.5 }}
              >
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
                        state: neighborNavigationState,
                      })
                    }
                  >
                    <NavigateNextIcon />
                  </IconButton>
                </span>
              </Tooltip>
              <Tooltip title={t('video.neighborsDayHint')}>
                <Typography
                  variant="caption"
                  color="text.disabled"
                  sx={{ ml: 1 }}
                >
                  {neighbors.day_scope === 'local'
                    ? `${t('video.localDayLabel')} ${neighbors.day_label}`
                    : `UTC ${neighbors.day_label}`}
                </Typography>
              </Tooltip>
            </Stack>
          )}
          <VideoPlayer
            video={(displayVideo ?? video) as Video}
            showTracksRegenHint={showTracksRegenHint}
          />
          {isAdmin && (
            <Box sx={{ mt: 1 }}>
              {trackRegenErrorMessage && (
                <Alert severity="error" sx={{ mb: 1 }} onClose={() => trackRegenMutation.reset()}>
                  {trackRegenErrorMessage}
                </Alert>
              )}
              {specRegenErrorMessage && (
                <Alert severity="error" sx={{ mb: 1 }} onClose={() => specRegenMutation.reset()}>
                  {specRegenErrorMessage}
                </Alert>
              )}
              {showTracksRegenHint && (
                <Alert
                  severity="info"
                  sx={{ mb: 1 }}
                >
                  {t('video.tracksMissingHint')}
                </Alert>
              )}
              {!trackRegenMutation.isPending && trackJobSummary && (
                <Alert
                  severity={trackJobSummary.severity}
                  sx={{ mb: 1 }}
                  onClose={() => trackRegenMutation.reset()}
                >
                  {trackJobSummary.message}
                </Alert>
              )}
              {!specRegenMutation.isPending && specJobSummary && (
                <Alert
                  severity={specJobSummary.severity}
                  sx={{ mb: 1 }}
                  onClose={() => specRegenMutation.reset()}
                >
                  {specJobSummary.message}
                </Alert>
              )}
              <Stack direction="row" flexWrap="wrap" gap={1}>
                {canRegenTracks && (
                  <Tooltip title={t('video.regenerateTracksThisVideoHelp')}>
                    <span>
                      <Button
                        variant="outlined"
                        size="small"
                        onClick={() => trackRegenMutation.mutate()}
                        disabled={trackRegenMutation.isPending || specRegenMutation.isPending}
                      >
                        {trackRegenMutation.isPending
                          ? t('video.regenerateTracksThisVideoRunning')
                          : t('video.regenerateTracksThisVideo')}
                      </Button>
                    </span>
                  </Tooltip>
                )}
                <Tooltip title={t('video.regenerateSpectrogramThisVideoHelp')}>
                  <span>
                    <Button
                      variant="outlined"
                      size="small"
                      disabled={trackRegenMutation.isPending || specRegenMutation.isPending}
                      startIcon={<GraphicEqIcon fontSize="small" />}
                      onClick={() => specRegenMutation.mutate()}
                    >
                      {specRegenMutation.isPending
                        ? t('video.regenerateSpectrogramThisVideoRunning')
                        : t('video.regenerateSpectrogramThisVideo')}
                    </Button>
                  </span>
                </Tooltip>
              </Stack>
            </Box>
          )}
          <DetectedSpecies
            species={(displayVideo ?? (video as Video)).species}
            videoId={(video as Video).id}
          />
        </Grid>
        {/* Video Info Column */}
        <Grid size={{ xs: 12, lg: 4 }}>
          <VideoInfo video={(displayVideo ?? video) as Video} />
        </Grid>
      </Grid>
    </>
  );
};
