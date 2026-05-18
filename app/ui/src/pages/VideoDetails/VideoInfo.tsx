import { useCallback, useEffect, useState } from 'react';
import type { TFunction } from 'i18next';
import { useTranslation } from 'react-i18next';
import { useLocation, useNavigate } from 'react-router-dom';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import Paper from '@mui/material/Paper';
import Chip from '@mui/material/Chip';
import FormControlLabel from '@mui/material/FormControlLabel';
import Switch from '@mui/material/Switch';
import Avatar from '@mui/material/Avatar';
import Button from '@mui/material/Button';
import Dialog from '@mui/material/Dialog';
import DialogTitle from '@mui/material/DialogTitle';
import DialogContent from '@mui/material/DialogContent';
import DialogContentText from '@mui/material/DialogContentText';
import DialogActions from '@mui/material/DialogActions';
import TextField from '@mui/material/TextField';
import Accordion from '@mui/material/Accordion';
import AccordionSummary from '@mui/material/AccordionSummary';
import AccordionDetails from '@mui/material/AccordionDetails';
import CircularProgress from '@mui/material/CircularProgress';
import Collapse from '@mui/material/Collapse';
import FavoriteIcon from '@mui/icons-material/Favorite';
import AccessTimeIcon from '@mui/icons-material/AccessTime';
import MonitorWeightIcon from '@mui/icons-material/MonitorWeight';
import DownloadIcon from '@mui/icons-material/Download';
import DeleteIcon from '@mui/icons-material/Delete';
import AccountTreeIcon from '@mui/icons-material/AccountTree';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import { Video } from '../../types';
import { WeatherCard } from '../../components/WeatherCard';
import { getApiErrorMessage, resolveImageUrl } from '../../api/api';
import { BASE_API_URL } from '../../api/client';
import {
  deleteVideo,
  patchVideoFavorite,
  patchVideoRecording,
  fetchVideoFusionTrace,
  type FusionTracePayload,
  type FusionTraceStep,
  type FusionTraceTrack,
} from '../../api/video';
import { queryKeys } from '../../api/queryKeys';
import { useProtectedArea } from '../../contexts/ProtectedAreaContext';
import { formatLocalDateTime } from '../../util';

function safeInternalPath(from: unknown): string | null {
  if (
    typeof from !== 'string' ||
    !from.startsWith('/') ||
    from.startsWith('//')
  ) {
    return null;
  }
  if (from.includes('://') || from.includes('\\')) {
    return null;
  }
  return from;
}

function stageLabel(t: TFunction, stage: string): string {
  const key = `fusionTrace.stage.${stage}`;
  const translated = t(key);
  return translated === key ? stage : translated;
}

function fieldLabel(t: TFunction, field: string): string {
  const key = `fusionTrace.field.${field}`;
  const translated = t(key);
  return translated === key ? field : translated;
}

function trackSummaryLabel(t: TFunction, track: FusionTraceTrack): string {
  const species = track.species_name?.trim() || '—';
  const id = track.track_id != null ? String(track.track_id) : '—';
  if (track.bucket === 'persisted' || track.bucket === 'accepted') {
    return t('fusionTrace.trackPersisted', { species, id });
  }
  return t('fusionTrace.trackRejected', { species, id });
}

function FusionTrackSteps({
  t,
  steps,
}: {
  t: TFunction;
  steps: FusionTraceStep[];
}) {
  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
      {steps.map((step) => (
        <Box key={step.stage}>
          <Typography variant="subtitle2" color="primary" gutterBottom>
            {stageLabel(t, step.stage)}
          </Typography>
          <Box component="dl" sx={{ m: 0 }}>
            {step.lines.map((line) => (
              <Box
                key={line.field}
                sx={{
                  display: 'grid',
                  gridTemplateColumns: {
                    xs: '1fr',
                    sm: 'minmax(0, 0.95fr) minmax(0, 1.05fr)',
                  },
                  gap: 0.5,
                  mb: 0.75,
                }}
              >
                <Typography
                  component="dt"
                  variant="caption"
                  color="text.secondary"
                  sx={{ fontWeight: 600 }}
                >
                  {fieldLabel(t, line.field)}
                </Typography>
                <Typography
                  component="dd"
                  variant="body2"
                  sx={{ m: 0, wordBreak: 'break-word' }}
                >
                  {line.value}
                </Typography>
              </Box>
            ))}
          </Box>
        </Box>
      ))}
    </Box>
  );
}

