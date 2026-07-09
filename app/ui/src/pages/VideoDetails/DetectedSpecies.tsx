import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import Box from '@mui/material/Box';
import Grid from '@mui/material/Grid2';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';
import Card from '@mui/material/Card';
import CardContent from '@mui/material/CardContent';
import CardMedia from '@mui/material/CardMedia';
import CardActions from '@mui/material/CardActions';
import Autocomplete from '@mui/material/Autocomplete';
import Button from '@mui/material/Button';
import IconButton from '@mui/material/IconButton';
import Tooltip from '@mui/material/Tooltip';
import Share from '@mui/icons-material/Share';
import EditIcon from '@mui/icons-material/Edit';
import DeleteOutline from '@mui/icons-material/DeleteOutline';
import Snackbar from '@mui/material/Snackbar';
import Alert from '@mui/material/Alert';
import FormControl from '@mui/material/FormControl';
import TextField from '@mui/material/TextField';
import Chip from '@mui/material/Chip';
import { Link as RouterLink } from 'react-router-dom';
import { VideoSpecies } from '../../types';
import { labelToUniqueHexColor } from '../../util';
import { detectionProviderLabel } from '../../util/detectionProviderLabel';
import { SpeciesIcon } from '../../components/SpeciesIcon';
import { UnlinkBirdProfileButton } from '../../components/UnlinkBirdProfileButton';
import { DeleteBirdProfileButton } from '../../components/DeleteBirdProfileButton';
import { formatBirdProfileOptionLabel } from '../../components/filters/BirdProfileFilterAutocomplete';
import { SpeciesCorrectionAutocomplete } from '../../components/filters/SpeciesCorrectionAutocomplete';
import { useProtectedArea } from '../../contexts/ProtectedAreaContext';
import { SettingsPasswordDialog } from '../../components/SettingsPasswordDialog';
import { getApiErrorMessage, resolveImageUrl } from '../../api/api';
import { downloadDetectionCropForINaturalist } from '../../api/dataset';
import {
  assignDetectionBirdProfile,
  createBirdProfile,
  fetchBirdProfileSuggestLinks,
  fetchBirdProfiles,
  mergeBirdProfiles,
  recordBirdProfileLinkFeedback,
  setDetectionSemanticReview,
  updateDetectionSpecies,
  deleteDetection,
  type BirdProfileLinkCandidate,
} from '../../api/speciesOverviewDetections';
import { mergeVideoSpecies, type VideoReidMatchItem } from '../../api/video';
import { queryKeys } from '../../api/queryKeys';
import { invalidateLocalSpeciesEditCaches } from '../../api/invalidateLocalSpeciesCaches';
import { formatTimeMmSs } from '../../utils/timeUtils';

interface GroupedSpecies {
  species_id: number;
  species_name: string;
  image_url?: string;
  detections: VideoSpecies[];
  confidenceRange: string;
  totalDuration: number;
}

const INaturalistButton = ({
  detectionId,
  speciesName,
  disabled: gateDisabled,
}: {
  detectionId: number;
  speciesName: string;
  /** Нет сессии админа/оператора — как экспорт на таймлайне. */
  disabled?: boolean;
}) => {
  const { t } = useTranslation();
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const handleClick = async () => {
    if (gateDisabled) return;
    setLoading(true);
    setErrorMsg(null);
    try {
      await downloadDetectionCropForINaturalist(detectionId, speciesName);
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : String(err));
      console.error('iNaturalist export failed:', err);
    } finally {
      setLoading(false);
    }
  };
  return (
    <>
      <Tooltip
        title={
          gateDisabled
            ? t('common.loginRequiredForExport')
            : t('common.iNaturalist')
        }
      >
        <span>
          <IconButton
            size="small"
            onClick={handleClick}
            disabled={loading || !!gateDisabled}
            aria-label={t('common.iNaturalist')}
          >
            <Share fontSize="small" />
          </IconButton>
        </span>
      </Tooltip>
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
    </>
  );
};

interface DetectedSpeciesProps {
  species: VideoSpecies[];
  videoId?: string | number;
  reidMatchByDetectionId?: Record<number, VideoReidMatchItem>;
}

