import { useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import type { TFunction } from 'i18next';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useLocation, useNavigate, useParams } from 'react-router-dom';
import axios from 'axios';
import {
  fetchTrackRegenerationStatus,
  type TrackRegenerationJobStatus,
} from '../../api/speciesOverviewDetections';
import {
  fetchVideo,
  fetchVideoDetectionFrames,
  fetchVideoNeighbors,
  fetchVideoReidMatch,
  regenerateTracksForSingleVideo,
} from '../../api/video';
import { queryKeys } from '../../api/queryKeys';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Grid from '@mui/material/Grid2';
import IconButton from '@mui/material/IconButton';
import Stack from '@mui/material/Stack';
import Tooltip from '@mui/material/Tooltip';
import Typography from '@mui/material/Typography';
import Alert from '@mui/material/Alert';
import Accordion from '@mui/material/Accordion';
import AccordionDetails from '@mui/material/AccordionDetails';
import AccordionSummary from '@mui/material/AccordionSummary';
import LinearProgress from '@mui/material/LinearProgress';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import NavigateBeforeIcon from '@mui/icons-material/NavigateBefore';
import NavigateNextIcon from '@mui/icons-material/NavigateNext';
import type { Video, VideoSpecies } from '../../types';
import { VideoInfo } from './VideoInfo';
import { VideoPlayer } from './VideoPlayer';
import { DetectedSpecies } from './DetectedSpecies';
import { PageHelp } from '../../components/PageHelp';
import { PageLoadingState, PageMessageState } from '../../components/PageState';
import { videoDetailsHelpConfig } from '../../page-help-config';
import { useProtectedArea } from '../../contexts/ProtectedAreaContext';
import { useDocumentTitle } from '../../hooks/useDocumentTitle';

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
  const r = st.result as
    | {
        generated?: number;
        skipped?: number;
        failed?: number;
        frames_updated?: number;
        precise_rerun_candidates?: Array<{
          video_id?: number;
          reason?: string;
        }>;
        single_video_regen?: {
          track_count?: number;
          decision_reasons?: Record<string, number>;
        };
      }
    | null
    | undefined;
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

