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
import Button from '@mui/material/Button';
import IconButton from '@mui/material/IconButton';
import Tooltip from '@mui/material/Tooltip';
import Share from '@mui/icons-material/Share';
import EditIcon from '@mui/icons-material/Edit';
import Snackbar from '@mui/material/Snackbar';
import Alert from '@mui/material/Alert';
import FormControl from '@mui/material/FormControl';
import InputLabel from '@mui/material/InputLabel';
import MenuItem from '@mui/material/MenuItem';
import Select from '@mui/material/Select';
import { Link as RouterLink } from 'react-router-dom';
import { VideoSpecies } from '../../types';
import { labelToUniqueHexColor } from '../../util';
import { SpeciesIcon } from '../../components/SpeciesIcon';
import { useProtectedArea } from '../../contexts/ProtectedAreaContext';
import {
  resolveImageUrl,
  downloadDetectionCropForINaturalist,
  updateDetectionSpecies,
  mergeVideoSpecies,
  fetchBirdDirectory,
  getApiErrorMessage,
} from '../../api/api';
import { invalidateLocalSpeciesEditCaches } from '../../api/invalidateLocalSpeciesCaches';

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
        <Alert severity="error" onClose={() => setErrorMsg(null)}>
          {errorMsg}
        </Alert>
      </Snackbar>
    </>
  );
};

interface DetectedSpeciesProps {
  species: VideoSpecies[];
  videoId?: string | number;
}

export const DetectedSpecies: React.FC<DetectedSpeciesProps> = ({
  species = [],
  videoId,
}) => {
  const { t } = useTranslation();
  const safeSpecies = species ?? [];
  const { canEdit } = useProtectedArea();
  const queryClient = useQueryClient();

  const { data: speciesList = [] } = useQuery({
    queryKey: ['species'],
    queryFn: () => fetchBirdDirectory(),
    staleTime: 5 * 60 * 1000,
  });

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

  const [editingGroupKey, setEditingGroupKey] = useState<string | null>(null);
  const [selectedSpeciesId, setSelectedSpeciesId] = useState<number | ''>('');
  const [mergeSpeciesId, setMergeSpeciesId] = useState<number | ''>('');
  const [correctError, setCorrectError] = useState<string | null>(null);
  const [correctSuccess, setCorrectSuccess] = useState<string | null>(null);

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
    return null;
  }

  return (
    <>
      <Box sx={{ mt: 3 }}>
        <Typography variant="h6" gutterBottom>
          {t('video.speciesInVideo')}
        </Typography>
        {groupedSpecies.length >= 2 && videoId && canEdit && (
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
                sx={{ minWidth: 200 }}
                disabled={!canEdit}
              >
                <InputLabel id="video-merge-species-label">
                  {t('video.mergeAllToSpecies')}
                </InputLabel>
                <Select
                  labelId="video-merge-species-label"
                  value={mergeSpeciesId}
                  label={t('video.mergeAllToSpecies')}
                  onChange={(e) => {
                    const v = e.target.value;
                    setMergeSpeciesId(v === '' ? '' : Number(v));
                  }}
                >
                  {speciesList.map((s) => (
                    <MenuItem key={s.id} value={s.id}>
                      {s.name}
                    </MenuItem>
                  ))}
                </Select>
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
                  <Typography variant="subtitle1" noWrap>
                    {group.species_name}
                  </Typography>
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
                    const providerLabels: Record<string, string> = {
                      yolo: t('video.detectionProviderYolo'),
                      frigate: t('video.detectionProviderFrigate'),
                      birdnet_mqtt: t('video.detectionProviderBirdnetMqtt'),
                    };
                    return providers.length > 0 ? (
                      <Typography variant="body2" color="text.secondary">
                        {t('video.detectionSource')}:{' '}
                        {providers
                          .map((p) => (p ? (providerLabels[p] ?? p) : ''))
                          .filter(Boolean)
                          .join(', ')}
                      </Typography>
                    ) : null;
                  })()}
                  <Typography variant="body2" color="text.secondary">
                    {t('video.confidence')}: {group.confidenceRange}
                  </Typography>
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
                    {(() => {
                      const bestDet = group.detections
                        .filter((d) => d.source === 'video' && d.id)
                        .sort(
                          (a, b) => (b.confidence || 0) - (a.confidence || 0),
                        )[0];
                      return bestDet ? (
                        <INaturalistButton
                          detectionId={bestDet.id!}
                          speciesName={group.species_name}
                          disabled={!canEdit}
                        />
                      ) : null;
                    })()}
                    {editingGroupKey !== String(group.species_id) && (
                      <Tooltip
                        title={canEdit ? t('unknowns.correctSpecies') : ''}
                      >
                        <span>
                          <Button
                            size="small"
                            startIcon={<EditIcon fontSize="small" />}
                            onClick={() => {
                              setEditingGroupKey(String(group.species_id));
                              setSelectedSpeciesId(group.species_id);
                            }}
                            disabled={!canEdit}
                          >
                            {t('unknowns.correctSpecies')}
                          </Button>
                        </span>
                      </Tooltip>
                    )}
                  </Box>
                  {editingGroupKey === String(group.species_id) && (
                    <Stack
                      spacing={1}
                      sx={{ width: '100%', minWidth: 0, mt: 0.5 }}
                    >
                      <FormControl
                        fullWidth
                        size="small"
                        disabled={!canEdit}
                        sx={{ minWidth: 0 }}
                      >
                        <InputLabel
                          id={`video-correct-species-${group.species_id}`}
                        >
                          {t('unknowns.correctSpecies')}
                        </InputLabel>
                        <Select
                          labelId={`video-correct-species-${group.species_id}`}
                          value={selectedSpeciesId}
                          label={t('unknowns.correctSpecies')}
                          renderValue={(v: number | string) => {
                            if (v === '' || v === undefined) return '';
                            const id = Number(v);
                            const row = speciesList.find(
                              (s) => Number(s.id) === id,
                            );
                            return row?.name ?? `#${id}`;
                          }}
                          onChange={(e) => {
                            const v = e.target.value;
                            setSelectedSpeciesId(v === '' ? '' : Number(v));
                          }}
                          MenuProps={{ PaperProps: { sx: { maxHeight: 360 } } }}
                        >
                          {speciesList.map((s) => (
                            <MenuItem key={s.id} value={s.id}>
                              {s.name}
                            </MenuItem>
                          ))}
                        </Select>
                      </FormControl>
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
                </CardActions>
              </Card>
            </Grid>
          ))}
        </Grid>
      </Box>
      <Snackbar
        open={!!correctError}
        autoHideDuration={6000}
        onClose={() => setCorrectError(null)}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      >
        <Alert severity="error" onClose={() => setCorrectError(null)}>
          {correctError}
        </Alert>
      </Snackbar>
      <Snackbar
        open={!!correctSuccess}
        autoHideDuration={4000}
        onClose={() => setCorrectSuccess(null)}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      >
        <Alert severity="success" onClose={() => setCorrectSuccess(null)}>
          {correctSuccess}
        </Alert>
      </Snackbar>
    </>
  );
};