export const VideoInfo = ({
  video,
}: {
  video: Video;
}) => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const location = useLocation();
  const queryClient = useQueryClient();
  const { unlocked, canEdit } = useProtectedArea();
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [behaviorDialogOpen, setBehaviorDialogOpen] = useState(false);
  const [behaviorDraftLabel, setBehaviorDraftLabel] = useState('');
  const [behaviorDraftConf, setBehaviorDraftConf] = useState('');
  const [fusionOpen, setFusionOpen] = useState(false);
  const [fusionLoading, setFusionLoading] = useState(false);
  const [fusionErr, setFusionErr] = useState<string | null>(null);
  const [fusionData, setFusionData] = useState<FusionTracePayload | null>(null);
  const [fusionRawOpen, setFusionRawOpen] = useState(false);
  const downloadUrl = unlocked
    ? `${BASE_API_URL}/videos/${video.id}/download`
    : null;

  const loadFusionTrace = useCallback(async () => {
    setFusionLoading(true);
    setFusionErr(null);
    try {
      const data = await fetchVideoFusionTrace(Number(video.id));
      setFusionData(data);
    } catch (e) {
      setFusionData(null);
      setFusionErr(getApiErrorMessage(e, t('fusionTrace.loadError')));
    } finally {
      setFusionLoading(false);
    }
  }, [video.id, t]);

  useEffect(() => {
    if (!fusionOpen) return;
    void loadFusionTrace();
  }, [fusionOpen, loadFusionTrace]);

  const favoriteMutation = useMutation({
    mutationFn: (next: boolean) => patchVideoFavorite(Number(video.id), next),
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: queryKeys.video.detail(String(video.id)),
      });
    },
  });

  const behaviorMutation = useMutation({
    mutationFn: (payload: { label: string; conf: string }) =>
      patchVideoRecording(Number(video.id), {
        behavior_label: payload.label.trim() || '',
        behavior_confidence:
          payload.conf.trim() === ''
            ? null
            : Math.min(1, Math.max(0, Number(payload.conf))),
      }),
    onSuccess: async () => {
      setBehaviorDialogOpen(false);
      await queryClient.invalidateQueries({
        queryKey: queryKeys.video.detail(String(video.id)),
      });
      await queryClient.invalidateQueries({
        queryKey: queryKeys.calendar.timelineTab,
      });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: () => deleteVideo(Number(video.id)),
    onSuccess: async () => {
      setDeleteDialogOpen(false);
      const vid = String(video.id);
      queryClient.removeQueries({ queryKey: queryKeys.video.detail(vid) });
      queryClient.removeQueries({ queryKey: queryKeys.video.neighbors(vid) });
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: queryKeys.unknowns.all }),
        queryClient.invalidateQueries({
          queryKey: queryKeys.timeline.unknownsCountAll,
        }),
        queryClient.invalidateQueries({ queryKey: queryKeys.video.listAll }),
        queryClient.invalidateQueries({
          queryKey: queryKeys.video.neighborsAll,
        }),
        queryClient.invalidateQueries({
          queryKey: queryKeys.calendar.timelineTab,
        }),
        queryClient.invalidateQueries({
          queryKey: queryKeys.timeline.speciesVisitsAll,
        }),
        queryClient.invalidateQueries({ queryKey: queryKeys.overview.all }),
        queryClient.invalidateQueries({
          queryKey: queryKeys.calendar.migration,
        }),
        queryClient.invalidateQueries({
          queryKey: queryKeys.birdDirectory.all,
        }),
        queryClient.invalidateQueries({
          queryKey: queryKeys.speciesSummary.all,
        }),
      ]);
      const back = safeInternalPath(
        (location.state as { from?: string } | null)?.from,
      );
      if (back) {
        navigate(back, { replace: true });
      } else {
        navigate('/library', { replace: true });
      }
    },
  });
  const {
    processor_version,
    start_time,
    end_time,
    favorite,
    weather,
    food,
    scales,
    behavior_label,
    behavior_confidence,
    behavior_model_kind,
    behavior_model_version,
    behavior_shadow_label,
    behavior_shadow_confidence,
    behavior_shadow_model_kind,
    behavior_shadow_model_version,
  } = video;

  const formatDate = (date: string | Date) => formatLocalDateTime(date);

  const duration = Math.max(
    0,
    Math.round(
      (new Date(end_time).getTime() - new Date(start_time).getTime()) / 1000,
    ),
  );

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
      {/* Download / Delete — только для админа и помощника */}
      {unlocked && (
        <Box sx={{ display: 'flex', gap: 1, flexDirection: 'column' }}>
          {downloadUrl && (
            <Button
              variant="contained"
              startIcon={<DownloadIcon />}
              href={downloadUrl}
              download
              fullWidth
              sx={{ py: 1.5 }}
            >
              {t('videoInfo.downloadVideo')}
            </Button>
          )}
          <Button
            variant="outlined"
            color="error"
            startIcon={<DeleteIcon />}
            fullWidth
            sx={{ py: 1.5 }}
            onClick={() => setDeleteDialogOpen(true)}
            disabled={deleteMutation.isPending}
          >
            {t('videoInfo.deleteRecording')}
          </Button>
        </Box>
      )}

      <Dialog
        open={deleteDialogOpen}
        onClose={() => !deleteMutation.isPending && setDeleteDialogOpen(false)}
      >
        <DialogTitle>{t('videoInfo.deleteConfirmTitle')}</DialogTitle>
        <DialogContent>
          <DialogContentText>
            {t('videoInfo.deleteConfirmText')}
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button
            onClick={() => setDeleteDialogOpen(false)}
            disabled={deleteMutation.isPending}
          >
            {t('common.cancel')}
          </Button>
          <Button
            color="error"
            variant="contained"
            onClick={() => deleteMutation.mutate()}
            disabled={deleteMutation.isPending}
          >
            {deleteMutation.isPending
              ? t('common.deleting')
              : t('common.delete')}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Favorite: toggle when unlocked; read-only chip for viewers if already marked */}
      {unlocked ? (
        <Box
          sx={{
            display: 'flex',
            flexDirection: 'column',
            gap: 0.5,
            alignItems: 'flex-start',
          }}
        >
          <FormControlLabel
            control={
              <Switch
                checked={!!favorite}
                disabled={favoriteMutation.isPending}
                onChange={(_, v) => favoriteMutation.mutate(v)}
                inputProps={{
                  'aria-label': t('videoInfo.favoriteToggle'),
                }}
              />
            }
            label={t('videoInfo.favoriteToggle')}
          />
          <Typography
            variant="caption"
            color="text.secondary"
            sx={{ maxWidth: 420 }}
          >
            {t('videoInfo.favoriteHint')}
          </Typography>
        </Box>
      ) : (
        favorite && (
          <Chip
            icon={<FavoriteIcon />}
            label={t('videoInfo.favorite')}
            color="primary"
            size="small"
            sx={{ alignSelf: 'flex-start' }}
          />
        )
      )}

      {(behavior_label || canEdit) && (
        <Paper sx={{ p: 2 }}>
          <Typography variant="h6" gutterBottom>
            {t('videoInfo.behaviorTitle')}
          </Typography>
          {behavior_label ? (
            <Chip
              label={`${behavior_label}${
                behavior_confidence != null && !Number.isNaN(Number(behavior_confidence))
                  ? ` (${(Number(behavior_confidence) * 100).toFixed(0)}%)`
                  : ''
              }`}
              size="small"
              sx={{ mb: 1, alignSelf: 'flex-start' }}
            />
          ) : (
            <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
              {t('videoInfo.behaviorNone')}
            </Typography>
          )}
          {behavior_model_kind ? (
            <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 1 }}>
              Model: {behavior_model_kind}
              {behavior_model_version ? ` (${behavior_model_version})` : ''}
            </Typography>
          ) : null}
          {behavior_shadow_label ? (
            <Chip
              label={`Shadow: ${behavior_shadow_label}${
                behavior_shadow_confidence != null &&
                !Number.isNaN(Number(behavior_shadow_confidence))
                  ? ` (${(Number(behavior_shadow_confidence) * 100).toFixed(0)}%)`
                  : ''
              }`}
              size="small"
              variant="outlined"
              sx={{ mb: 1, ml: 1, alignSelf: 'flex-start' }}
            />
          ) : null}
          {behavior_shadow_model_kind ? (
            <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 1 }}>
              Shadow model: {behavior_shadow_model_kind}
              {behavior_shadow_model_version ? ` (${behavior_shadow_model_version})` : ''}
            </Typography>
          ) : null}
          {canEdit && (
            <>
              <Button
                variant="outlined"
                size="small"
                onClick={() => {
                  setBehaviorDraftLabel(behavior_label || '');
                  setBehaviorDraftConf(
                    behavior_confidence != null
                      ? String(behavior_confidence)
                      : '',
                  );
                  setBehaviorDialogOpen(true);
                }}
              >
                {t('videoInfo.behaviorEdit')}
              </Button>
              <Dialog
                open={behaviorDialogOpen}
                onClose={() =>
                  !behaviorMutation.isPending && setBehaviorDialogOpen(false)
                }
              >
                <DialogTitle>{t('videoInfo.behaviorDialogTitle')}</DialogTitle>
                <DialogContent sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 1 }}>
                  <TextField
                    label={t('videoInfo.behaviorLabelField')}
                    value={behaviorDraftLabel}
                    onChange={(e) => setBehaviorDraftLabel(e.target.value)}
                    size="small"
                    fullWidth
                    helperText={t('videoInfo.behaviorLabelHint')}
                  />
                  <TextField
                    label={t('videoInfo.behaviorConfField')}
                    value={behaviorDraftConf}
                    onChange={(e) => setBehaviorDraftConf(e.target.value)}
                    size="small"
                    fullWidth
                    type="number"
                    inputProps={{ min: 0, max: 1, step: 0.05 }}
                    helperText={t('videoInfo.behaviorConfHint')}
                  />
                </DialogContent>
                <DialogActions>
                  <Button
                    onClick={() => setBehaviorDialogOpen(false)}
                    disabled={behaviorMutation.isPending}
                  >
                    {t('common.cancel')}
                  </Button>
                  <Button
                    variant="contained"
                    disabled={behaviorMutation.isPending}
                    onClick={() => {
                      const c = behaviorDraftConf.trim();
                      if (c !== '' && Number.isNaN(Number(c))) return;
                      behaviorMutation.mutate({
                        label: behaviorDraftLabel,
                        conf: behaviorDraftConf,
                      });
                    }}
                  >
                    {behaviorMutation.isPending
                      ? t('videoInfo.behaviorSaving')
                      : t('videoInfo.behaviorSave')}
                  </Button>
                </DialogActions>
              </Dialog>
            </>
          )}
          <Typography variant="caption" color="text.secondary" display="block" sx={{ mt: 1 }}>
            {t('videoInfo.behaviorTrainingNotInUi')}
          </Typography>
        </Paper>
      )}

      {/* Recording Info Card */}
      <Paper sx={{ p: 2 }}>
        <Typography
          variant="h6"
          gutterBottom
          sx={{ display: 'flex', alignItems: 'center', gap: 1 }}
        >
          <AccessTimeIcon fontSize="small" />
          {t('videoInfo.recordingInfo')}
        </Typography>
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
          <Typography variant="body2" color="text.secondary">
            <strong>{t('videoInfo.start')}:</strong> {formatDate(start_time)}
          </Typography>
          <Typography variant="body2" color="text.secondary">
            <strong>{t('videoInfo.end')}:</strong> {formatDate(end_time)}
          </Typography>
          <Typography variant="body2" color="text.secondary">
            <strong>{t('videoInfo.duration')}:</strong> {duration}s
          </Typography>
          <Typography variant="body2" color="text.secondary">
            <strong>{t('videoInfo.processor')}:</strong> v{processor_version}
          </Typography>
          {canEdit && (
            <>
              <Button
                variant="outlined"
                size="small"
                startIcon={<AccountTreeIcon />}
                fullWidth
                sx={{ mt: 1 }}
                onClick={() => {
                  setFusionRawOpen(false);
                  setFusionOpen(true);
                }}
              >
                {t('fusionTrace.openButton')}
              </Button>
              <Typography
                variant="caption"
                color="text.secondary"
                display="block"
                sx={{ mt: 0.5 }}
              >
                {t('fusionTrace.hint')}
              </Typography>
            </>
          )}
        </Box>
      </Paper>

      <Dialog
        open={fusionOpen}
        onClose={() => !fusionLoading && setFusionOpen(false)}
        maxWidth="md"
        fullWidth
      >
        <DialogTitle>{t('fusionTrace.title')}</DialogTitle>
        <DialogContent>
          {fusionLoading && (
            <Box sx={{ display: 'flex', justifyContent: 'center', py: 3 }}>
              <CircularProgress size={32} />
            </Box>
          )}
          {!fusionLoading && fusionErr && (
            <DialogContentText color="error">{fusionErr}</DialogContentText>
          )}
          {!fusionLoading &&
            !fusionErr &&
            fusionData &&
            !fusionData.available && (
              <>
                <DialogContentText>
                  {t('fusionTrace.noTrace')}
                </DialogContentText>
                <Typography
                  variant="caption"
                  color="text.secondary"
                  display="block"
                  sx={{ mt: 1 }}
                >
                  {t('fusionTrace.noTraceDetail')}
                </Typography>
              </>
            )}
          {!fusionLoading &&
            !fusionErr &&
            fusionData?.available &&
            fusionData.tracks && (
              <Box
                sx={{
                  display: 'flex',
                  flexDirection: 'column',
                  gap: 1.5,
                  pt: 0.5,
                }}
              >
                {fusionData.log_created_at && (
                  <Typography variant="body2" color="text.secondary">
                    {t('fusionTrace.logAt')}:{' '}
                    {formatLocalDateTime(fusionData.log_created_at)}
                  </Typography>
                )}
                {fusionData.trace && typeof fusionData.trace === 'object' && (
                  <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                    {'merge_window_seconds' in fusionData.trace && (
                      <Chip
                        size="small"
                        variant="outlined"
                        label={t('fusionTrace.mergeWindow', {
                          sec: String(
                            (fusionData.trace as Record<string, unknown>)
                              .merge_window_seconds ?? '',
                          ),
                        })}
                      />
                    )}
                    {('persisted_track_count' in fusionData.trace ||
                      'accepted_track_count' in fusionData.trace) && (
                      <Chip
                        size="small"
                        variant="outlined"
                        label={t('fusionTrace.persistedCount', {
                          n: String(
                            ('persisted_track_count' in fusionData.trace
                              ? (fusionData.trace as Record<string, unknown>)
                                  .persisted_track_count
                              : (fusionData.trace as Record<string, unknown>)
                                  .accepted_track_count) ?? '',
                          ),
                        })}
                      />
                    )}
                    {'rejected_track_count' in fusionData.trace && (
                      <Chip
                        size="small"
                        variant="outlined"
                        label={t('fusionTrace.rejectedCount', {
                          n: String(
                            (fusionData.trace as Record<string, unknown>)
                              .rejected_track_count ?? '',
                          ),
                        })}
                      />
                    )}
                  </Box>
                )}
                {fusionData.tracks.map((tr, idx) => (
                  <Accordion
                    key={`${tr.bucket}-${tr.track_id ?? idx}-${idx}`}
                    defaultExpanded={idx === 0}
                  >
                    <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                      <Typography variant="subtitle2">
                        {trackSummaryLabel(t, tr)}
                      </Typography>
                    </AccordionSummary>
                    <AccordionDetails>
                      <FusionTrackSteps t={t} steps={tr.steps} />
                    </AccordionDetails>
                  </Accordion>
                ))}
                <Button
                  size="small"
                  onClick={() => setFusionRawOpen((o) => !o)}
                  sx={{ alignSelf: 'flex-start' }}
                >
                  {fusionRawOpen
                    ? t('fusionTrace.hideRaw')
                    : t('fusionTrace.showRaw')}
                </Button>
                <Collapse in={fusionRawOpen}>
                  <Box
                    component="pre"
                    sx={{
                      mt: 1,
                      p: 1,
                      bgcolor: 'action.hover',
                      borderRadius: 1,
                      fontSize: 11,
                      overflow: 'auto',
                      maxHeight: 280,
                    }}
                  >
                    {JSON.stringify(fusionData.trace ?? {}, null, 2)}
                  </Box>
                </Collapse>
              </Box>
            )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setFusionOpen(false)} disabled={fusionLoading}>
            {t('common.close')}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Weather Card */}
      <WeatherCard
        weather={weather}
        date={
          start_time
            ? new Date(start_time).toISOString().slice(0, 10)
            : undefined
        }
      />

      {scales && (
        <Paper sx={{ p: 2 }}>
          <Typography
            variant="h6"
            gutterBottom
            sx={{ display: 'flex', alignItems: 'center', gap: 1 }}
          >
            <MonitorWeightIcon fontSize="small" />
            {t('videoInfo.scalesEstimateTitle')}
          </Typography>
          <Chip
            label={t('videoInfo.scalesEstimateValue', {
              value: scales.display_value,
              unit: scales.display_unit,
            })}
            variant="outlined"
            sx={{ mb: 1 }}
          />
          <Typography variant="caption" color="text.secondary" display="block">
            {t('videoInfo.scalesEstimateHint')}
          </Typography>
        </Paper>
      )}

      {/* Food Section */}
      {food.length > 0 && (
        <Paper sx={{ p: 2 }}>
          <Typography variant="h6" gutterBottom>
            {t('videoInfo.birdFood')}
          </Typography>
          <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
            {food.map((f) => (
              <Chip
                key={f.id}
                avatar={
                  <Avatar alt={f.name} src={resolveImageUrl(f.image_url)}>
                    {f.name[0]}
                  </Avatar>
                }
                label={f.name}
                variant="outlined"
              />
            ))}
          </Box>
        </Paper>
      )}
    </Box>
  );
};
