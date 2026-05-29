import React, { memo, useState } from 'react';
import type { SpeciesVisit } from '../types';
import Card from '@mui/material/Card';
import CardContent from '@mui/material/CardContent';
import Typography from '@mui/material/Typography';
import { SpeciesIcon } from './SpeciesIcon';
import Chip from '@mui/material/Chip';
import Box from '@mui/material/Box';
import CardActionArea from '@mui/material/CardActionArea';
import Collapse from '@mui/material/Collapse';
import IconButton from '@mui/material/IconButton';
import ExpandMore from '@mui/icons-material/ExpandMore';
import ExpandLess from '@mui/icons-material/ExpandLess';
import Thermostat from '@mui/icons-material/Thermostat';
import CalendarToday from '@mui/icons-material/CalendarToday';
import Groups from '@mui/icons-material/Groups';
import VideoCall from '@mui/icons-material/VideoCall';
import Mic from '@mui/icons-material/Mic';
import Share from '@mui/icons-material/Share';
import MonitorWeightIcon from '@mui/icons-material/MonitorWeight';
import DeleteOutline from '@mui/icons-material/DeleteOutline';
import Tooltip from '@mui/material/Tooltip';
import Snackbar from '@mui/material/Snackbar';
import Alert from '@mui/material/Alert';
import Button from '@mui/material/Button';
import Stack from '@mui/material/Stack';
import TextField from '@mui/material/TextField';
import { useLocation, useNavigate } from 'react-router-dom';
import { useTheme } from '@mui/material/styles';
import { useTranslation } from 'react-i18next';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { downloadDetectionCropForINaturalist } from '../api/dataset';
import { getApiErrorMessage } from '../api/api';
import { invalidateLocalSpeciesEditCaches } from '../api/invalidateLocalSpeciesCaches';
import {
  deleteVisit,
  updateDetectionNickname,
} from '../api/speciesOverviewDetections';
import { UnlinkBirdProfileButton } from './UnlinkBirdProfileButton';
import { DeleteBirdProfileButton } from './DeleteBirdProfileButton';
import { getVisitBirdProfileId } from '../pages/Timeline/timelineFilters';
import { useProtectedArea } from '../contexts/ProtectedAreaContext';
import { formatDuration } from '../utils/timeUtils';
import { formatLocalDateTime, formatLocalTime } from '../util';