const ProfileSuggestLinksBlock = ({
  detectionId,
  speciesId,
  anchorProfileId,
  dismissed,
  onDismiss,
  onMerged,
}: {
  detectionId: number;
  speciesId: number;
  anchorProfileId: number | null;
  dismissed: boolean;
  onDismiss: () => void;
  onMerged: (message: string) => void;
}) => {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const { data, isLoading } = useQuery({
    queryKey: queryKeys.birdProfiles.suggestLinks(detectionId, anchorProfileId),
    queryFn: () =>
      fetchBirdProfileSuggestLinks(anchorProfileId, {
        video_species_id: detectionId,
        species_id: speciesId,
        limit: 6,
      }),
    enabled: !dismissed,
    staleTime: 30_000,
  });
  const mergeMutation = useMutation({
    mutationFn: ({
      targetProfileId,
      sourceProfileId,
    }: {
      targetProfileId: number;
      sourceProfileId: number;
    }) => mergeBirdProfiles(targetProfileId, sourceProfileId),
    onSuccess: (payload) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.birdProfiles.all });
      onMerged(
        t('video.profileMergeSuccess', {
          name: payload.display_name,
          count: payload.merged_detections,
        }),
      );
    },
  });
  const feedbackMutation = useMutation({
    mutationFn: recordBirdProfileLinkFeedback,
  });

  if (dismissed || isLoading || !data?.available || !data.candidates?.length) {
    return null;
  }

  const handleReject = async (candidate: BirdProfileLinkCandidate) => {
    await feedbackMutation.mutateAsync({
      action: 'reject',
      candidate_profile_id: candidate.profile_id,
      anchor_profile_id: anchorProfileId,
      video_species_id: detectionId,
      similarity: candidate.similarity,
    });
    onDismiss();
  };

  const handleMerge = async (candidate: BirdProfileLinkCandidate) => {
    const targetId = anchorProfileId ?? candidate.profile_id;
    const sourceId =
      anchorProfileId && anchorProfileId !== candidate.profile_id
        ? candidate.profile_id
        : null;
    if (!sourceId || targetId === sourceId) {
      await assignDetectionBirdProfile(detectionId, candidate.profile_id);
      await feedbackMutation.mutateAsync({
        action: 'confirm',
        candidate_profile_id: candidate.profile_id,
        anchor_profile_id: anchorProfileId,
        video_species_id: detectionId,
        similarity: candidate.similarity,
      });
      onMerged(t('video.profileLinkedInVideo', { count: 1 }));
      return;
    }
    await mergeMutation.mutateAsync({
      targetProfileId: targetId,
      sourceProfileId: sourceId,
    });
    await feedbackMutation.mutateAsync({
      action: 'confirm',
      candidate_profile_id: candidate.profile_id,
      anchor_profile_id: anchorProfileId,
      video_species_id: detectionId,
      similarity: candidate.similarity,
    });
  };

  return (
    <Alert severity="info" variant="outlined" sx={{ mt: 0.5 }}>
      <Typography variant="caption" display="block" fontWeight={700}>
        {t('video.profileMaybeSameBird')}
      </Typography>
      <Stack spacing={0.75} sx={{ mt: 0.75 }}>
        {data.candidates.map((candidate) => (
          <Box
            key={`suggest-${candidate.profile_id}`}
            sx={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: 1,
              flexWrap: 'wrap',
            }}
          >
            <Typography variant="caption">
              {candidate.display_name} • {candidate.similarity_percent}%
              {candidate.tier === 'auto' ? ` • ${t('video.profileAutoLinkTier')}` : ''}
            </Typography>
            <Stack direction="row" spacing={0.5}>
              <Button
                size="small"
                variant="contained"
                disabled={mergeMutation.isPending || feedbackMutation.isPending}
                onClick={() => handleMerge(candidate)}
              >
                {t('video.profileMergeButton')}
              </Button>
              <Button
                size="small"
                variant="text"
                disabled={feedbackMutation.isPending}
                onClick={() => handleReject(candidate)}
              >
                {t('video.profileDismissSuggest')}
              </Button>
            </Stack>
          </Box>
        ))}
      </Stack>
    </Alert>
  );
};