function tailPath(p: string | null | undefined): string {
  if (!p) return '';
  const s = String(p).replace(/\\/g, '/');
  const i = s.lastIndexOf('/');
  return i >= 0 ? s.slice(i + 1) : s;
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
    queryKey: queryKeys.video.detail(String(params.id)),
    queryFn: () => fetchVideo(params.id as string),
  });
  useDocumentTitle(
    video ? `${t('video.video')} ${params.id}` : t('video.video'),
  );

  const { data: neighbors } = useQuery({
    queryKey: queryKeys.video.neighbors(String(params.id)),
    queryFn: () => fetchVideoNeighbors(params.id as string),
    enabled: Boolean(params.id),
  });

  const {
    data: detectionFrames,
    isPending: detectionFramesPending,
    error: detectionFramesError,
  } = useQuery({
    queryKey: queryKeys.video.detectionFrames(String(params.id)),
    queryFn: () => fetchVideoDetectionFrames(params.id as string),
    enabled: Boolean(params.id),
  });

  const { data: reidMatchPayload } = useQuery({
    queryKey: queryKeys.video.reidMatch(String(params.id)),
    queryFn: () => fetchVideoReidMatch(params.id as string),
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
      (s: VideoSpecies) =>
        s.source === 'video' && Array.isArray(s.frames) && s.frames.length > 0,
    );
    return Boolean(video.video_path) && !anyFrames;
  }, [video, displayVideo, detectionFramesPending, detectionFramesError]);
  const canRegenTracks = Boolean(isAdmin && video?.video_path);

  const videoIdNum = Number(params.id);

  const [followTrackRegen, setFollowTrackRegen] = useState<number | null>(null);
  const [trackRegenPollNonce, setTrackRegenPollNonce] = useState(0);
  const [finishedTrackRegen, setFinishedTrackRegen] =
    useState<TrackRegenerationJobStatus | null>(null);

  const trackRegenStart = useMutation({
    mutationFn: () => regenerateTracksForSingleVideo(videoIdNum),
    onSuccess: () => {
      setFinishedTrackRegen(null);
      setTrackRegenPollNonce((n) => n + 1);
      setFollowTrackRegen(videoIdNum);
    },
  });

  const { data: trackRemoteStatus } = useQuery({
    queryKey: queryKeys.video.trackRegenStatusUi(
      followTrackRegen,
      trackRegenPollNonce,
    ),
    queryFn: fetchTrackRegenerationStatus,
    enabled: followTrackRegen !== null,
    staleTime: 0,
    refetchOnMount: 'always',
    refetchInterval: (q) => (q.state.data?.status === 'running' ? 1000 : false),
  });

  useEffect(() => {
    trackRegenStart.reset();
    setFollowTrackRegen(null);
    setTrackRegenPollNonce(0);
    setFinishedTrackRegen(null);
    // Только смена ролика. Объекты useMutation() нестабильны по ссылке — если перечислить их
    // в deps, эффект крутится на каждом кадре (reset → ререндер → новый объект → снова effect).
    // eslint-disable-next-line react-hooks/exhaustive-deps -- намеренно только params.id
  }, [params.id]);

  useEffect(() => {
    if (followTrackRegen === null) return;
    const st = trackRemoteStatus;
    if (!st || st.status === 'running') return;
    setFinishedTrackRegen(st);
    setFollowTrackRegen(null);
    void queryClient.invalidateQueries({
      queryKey: queryKeys.video.detail(String(params.id)),
    });
    void queryClient.invalidateQueries({
      queryKey: queryKeys.video.detectionFrames(String(params.id)),
    });
    void queryClient.invalidateQueries({
      queryKey: queryKeys.timeline.speciesVisitsAll,
    });
  }, [followTrackRegen, trackRemoteStatus, queryClient, params.id]);

  const trackJobSummary = useMemo(
    () =>
      summarizeTrackRegenJob(finishedTrackRegen ?? undefined, videoIdNum, t),
    [finishedTrackRegen, videoIdNum, t],
  );

  const trackRegenBusy = trackRegenStart.isPending || followTrackRegen !== null;

  const trackProgress = trackRemoteStatus?.progress;
  const yoloFramesDone = trackProgress?.yolo_frames_done;
  const yoloFramesTotal = trackProgress?.yolo_frames_total;
  const hasYoloFrameProgress =
    typeof yoloFramesDone === 'number' &&
    typeof yoloFramesTotal === 'number' &&
    yoloFramesTotal > 0;
  const trackProgressOtherJob =
    followTrackRegen !== null &&
    trackRemoteStatus?.status === 'running' &&
    trackProgress?.active_request_video_id != null &&
    trackProgress.active_request_video_id !== videoIdNum;

  const trackRegenErrorMessage = (() => {
    const err = trackRegenStart.error;
    if (!err) return null;
    if (
      axios.isAxiosError(err) &&
      err.response?.data &&
      typeof err.response.data === 'object'
    ) {
      const d = err.response.data as { error?: string };
      if (d.error) return d.error;
    }
    return t('video.regenerateTracksThisVideoFailed');
  })();

  const trackProgressPct =
    trackProgress &&
    typeof trackProgress.total === 'number' &&
    trackProgress.total > 0 &&
    typeof trackProgress.processed === 'number'
      ? Math.min(
          100,
          Math.round((100 * trackProgress.processed) / trackProgress.total),
        )
      : null;
  const trackBarPct = hasYoloFrameProgress
    ? Math.min(
        100,
        Math.round((100 * yoloFramesDone) / yoloFramesTotal),
      )
    : trackProgressPct;
  const trackIndeterminate =
    !hasYoloFrameProgress &&
    (!trackProgress ||
      !trackProgress.total ||
      trackProgress.total <= 1 ||
      (trackProgress.total === 1 && (trackProgress.processed ?? 0) < 1));

  if (isLoading) return <PageLoadingState label={t('common.loading')} />;
  if (error || !video)
    return (
      <PageMessageState
        title={t('video.video')}
        message={t('errors.loadVideo')}
        severity="error"
        action={
          <Button variant="outlined" onClick={() => refetch()}>
            {t('common.retry')}
          </Button>
        }
      />
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
          {showTracksRegenHint &&
            (displayVideo ?? video).species.some((s) => s.source === 'video') && (
              <Alert severity="info" variant="outlined" sx={{ mb: 1 }}>
                {t('video.speciesWithoutOverlayHint')}
              </Alert>
            )}
          <VideoPlayer
            video={(displayVideo ?? video) as Video}
            showTracksRegenHint={showTracksRegenHint}
          />
          {isAdmin && (
            <Accordion sx={{ mt: 1 }}>
              <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                <Typography variant="subtitle1">
                  {t('video.serviceToolsTitle')}
                </Typography>
              </AccordionSummary>
              <AccordionDetails sx={{ px: 0, pb: 0 }}>
                <Box>
                  {trackRegenErrorMessage && (
                    <Alert
                      severity="error"
                      variant="outlined"
                      sx={{ mb: 1 }}
                      onClose={() => trackRegenStart.reset()}
                    >
                      {trackRegenErrorMessage}
                    </Alert>
                  )}
                  {showTracksRegenHint && (
                    <Alert severity="info" variant="outlined" sx={{ mb: 1 }}>
                      {t('video.tracksMissingHint')}
                    </Alert>
                  )}
                  {followTrackRegen !== null &&
                    trackRemoteStatus?.status === 'running' &&
                    trackProgressOtherJob && (
                      <Alert
                        severity="warning"
                        variant="outlined"
                        sx={{ mb: 1 }}
                      >
                        {t('video.trackRegenOtherVideo', {
                          id: trackProgress?.active_request_video_id ?? '?',
                        })}
                      </Alert>
                    )}
                  {followTrackRegen !== null &&
                    trackRemoteStatus?.status === 'running' &&
                    !trackProgressOtherJob && (
                      <Alert severity="info" variant="outlined" sx={{ mb: 1 }}>
                        <LinearProgress
                          variant={
                            trackIndeterminate ? 'indeterminate' : 'determinate'
                          }
                          {...(!trackIndeterminate
                            ? { value: trackBarPct ?? 0 }
                            : {})}
                          sx={{ mb: 1 }}
                        />
                        <Typography variant="body2" component="div">
                          {trackProgress &&
                          trackProgress.total &&
                          trackProgress.total > 1
                            ? t('video.trackRegenProgressBatch', {
                                processed: trackProgress.processed ?? 0,
                                total: trackProgress.total,
                              })
                            : t('video.trackRegenProgressSingle', {
                                phase: trackProgress?.phase ?? '…',
                              })}
                        </Typography>
                        {hasYoloFrameProgress ? (
                          <Typography
                            variant="caption"
                            color="text.secondary"
                            display="block"
                            sx={{ mt: 0.5 }}
                          >
                            {t('video.trackRegenFrameProgress', {
                              done: yoloFramesDone ?? 0,
                              total: yoloFramesTotal ?? 0,
                            })}
                          </Typography>
                        ) : null}
                        {trackProgress?.current_video ? (
                          <Typography
                            variant="caption"
                            color="text.secondary"
                            display="block"
                            sx={{ mt: 0.5 }}
                          >
                            {t('video.trackRegenProgressFile', {
                              name: tailPath(trackProgress.current_video),
                            })}
                          </Typography>
                        ) : null}
                      </Alert>
                    )}
                  {!trackRegenBusy && trackJobSummary && (
                    <Alert
                      severity={trackJobSummary.severity}
                      variant="outlined"
                      sx={{ mb: 1 }}
                      onClose={() => setFinishedTrackRegen(null)}
                    >
                      {trackJobSummary.message}
                    </Alert>
                  )}
                  <Stack direction="row" flexWrap="wrap" gap={1}>
                    {canRegenTracks && (
                      <Tooltip title={t('video.regenerateTracksThisVideoHelp')}>
                        <span>
                          <Button
                            variant="outlined"
                            size="small"
                            onClick={() => trackRegenStart.mutate()}
                            disabled={trackRegenBusy}
                          >
                            {trackRegenBusy
                              ? t('video.regenerateTracksThisVideoRunning')
                              : t('video.regenerateTracksThisVideo')}
                          </Button>
                        </span>
                      </Tooltip>
                    )}
                  </Stack>
                </Box>
              </AccordionDetails>
            </Accordion>
          )}
          <DetectedSpecies
            species={(displayVideo ?? (video as Video)).species}
            videoId={(video as Video).id}
            reidMatchByDetectionId={Object.fromEntries(
              (reidMatchPayload?.matches ?? []).map((m) => [m.video_species_id, m]),
            )}
          />
        </Grid>
        {/* Video Info Column */}
        <Grid size={{ xs: 12, lg: 4 }}>
          <VideoInfo
            video={(displayVideo ?? video) as Video}
          />
        </Grid>
      </Grid>
    </>
  );
};