const DetectionItem = ({
  detection,
  speciesName,
  onClick,
  isLastInGroup,
  inaturalistShareEnabled,
}: {
  detection: SpeciesVisit['detections'][0];
  speciesName: string;
  onClick: () => void;
  isLastInGroup: boolean;
  inaturalistShareEnabled: boolean;
}) => {
  const theme = useTheme();
  const { t } = useTranslation();
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const handleINaturalist = async (e: React.MouseEvent) => {
    e.stopPropagation();
    if (
      !inaturalistShareEnabled ||
      !detection.id ||
      detection.source !== 'video'
    )
      return;
    setLoading(true);
    setErrorMsg(null);
    try {
      await downloadDetectionCropForINaturalist(detection.id, speciesName);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setErrorMsg(msg);
      console.error('iNaturalist export failed:', err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Box>
      <CardActionArea
        component="div"
        onClick={onClick}
        sx={{
          p: 1.5,
          borderRadius: 1,
          backgroundColor: theme.palette.action.hover,
        }}
      >
        <Box display="flex" alignItems="center" gap={1.5}>
          <Box display="flex" alignItems="center">
            {detection.source === 'video' ? (
              <VideoCall color="primary" fontSize="small" />
            ) : (
              <Mic color="secondary" fontSize="small" />
            )}
          </Box>
          <Typography
            variant="body2"
            color="text.secondary"
            sx={{ minWidth: 65 }}
          >
            {formatLocalTime(detection.start_time)}
          </Typography>
          <Chip
            label={`${Math.round(detection.confidence * 100)}%`}
            size="small"
            color={detection.source === 'video' ? 'primary' : 'secondary'}
            sx={{
              height: 24,
              '& .MuiChip-label': { px: 1, fontSize: '0.75rem' },
            }}
          />
          <Typography
            variant="body2"
            color="text.secondary"
            sx={{ ml: 'auto' }}
          >
            {(() => {
              const sec = Math.round(
                (new Date(detection.end_time).getTime() -
                  new Date(detection.start_time).getTime()) /
                  1000,
              );
              return sec >= 0 ? formatDuration(sec) : '—';
            })()}
          </Typography>
          {detection.source === 'video' && detection.id && (
            <Tooltip
              title={
                inaturalistShareEnabled
                  ? t('common.iNaturalist')
                  : t('common.loginRequiredForExport')
              }
            >
              <span>
                <IconButton
                  size="small"
                  onClick={handleINaturalist}
                  disabled={loading || !inaturalistShareEnabled}
                  sx={{ p: 0.5 }}
                  aria-label={t('common.iNaturalist')}
                >
                  <Share fontSize="small" />
                </IconButton>
              </span>
            </Tooltip>
          )}
        </Box>
      </CardActionArea>
      <Snackbar
        open={!!errorMsg}
        autoHideDuration={6000}
        onClose={() => setErrorMsg(null)}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      >
        <Alert
          severity="error"
          variant="filled"
          elevation={6}
          onClose={() => setErrorMsg(null)}
        >
          {errorMsg}
        </Alert>
      </Snackbar>
      {isLastInGroup && <Box mx={1.5} my={1} />}
    </Box>
  );
};

const groupDetectionsByVideo = (detections: SpeciesVisit['detections']) => {
  return detections.reduce<SpeciesVisit['detections'][]>((acc, detection) => {
    if (
      acc.length === 0 ||
      acc[acc.length - 1][0].video_id !== detection.video_id
    ) {
      acc.push([detection]);
    } else {
      acc[acc.length - 1].push(detection);
    }
    return acc;
  }, []);
};

export interface VisitCardProps {
  visit: SpeciesVisit;
  compact?: boolean;
  showDateTime?: boolean;
}

export const VisitCard = memo(function VisitCard({
  visit,
  compact = false,
  showDateTime = false,
}: VisitCardProps) {
  const { t } = useTranslation();
  const { canEdit } = useProtectedArea();
  const quickCorrectionOnly = true;
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const location = useLocation();
  const [expanded, setExpanded] = useState(false);
  const [editingNickname, setEditingNickname] = useState(false);
  const [nicknameDraft, setNicknameDraft] = useState('');
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saveSuccess, setSaveSuccess] = useState<string | null>(null);
  const nickname =
    (visit.individual_nickname && String(visit.individual_nickname).trim()) || '';
  const firstVideoDetectionId = (visit.detections ?? []).find(
    (d) => d.source === 'video' && d.id,
  )?.id;
  const firstVideoId = (visit.detections ?? []).find((d) => d.video_id)?.video_id;
  const birdProfileId = getVisitBirdProfileId(visit);
  const nicknameMutation = useMutation({
    mutationFn: (value: string | null) =>
      updateDetectionNickname(Number(firstVideoDetectionId), value),
    onSuccess: () => {
      invalidateLocalSpeciesEditCaches(queryClient, firstVideoId);
      setSaveSuccess(t('video.nicknameSaved'));
    },
  });
  const deleteVisitMutation = useMutation({
    mutationFn: () => deleteVisit(Number(visit.id), { source: 'timeline' }),
    onSuccess: () => {
      invalidateLocalSpeciesEditCaches(queryClient, firstVideoId);
      setSaveSuccess(t('visitCard.deleteVisitSuccess'));
    },
    onError: (err) => {
      setSaveError(getApiErrorMessage(err, t('errors.loadSightings')));
    },
  });
  const behaviorLabels = [
    ...new Set(
      (visit.behavior_events ?? [])
        .map((e) => String(e.label || '').trim().toLowerCase())
        .filter(Boolean),
    ),
  ];
  const behaviorText = behaviorLabels.join(', ');
  const detections = visit.detections ?? [];
  const bestConfidence = detections.length
    ? Math.max(...detections.map((d) => Number(d.confidence) || 0))
    : null;
  const videoDetections = detections.filter((d) => d.source === 'video').length;
  const audioDetections = detections.filter((d) => d.source === 'audio').length;
  const detectionSourcesLabel =
    audioDetections > 0
      ? t('visitCard.sourceMix', {
          video: videoDetections,
          audio: audioDetections,
        })
      : t('visitCard.sourceVideoOnly', { count: videoDetections });

  const startDateTime = new Date(visit.start_time);
  const isToday = new Date().toDateString() === startDateTime.toDateString();

  const formatDateTime = () => {
    if (isToday) {
      return t('visitCard.todayAt', {
        time: formatLocalTime(startDateTime),
      });
    }
    return formatLocalDateTime(startDateTime);
  };

  const onNicknameSave = async () => {
    if (!firstVideoDetectionId || !canEdit) return;
    setSaveError(null);
    try {
      const cleaned = nicknameDraft.trim();
      await nicknameMutation.mutateAsync(cleaned.length ? cleaned : null);
      setEditingNickname(false);
    } catch (err) {
      setSaveError(getApiErrorMessage(err, t('errors.loadSightings')));
    }
  };

  return (
    <Card>
      <CardContent sx={{ '&:last-child': { pb: 2 } }}>
        <Box display="flex" alignItems="flex-start" gap={2}>
          <SpeciesIcon
            speciesName={visit.species.name}
            imageUrl={visit.species.image_url}
            size={compact ? 44 : 48}
          />
          <Box flex={1} minWidth={0}>
            <Box display="flex" alignItems="center" gap={1}>
              <Box flex={1}>
                <Typography
                  variant={compact ? 'body1' : 'h6'}
                  component="div"
                  sx={{
                    lineHeight: compact ? 1.4 : 1.5,
                    wordBreak: 'break-word',
                  }}
                >
                  {visit.species.name}
                </Typography>
                {(nickname || behaviorText) && (
                  <Box display="flex" alignItems="center" gap={0.5} flexWrap="wrap">
                    <Typography variant="body2" color="text.secondary">
                      {nickname ? `${t('video.nickname')}: ${nickname}` : ''}
                      {nickname && behaviorText ? ' • ' : ''}
                      {behaviorText ? `${t('video.behavior')}: ${behaviorText}` : ''}
                    </Typography>
                    {nickname && firstVideoDetectionId && canEdit ? (
                      <>
                        <UnlinkBirdProfileButton
                          detectionId={Number(firstVideoDetectionId)}
                          videoId={firstVideoId}
                          profileName={nickname}
                        />
                        {birdProfileId ? (
                          <DeleteBirdProfileButton
                            profileId={birdProfileId}
                            profileName={nickname}
                            onDeleted={() =>
                              invalidateLocalSpeciesEditCaches(
                                queryClient,
                                firstVideoId,
                              )
                            }
                          />
                        ) : null}
                      </>
                    ) : null}
                  </Box>
                )}
                {firstVideoDetectionId && canEdit && !quickCorrectionOnly && (
                  <Box mt={0.5}>
                    {!editingNickname ? (
                      <Button
                        size="small"
                        onClick={() => {
                          setEditingNickname(true);
                          setNicknameDraft(nickname);
                        }}
                      >
                        {t('video.editNickname')}
                      </Button>
                    ) : (
                      <Stack direction="row" spacing={1} alignItems="center">
                        <TextField
                          size="small"
                          label={t('video.nickname')}
                          value={nicknameDraft}
                          inputProps={{ maxLength: 64 }}
                          onChange={(e) => setNicknameDraft(e.target.value)}
                        />
                        <Button
                          size="small"
                          variant="contained"
                          disabled={nicknameMutation.isPending}
                          onClick={onNicknameSave}
                        >
                          {t('unknowns.apply')}
                        </Button>
                        <Button
                          size="small"
                          onClick={() => setEditingNickname(false)}
                        >
                          {t('common.cancel')}
                        </Button>
                      </Stack>
                    )}
                  </Box>
                )}
                {showDateTime && (
                  <Typography
                    variant="body2"
                    color="text.secondary"
                    sx={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 0.5,
                      mt: 0.5,
                    }}
                  >
                    <CalendarToday sx={{ fontSize: 14 }} />
                    {formatDateTime()}
                  </Typography>
                )}
              </Box>
              <Tooltip
                title={
                  expanded
                    ? t('timeline.collapseVisitDetails')
                    : t('timeline.expandVisitDetails')
                }
              >
                <IconButton
                  size="small"
                  onClick={() => setExpanded(!expanded)}
                  sx={{ mt: -0.5 }}
                  aria-expanded={expanded}
                  aria-label={
                    expanded
                      ? t('timeline.collapseVisitDetails')
                      : t('timeline.expandVisitDetails')
                  }
                >
                  {expanded ? <ExpandLess /> : <ExpandMore />}
                </IconButton>
              </Tooltip>
            </Box>
            <Box display="flex" gap={1.5} mt={1.5} flexWrap="wrap">
              {bestConfidence != null ? (
                <Chip
                  label={t('visitCard.bestConfidence', {
                    value: Math.round(bestConfidence * 100),
                  })}
                  size="small"
                  color={bestConfidence >= 0.7 ? 'success' : 'default'}
                  sx={{ height: 28 }}
                />
              ) : null}
              <Chip
                label={t('visitCard.detectionsCount', {
                  count: detections.length,
                })}
                size="small"
                variant="outlined"
                sx={{ height: 28 }}
              />
              <Chip
                label={detectionSourcesLabel}
                size="small"
                variant="outlined"
                sx={{ height: 28 }}
              />
              {visit.timeline_kind !== 'unlinked_video' ? (
                <Chip
                  icon={
                    <Box display="flex" alignItems="center">
                      <Groups sx={{ fontSize: 18 }} />
                    </Box>
                  }
                  label={visit.max_simultaneous}
                  size="small"
                  sx={{ height: 28 }}
                />
              ) : (
                <Chip
                  label={t('visitCard.recordingWithoutVisit')}
                  size="small"
                  color="default"
                  variant="outlined"
                  sx={{ height: 28 }}
                />
              )}
              {canEdit && visit.timeline_kind !== 'unlinked_video' && visit.id > 0 ? (
                <Button
                  size="small"
                  color="error"
                  variant="outlined"
                  startIcon={<DeleteOutline fontSize="small" />}
                  disabled={deleteVisitMutation.isPending}
                  onClick={() => {
                    if (
                      !window.confirm(
                        t('visitCard.deleteVisitConfirm', {
                          name: visit.species.name,
                        }),
                      )
                    ) {
                      return;
                    }
                    deleteVisitMutation.mutate();
                  }}
                >
                  {t('visitCard.deleteVisit')}
                </Button>
              ) : null}
              {(() => {
                const sec =
                  visit.video_duration_seconds != null &&
                  visit.video_duration_seconds > 0
                    ? visit.video_duration_seconds
                    : visit.total_recording_seconds;
                return sec != null && sec > 0 ? (
                  <Chip
                    icon={
                      <Box display="flex" alignItems="center">
                        <VideoCall sx={{ fontSize: 18 }} />
                      </Box>
                    }
                    label={formatDuration(sec)}
                    size="small"
                    sx={{ height: 28 }}
                    title={t('visitCard.recordingTime')}
                  />
                ) : null;
              })()}
              {visit.weather?.temp && (
                <Chip
                  icon={
                    <Box display="flex" alignItems="center">
                      <Thermostat sx={{ fontSize: 18 }} />
                    </Box>
                  }
                  label={`${visit.weather.temp}°C`}
                  size="small"
                  sx={{ height: 28 }}
                />
              )}
              {visit.scales && (
                <Tooltip title={t('videoInfo.scalesEstimateHint')}>
                  <Chip
                    icon={
                      <Box display="flex" alignItems="center">
                        <MonitorWeightIcon sx={{ fontSize: 18 }} />
                      </Box>
                    }
                    label={t('videoInfo.scalesEstimateValue', {
                      value: visit.scales.display_value,
                      unit: visit.scales.display_unit,
                    })}
                    size="small"
                    sx={{ height: 28 }}
                  />
                </Tooltip>
              )}
            </Box>
          </Box>
        </Box>
        <Collapse in={expanded} timeout="auto">
          <Box mt={2}>
            {groupDetectionsByVideo(visit.detections ?? []).map(
              (group, groupIndex) => {
                const vid = group[0]?.video_id;
                return (
                  <Box key={`group-${groupIndex}-${vid ?? 'x'}`}>
                    {group.map((detection, index) => (
                      <DetectionItem
                        key={`${detection.video_id}-${index}`}
                        detection={detection}
                        speciesName={visit.species.name}
                        inaturalistShareEnabled={canEdit}
                        onClick={() =>
                          navigate(`/videos/${detection.video_id}`, {
                            state: {
                              from: `${location.pathname}${location.search}`,
                              ...(visit.timeline_kind !== 'unlinked_video' &&
                              visit.id > 0
                                ? { visitId: visit.id }
                                : {}),
                            },
                          })
                        }
                        isLastInGroup={index === group.length - 1}
                      />
                    ))}
                  </Box>
                );
              },
            )}
          </Box>
        </Collapse>
      </CardContent>
      <Snackbar
        open={!!saveError}
        autoHideDuration={6000}
        onClose={() => setSaveError(null)}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      >
        <Alert
          severity="error"
          variant="filled"
          elevation={6}
          onClose={() => setSaveError(null)}
        >
          {saveError}
        </Alert>
      </Snackbar>
      <Snackbar
        open={!!saveSuccess}
        autoHideDuration={3000}
        onClose={() => setSaveSuccess(null)}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      >
        <Alert
          severity="success"
          variant="filled"
          elevation={6}
          onClose={() => setSaveSuccess(null)}
        >
          {saveSuccess}
        </Alert>
      </Snackbar>
    </Card>
  );
});