export const DetectedSpecies: React.FC<DetectedSpeciesProps> = ({
  species = [],
  videoId,
  reidMatchByDetectionId = {},
}) => {
  const { t } = useTranslation();
  const safeSpecies = species ?? [];
  const { canEdit, requiresPassword, setUnlocked } = useProtectedArea();
  const [showPasswordDialog, setShowPasswordDialog] = useState(false);
  const quickCorrectionOnly = true;
  const allowNicknameEdit = canEdit;
  const queryClient = useQueryClient();

  const { data: birdProfilesResponse } = useQuery({
    queryKey: queryKeys.birdProfiles.videoDetails,
    queryFn: () => fetchBirdProfiles({ limit: 200 }),
    enabled: canEdit,
    staleTime: 60 * 1000,
  });
  const birdProfiles = birdProfilesResponse?.items ?? [];

  const correctMutation = useMutation({
    mutationFn: ({
      detectionId,
      speciesId,
    }: {
      detectionId: number;
      speciesId: number;
    }) =>
      // Сервер при source=video без apply_scope снова даёт legacy_fanout; явно передаём для ясности.
      updateDetectionSpecies(detectionId, speciesId, 'video', 'legacy_fanout'),
    onSuccess: (data) => {
      invalidateLocalSpeciesEditCaches(queryClient, videoId);
      if (data?.message === 'Species unchanged') {
        setCorrectSuccess(t('video.speciesUnchanged'));
      } else if (data?.updated_count && data.updated_count > 1) {
        setCorrectSuccess(
          t('video.correctedInVideos', { count: data.updated_count }),
        );
      } else {
        setCorrectSuccess(t('unknowns.corrected'));
      }
    },
  });

  const mergeMutation = useMutation({
    mutationFn: (speciesId: number) => mergeVideoSpecies(videoId!, speciesId),
    onSuccess: (data) => {
      invalidateLocalSpeciesEditCaches(queryClient, videoId);
      setCorrectSuccess(data?.message ?? t('unknowns.corrected'));
    },
  });

  const assignProfileMutation = useMutation({
    mutationFn: ({ detectionId, profileId }: { detectionId: number; profileId: number }) =>
      assignDetectionBirdProfile(detectionId, profileId),
    onSuccess: (data) => {
      invalidateLocalSpeciesEditCaches(queryClient, videoId);
      setCorrectSuccess(
        t('video.profileLinkedInVideo', { count: Number(data?.updated_count || 1) }),
      );
    },
  });
  const createProfileMutation = useMutation({
    mutationFn: ({
      displayName,
      speciesId,
      avatarUrl,
    }: {
      displayName: string;
      speciesId?: number | null;
      avatarUrl?: string | null;
    }) =>
      createBirdProfile({
        display_name: displayName,
        species_id: speciesId,
        avatar_url: avatarUrl,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.birdProfiles.all });
    },
  });
  const semanticReviewMutation = useMutation({
    mutationFn: ({ detectionId }: { detectionId: number }) =>
      setDetectionSemanticReview(detectionId, {
        semantic_review_required: true,
        source: 'video_details',
      }),
    onSuccess: () => {
      invalidateLocalSpeciesEditCaches(queryClient, videoId);
      queryClient.invalidateQueries({ queryKey: queryKeys.unknowns.all });
      setCorrectSuccess(t('video.semanticReviewQueued'));
    },
  });

  const deleteDetectionMutation = useMutation({
    mutationFn: (detectionId: number) =>
      deleteDetection(detectionId, { source: 'video', reason: 'false_positive' }),
    onSuccess: () => {
      invalidateLocalSpeciesEditCaches(queryClient, videoId);
      if (videoId != null) {
        queryClient.invalidateQueries({
          queryKey: queryKeys.video.detectionFrames(String(videoId)),
        });
      }
      setCorrectSuccess(t('video.deleteDetectionSuccess'));
    },
    onError: (err) => {
      setCorrectError(getApiErrorMessage(err, t('errors.loadSightings')));
    },
  });

  const [editingGroupKey, setEditingGroupKey] = useState<string | null>(null);
  const [selectedSpeciesId, setSelectedSpeciesId] = useState<number | ''>('');
  const [mergeSpeciesId, setMergeSpeciesId] = useState<number | ''>('');
  const [correctError, setCorrectError] = useState<string | null>(null);
  const [correctSuccess, setCorrectSuccess] = useState<string | null>(null);
  const [profileDraft, setProfileDraft] = useState<Record<string, string>>({});
  const [profileSelection, setProfileSelection] = useState<Record<string, number | null>>({});
  const [dismissedSuggestKeys, setDismissedSuggestKeys] = useState<Record<string, boolean>>({});

  const handleCorrectGroup = async (group: GroupedSpecies) => {
    if (selectedSpeciesId === '') return;
    const nextId = Number(selectedSpeciesId);
    if (!Number.isFinite(nextId) || nextId === Number(group.species_id)) return;
    setCorrectError(null);
    const bestDet = group.detections
      .filter((d) => d.source === 'video' && d.id)
      .sort((a, b) => (b.confidence || 0) - (a.confidence || 0))[0];
    if (!bestDet?.id) {
      setCorrectError(t('video.correctNoDetectionId'));
      return;
    }
    try {
      await correctMutation.mutateAsync({
        detectionId: bestDet.id,
        speciesId: nextId,
      });
      setEditingGroupKey(null);
      setSelectedSpeciesId('');
    } catch (err) {
      setCorrectError(getApiErrorMessage(err, t('errors.loadSightings')));
    }
  };

  const handleMergeAll = async () => {
    if (mergeSpeciesId === '' || !videoId) return;
    const mid = Number(mergeSpeciesId);
    if (!Number.isFinite(mid)) return;
    setCorrectError(null);
    try {
      await mergeMutation.mutateAsync(mid);
      setMergeSpeciesId('');
    } catch (err) {
      setCorrectError(getApiErrorMessage(err, t('errors.loadSightings')));
    }
  };

  // Group species by species_id and calculate stats
  const groupedSpecies = safeSpecies
    .filter((s) => s.source === 'video')
    .reduce((groups: GroupedSpecies[], sp) => {
      let group = groups.find((g) => g.species_id === sp.species_id);
      if (!group) {
        group = {
          species_id: sp.species_id,
          species_name: sp.species_name,
          image_url: sp.image_url,
          detections: [],
          confidenceRange: '',
          totalDuration: 0,
        };
        groups.push(group);
      }
      group.detections.push(sp);
      group.totalDuration += Math.max(0, sp.end_time - sp.start_time);
      return groups;
    }, []);

  // Calculate confidence range for each group
  groupedSpecies.forEach((group) => {
    const confidences = group.detections.map((d) => d.confidence * 100);
    if (confidences.length === 0) {
      group.confidenceRange = '—';
      return;
    }
    const min = Math.min(...confidences).toFixed(0);
    const max = Math.max(...confidences).toFixed(0);
    group.confidenceRange = min === max ? `${min}%` : `${min}% - ${max}%`;
  });

  if (groupedSpecies.length === 0) {
    return (
      <Box sx={{ mt: 3 }}>
        <Typography variant="h6" gutterBottom>
          {t('video.speciesInVideo')}
        </Typography>
        <Alert severity="info" variant="outlined">
          <Typography variant="subtitle2">{t('video.speciesEmptyTitle')}</Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
            {t('video.speciesEmptyHint')}
          </Typography>
        </Alert>
      </Box>
    );
  }

  return (
    <>
      <Box sx={{ mt: 3 }}>
        <Typography variant="h6" gutterBottom>
          {t('video.speciesInVideo')}
        </Typography>
        {!canEdit && requiresPassword && groupedSpecies.length > 0 && (
          <Alert severity="info" variant="outlined" sx={{ mb: 2 }}>
            <Stack
              direction={{ xs: 'column', sm: 'row' }}
              spacing={1}
              alignItems={{ xs: 'flex-start', sm: 'center' }}
              justifyContent="space-between"
            >
              <Box>
                <Typography variant="body2" fontWeight={600}>
                  {t('video.guestCorrectionTitle')}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  {t('video.guestCorrectionHint')}
                </Typography>
              </Box>
              <Button
                size="small"
                variant="outlined"
                onClick={() => setShowPasswordDialog(true)}
              >
                {t('video.unlockToCorrect')}
              </Button>
            </Stack>
          </Alert>
        )}
        {groupedSpecies.length >= 2 && videoId && canEdit && !quickCorrectionOnly && (
          <Box
            sx={{
              mb: 2,
              p: 2,
              borderRadius: 2,
              bgcolor: 'action.hover',
              border: '1px solid',
              borderColor: 'divider',
            }}
          >
            <Typography
              variant="subtitle2"
              color="text.secondary"
              sx={{ mb: 1 }}
            >
              {t('video.mergeAllHint')}
            </Typography>
            <Box
              sx={{
                display: 'flex',
                alignItems: 'center',
                gap: 1,
                flexWrap: 'wrap',
              }}
            >
              <FormControl
                size="small"
                sx={{ minWidth: 240, flex: 1 }}
                disabled={!canEdit}
              >
                <SpeciesCorrectionAutocomplete
                  value={mergeSpeciesId}
                  onChange={setMergeSpeciesId}
                  disabled={!canEdit}
                  label={t('video.mergeAllToSpecies')}
                />
              </FormControl>
              <Button
                size="small"
                variant="contained"
                disabled={
                  mergeSpeciesId === '' || mergeMutation.isPending || !canEdit
                }
                onClick={handleMergeAll}
              >
                {mergeMutation.isPending ? '...' : t('unknowns.apply')}
              </Button>
            </Box>
          </Box>
        )}
        <Grid container spacing={2}>
          {groupedSpecies.map((group) => (
            <Grid
              size={{ xs: 12, sm: 6, md: 4 }}
              key={group.species_id}
              sx={{ minWidth: 0 }}
            >
              <Card
                sx={{
                  height: '100%',
                  display: 'flex',
                  flexDirection: 'column',
                  border: `2px solid ${labelToUniqueHexColor(group.species_name)}`,
                  overflow: 'hidden',
                  minWidth: 0,
                }}
              >
                <Box
                  sx={{
                    aspectRatio: '16/10',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    bgcolor: 'action.hover',
                    overflow: 'hidden',
                  }}
                >
                  {group.image_url ? (
                    <CardMedia
                      component="img"
                      alt={group.species_name}
                      image={resolveImageUrl(group.image_url)}
                      sx={{
                        width: '100%',
                        height: '100%',
                        objectFit: 'cover',
                        objectPosition: 'center top',
                      }}
                    />
                  ) : (
                    <SpeciesIcon speciesName={group.species_name} size={64} />
                  )}
                </Box>
                <CardContent sx={{ py: 1.5 }}>
                  <Typography variant="subtitle1" noWrap title={group.species_name}>
                    {group.species_name}
                  </Typography>
                  {(() => {
                    const bestDet = group.detections
                      .filter((d) => d.source === 'video' && d.id)
                      .sort((a, b) => (b.confidence || 0) - (a.confidence || 0))[0];
                    const nickname = bestDet?.individual_nickname?.trim();
                    return nickname ? (
                      <Typography variant="body2" color="primary" sx={{ mt: 0.25 }}>
                        {t('video.nicknameLabel')}: {nickname}
                      </Typography>
                    ) : null;
                  })()}
                  <Typography variant="body2" color="text.secondary">
                    {group.detections.length}{' '}
                    {group.detections.length > 1
                      ? t('video.detections')
                      : t('video.detection')}{' '}
                    • {Math.max(0, Math.round(group.totalDuration))}s
                  </Typography>
                  {(() => {
                    const providers = [
                      ...new Set(
                        group.detections
                          .map((d) => d.detection_provider)
                          .filter(Boolean),
                      ),
                    ];
                    return providers.length > 0 ? (
                      <Typography variant="body2" color="text.secondary">
                        {t('video.detectionSource')}:{' '}
                        {providers
                          .map((p) =>
                            p
                              ? detectionProviderLabel(t, p, {
                                  technical: canEdit,
                                })
                              : '',
                          )
                          .filter(Boolean)
                          .join(', ')}
                      </Typography>
                    ) : null;
                  })()}
                  <Typography variant="body2" color="text.secondary">
                    {t('video.confidence')}: {group.confidenceRange}
                  </Typography>
                  {(() => {
                    const videoDetections = group.detections.filter(
                      (d) => d.source === 'video',
                    );
                    if (videoDetections.length === 0) return null;
                    const distances = videoDetections
                      .map((d) => d.welfare_distance)
                      .filter(
                        (v): v is number =>
                          v != null && Number.isFinite(Number(v)),
                      );
                    const maxDistance =
                      distances.length > 0
                        ? Math.max(...distances.map(Number))
                        : null;
                    const hasAnomaly = videoDetections.some(
                      (d) => d.review_reason === 'welfare_anomaly',
                    );
                    const label =
                      maxDistance != null
                        ? t('video.welfareDistanceChip', {
                            distance: maxDistance.toFixed(1),
                          })
                        : hasAnomaly
                          ? t('video.welfareAnomalyChip')
                          : t('video.welfareUnavailableChip');
                    const scoringHint = group.detections[0]?.scoring_hint;
                    return (
                      <Stack spacing={0.5} sx={{ mt: 0.5 }}>
                        <Tooltip
                          title={
                            maxDistance != null || hasAnomaly
                              ? t('video.welfareAnomalyHint')
                              : t('video.welfareUnavailableHint')
                          }
                          placement="top"
                        >
                          <Chip
                            size="small"
                            color={maxDistance != null || hasAnomaly ? 'warning' : 'default'}
                            variant="outlined"
                            label={label}
                            sx={{ alignSelf: 'flex-start' }}
                          />
                        </Tooltip>
                        {scoringHint ? (
                          <Tooltip
                            title={
                              <Box component="span" sx={{ whiteSpace: 'pre-line' }}>
                                {t('video.scoringHintTooltip', {
                                  provider: scoringHint.primary_provider ?? '—',
                                  weights: Object.entries(
                                    scoringHint.arbiter_weights ?? {},
                                  )
                                    .map(([k, v]) => `${k}=${v}`)
                                    .join(', '),
                                })}
                              </Box>
                            }
                          >
                            <Typography
                              component="button"
                              type="button"
                              variant="caption"
                              color="text.secondary"
                              display="block"
                              aria-label={t('video.scoringWhySpecies')}
                              sx={{
                                p: 0,
                                m: 0,
                                border: 0,
                                background: 'none',
                                font: 'inherit',
                                textAlign: 'left',
                                cursor: 'help',
                                textDecoration: 'underline dotted',
                                textUnderlineOffset: 2,
                              }}
                            >
                              {t('video.scoringWhySpecies')}
                            </Typography>
                          </Tooltip>
                        ) : null}
                      </Stack>
                    );
                  })()}
                  {canEdit &&
                  group.detections.filter((d) => d.source === 'video' && d.id).length >
                    0 ? (
                    <Box sx={{ mt: 1.5, width: '100%' }}>
                      <Typography variant="subtitle2" gutterBottom>
                        {t('video.detectionTracksTitle')}
                      </Typography>
                      <Stack spacing={0.75}>
                        {[...group.detections]
                          .filter((d) => d.source === 'video' && d.id)
                          .sort((a, b) => a.start_time - b.start_time)
                          .map((det) => (
                            <Stack
                              key={det.id}
                              direction="row"
                              alignItems="center"
                              spacing={1}
                              flexWrap="wrap"
                              sx={{
                                py: 0.5,
                                px: 1,
                                borderRadius: 1,
                                bgcolor: 'action.hover',
                              }}
                            >
                              <Typography variant="body2" sx={{ flex: 1, minWidth: 0 }}>
                                {t('video.detectionTrackRow', {
                                  track:
                                    det.track_id != null ? String(det.track_id) : '—',
                                  start: formatTimeMmSs(det.start_time),
                                  end: formatTimeMmSs(det.end_time),
                                  conf: Math.round((det.confidence || 0) * 100),
                                })}
                              </Typography>
                              <Button
                                size="small"
                                color="error"
                                variant="outlined"
                                startIcon={<DeleteOutline fontSize="small" />}
                                disabled={deleteDetectionMutation.isPending}
                                onClick={() => {
                                  const did = det.id;
                                  if (!did) return;
                                  if (
                                    !window.confirm(
                                      t('video.deleteDetectionConfirm', {
                                        track:
                                          det.track_id != null
                                            ? String(det.track_id)
                                            : '—',
                                        start: formatTimeMmSs(det.start_time),
                                        end: formatTimeMmSs(det.end_time),
                                      }),
                                    )
                                  ) {
                                    return;
                                  }
                                  deleteDetectionMutation.mutate(did);
                                }}
                              >
                                {t('video.deleteDetection')}
                              </Button>
                            </Stack>
                          ))}
                      </Stack>
                      <Typography variant="caption" color="text.secondary" display="block" sx={{ mt: 0.5 }}>
                        {t('video.deleteDetectionHint')}
                      </Typography>
                    </Box>
                  ) : null}
                  {(() => {
                    const bestDet = group.detections
                      .filter((d) => d.source === 'video' && d.id)
                      .sort((a, b) => (b.confidence || 0) - (a.confidence || 0))[0];
                    if (!bestDet?.id) return null;
                    const match = reidMatchByDetectionId[bestDet.id];
                    if (!match || match.decision !== 'suggest_same_individual') return null;
                    return (
                      <Box sx={{ mt: 1 }}>
                        <Alert severity="info" variant="outlined" sx={{ py: 0.5 }}>
                          <Typography variant="caption" display="block">
                            {t('video.possibleSameBird')}
                          </Typography>
                          <Typography variant="caption" color="text.secondary">
                            {t('video.similarityPercent', {
                              value: Math.round(match.similarity * 100),
                            })}
                            {canEdit &&
                            typeof match.effective_threshold === 'number'
                              ? ` • τ≈${Math.round(match.effective_threshold * 100)}%`
                              : ''}
                            {match.cross_camera ? ` • ${t('video.reidCrossCameraHint')}` : ''}
                            {match.candidate_nickname
                              ? ` • ${t('video.nicknameLabel')}: ${match.candidate_nickname}`
                              : ''}
                          </Typography>
                          {match.candidate_video_id ? (
                            <Box sx={{ mt: 0.5 }}>
                              <Chip
                                size="small"
                                label={`${t('video.relatedVideo')}: #${match.candidate_video_id}`}
                                component={RouterLink}
                                clickable
                                to={`/videos/${match.candidate_video_id}`}
                              />
                            </Box>
                          ) : null}
                        </Alert>
                      </Box>
                    );
                  })()}
                </CardContent>
                <CardActions
                  sx={{
                    pt: 0,
                    flexWrap: 'wrap',
                    gap: 0.5,
                    alignItems: 'flex-start',
                    flexDirection: 'column',
                    alignSelf: 'stretch',
                    px: 2,
                    pb: 1.5,
                  }}
                >
                  <Box
                    sx={{
                      display: 'flex',
                      flexWrap: 'wrap',
                      gap: 0.5,
                      width: '100%',
                    }}
                  >
                    <Button
                      size="small"
                      component={RouterLink}
                      to={`/species/${group.species_id}`}
                    >
                      {t('video.learnMore')}
                    </Button>
                    {!quickCorrectionOnly &&
                      canEdit &&
                      (() => {
                        const bestDet = group.detections
                          .filter((d) => d.source === 'video' && d.id)
                          .sort(
                            (a, b) =>
                              (b.confidence || 0) - (a.confidence || 0),
                          )[0];
                        return bestDet ? (
                          <INaturalistButton
                            detectionId={bestDet.id!}
                            speciesName={group.species_name}
                          />
                        ) : null;
                      })()}
                    {canEdit &&
                      editingGroupKey !== String(group.species_id) && (
                        <Button
                          size="small"
                          startIcon={<EditIcon fontSize="small" />}
                          onClick={() => {
                            setEditingGroupKey(String(group.species_id));
                            setSelectedSpeciesId(group.species_id);
                          }}
                        >
                          {t('unknowns.correctSpecies')}
                        </Button>
                      )}
                  </Box>
                  {editingGroupKey === String(group.species_id) && (
                    <Stack
                      spacing={1}
                      sx={{ width: '100%', minWidth: 0, mt: 0.5 }}
                    >
                      <SpeciesCorrectionAutocomplete
                        value={selectedSpeciesId}
                        onChange={setSelectedSpeciesId}
                        disabled={!canEdit}
                        excludeSpeciesId={group.species_id}
                        label={t('unknowns.correctSpecies')}
                      />
                      <Stack
                        direction="row"
                        spacing={1}
                        flexWrap="wrap"
                        useFlexGap
                        sx={{ width: '100%' }}
                      >
                        <Button
                          size="small"
                          variant="contained"
                          disabled={
                            selectedSpeciesId === '' ||
                            !Number.isFinite(Number(selectedSpeciesId)) ||
                            Number(selectedSpeciesId) ===
                              Number(group.species_id) ||
                            correctMutation.isPending ||
                            !canEdit
                          }
                          onClick={() => handleCorrectGroup(group)}
                        >
                          {correctMutation.isPending
                            ? '...'
                            : t('unknowns.apply')}
                        </Button>
                        <Button
                          size="small"
                          onClick={() => {
                            setEditingGroupKey(null);
                            setSelectedSpeciesId('');
                          }}
                        >
                          {t('common.cancel')}
                        </Button>
                      </Stack>
                    </Stack>
                  )}
                  {allowNicknameEdit && (() => {
                    const bestDet = group.detections
                      .filter((d) => d.source === 'video' && d.id)
                      .sort((a, b) => (b.confidence || 0) - (a.confidence || 0))[0];
                    if (!bestDet?.id) return null;
                    const key = String(bestDet.id);
                    const selectedProfileId =
                      profileSelection[key] ?? bestDet.bird_profile_id ?? null;
                    const selectedProfile =
                      birdProfiles.find((p) => Number(p.id) === Number(selectedProfileId)) ||
                      null;
                    const draftName =
                      profileDraft[key] ??
                      selectedProfile?.display_name ??
                      bestDet.bird_profile_name ??
                      bestDet.individual_nickname ??
                      '';
                    const filteredOptions = birdProfiles.filter(
                      (p) =>
                        !draftName ||
                        p.display_name.toLowerCase().includes(draftName.toLowerCase()),
                    );
                    return (
                      <Stack spacing={1} sx={{ width: '100%', minWidth: 0, mt: 1 }}>
                        <Autocomplete
                          freeSolo
                          options={filteredOptions}
                          value={selectedProfile}
                          getOptionLabel={(option) =>
                            typeof option === 'string' ? option : option.display_name
                          }
                          onChange={(_, value) => {
                            if (value && typeof value !== 'string') {
                              setProfileSelection((prev) => ({ ...prev, [key]: value.id }));
                              setProfileDraft((prev) => ({
                                ...prev,
                                [key]: value.display_name,
                              }));
                            } else {
                              setProfileSelection((prev) => ({ ...prev, [key]: null }));
                            }
                          }}
                          inputValue={draftName}
                          onInputChange={(_, value) =>
                            setProfileDraft((prev) => ({
                              ...prev,
                              [key]: value,
                            }))
                          }
                          renderInput={(params) => (
                            <TextField
                              {...params}
                              size="small"
                              label={t('video.profileField')}
                              placeholder={t('video.profileFieldPlaceholder')}
                            />
                          )}
                        />
                        {selectedProfile ? (
                          <Stack direction="row" spacing={1} alignItems="center">
                            {selectedProfile.avatar_url ? (
                              <CardMedia
                                component="img"
                                image={resolveImageUrl(selectedProfile.avatar_url)}
                                alt={selectedProfile.display_name}
                                sx={{ width: 28, height: 28, borderRadius: 1 }}
                              />
                            ) : null}
                            <Chip
                              size="small"
                              label={`${selectedProfile.display_name} • ${selectedProfile.status}`}
                              color="info"
                              variant="outlined"
                            />
                            <UnlinkBirdProfileButton
                              detectionId={bestDet.id!}
                              videoId={
                                videoId != null ? Number(videoId) : undefined
                              }
                              profileName={selectedProfile.display_name}
                              onUnlinked={() => {
                                setProfileSelection((prev) => ({
                                  ...prev,
                                  [key]: null,
                                }));
                                setProfileDraft((prev) => ({
                                  ...prev,
                                  [key]: '',
                                }));
                                invalidateLocalSpeciesEditCaches(queryClient, videoId);
                              }}
                            />
                            <DeleteBirdProfileButton
                              profileId={Number(selectedProfile.id)}
                              profileName={formatBirdProfileOptionLabel(
                                selectedProfile,
                              )}
                              onDeleted={() => {
                                setProfileSelection((prev) => ({
                                  ...prev,
                                  [key]: null,
                                }));
                                setProfileDraft((prev) => ({
                                  ...prev,
                                  [key]: '',
                                }));
                                invalidateLocalSpeciesEditCaches(queryClient, videoId);
                              }}
                            />
                          </Stack>
                        ) : null}
                        <ProfileSuggestLinksBlock
                          detectionId={bestDet.id!}
                          speciesId={group.species_id}
                          anchorProfileId={
                            profileSelection[key] ?? bestDet.bird_profile_id ?? null
                          }
                          dismissed={!!dismissedSuggestKeys[key]}
                          onDismiss={() =>
                            setDismissedSuggestKeys((prev) => ({ ...prev, [key]: true }))
                          }
                          onMerged={(message) => {
                            setCorrectSuccess(message);
                            invalidateLocalSpeciesEditCaches(queryClient, videoId);
                            queryClient.invalidateQueries({ queryKey: queryKeys.birdProfiles.all });
                          }}
                        />
                        <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                          <Button
                            size="small"
                            variant="contained"
                            disabled={
                              assignProfileMutation.isPending ||
                              !Number.isFinite(Number(profileSelection[key] ?? selectedProfileId))
                            }
                            onClick={() =>
                              assignProfileMutation.mutate({
                                detectionId: bestDet.id!,
                                profileId: Number(profileSelection[key] ?? selectedProfileId),
                              })
                            }
                          >
                            {t('video.profileLinkButton')}
                          </Button>
                          <Button
                            size="small"
                            variant="outlined"
                            disabled={
                              createProfileMutation.isPending ||
                              !draftName.trim()
                            }
                            onClick={async () => {
                              const created = await createProfileMutation.mutateAsync({
                                displayName: draftName.trim(),
                                speciesId: group.species_id,
                                avatarUrl: group.image_url || null,
                              });
                              setProfileSelection((prev) => ({ ...prev, [key]: created.id }));
                              await assignProfileMutation.mutateAsync({
                                detectionId: bestDet.id!,
                                profileId: created.id,
                              });
                            }}
                          >
                            {t('video.profileCreateAndLinkButton')}
                          </Button>
                          <Button
                            size="small"
                            color="warning"
                            variant="outlined"
                            disabled={semanticReviewMutation.isPending}
                            onClick={() =>
                              semanticReviewMutation.mutate({ detectionId: bestDet.id! })
                            }
                          >
                            {t('video.semanticReviewButton')}
                          </Button>
                        </Box>
                        {bestDet.semantic_conflict ? (
                          <Alert severity="warning" variant="outlined">
                            <Typography variant="caption" display="block">
                              {bestDet.review_reason === 'semantic_review_required'
                                ? t('unknowns.reviewReasonOperatorFlagged')
                                : bestDet.review_reason === 'classifier_uncertainty'
                                  ? t('unknowns.reviewReasonClassifierUncertainty')
                                  : bestDet.review_reason === 'low_confidence'
                                    ? t('unknowns.reviewReasonLowConfidence')
                                    : bestDet.review_reason === 'reid_no_match'
                                      ? t('unknowns.reviewReasonReidNoMatch')
                                    : bestDet.review_reason === 'welfare_anomaly'
                                      ? t('unknowns.reviewReasonWelfareAnomaly')
                                      : bestDet.review_reason === 'generic_bird'
                                        ? t('unknowns.reviewReasonGenericBird')
                                        : bestDet.review_reason === 'bbox_rejected'
                                          ? t('unknowns.reviewReasonBboxRejected')
                                          : bestDet.review_reason === 'unknown_label'
                                            ? t('unknowns.reviewReasonUnknownLabel')
                                            : bestDet.review_reason ===
                                                'detect_first_anchor_only'
                                              ? t('unknowns.reviewReasonDetectFirstAnchor')
                                              : t('video.semanticReviewQueued')}
                            </Typography>
                          </Alert>
                        ) : null}
                      </Stack>
                    );
                  })()}
                </CardActions>
              </Card>
            </Grid>
          ))}
        </Grid>
      </Box>
      <SettingsPasswordDialog
        open={showPasswordDialog}
        onSuccess={(role) => {
          setUnlocked(true, role);
          setShowPasswordDialog(false);
        }}
        onClose={() => setShowPasswordDialog(false)}
      />
      <Snackbar
        open={!!correctError}
        autoHideDuration={6000}
        onClose={() => setCorrectError(null)}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      >
        <Alert
          severity="error"
          variant="filled"
          elevation={6}
          onClose={() => setCorrectError(null)}
        >
          {correctError}
        </Alert>
      </Snackbar>
      <Snackbar
        open={!!correctSuccess}
        autoHideDuration={4000}
        onClose={() => setCorrectSuccess(null)}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      >
        <Alert
          severity="success"
          variant="filled"
          elevation={6}
          onClose={() => setCorrectSuccess(null)}
        >
          {correctSuccess}
        </Alert>
      </Snackbar>
    </>
  );
};
