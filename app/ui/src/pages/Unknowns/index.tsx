import { useState, useEffect, useMemo, type ReactNode } from 'react';
import {
  Link as RouterLink,
  useLocation,
  useNavigate,
  useSearchParams,
} from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import CircularProgress from '@mui/material/CircularProgress';
import Card from '@mui/material/Card';
import CardContent from '@mui/material/CardContent';
import CardActionArea from '@mui/material/CardActionArea';
import Chip from '@mui/material/Chip';
import Button from '@mui/material/Button';
import Checkbox from '@mui/material/Checkbox';
import FormControlLabel from '@mui/material/FormControlLabel';
import FormControl from '@mui/material/FormControl';
import InputLabel from '@mui/material/InputLabel';
import Select from '@mui/material/Select';
import MenuItem from '@mui/material/MenuItem';
import Alert from '@mui/material/Alert';
import Dialog from '@mui/material/Dialog';
import DialogTitle from '@mui/material/DialogTitle';
import DialogContent from '@mui/material/DialogContent';
import DialogActions from '@mui/material/DialogActions';
import TextField from '@mui/material/TextField';
import List from '@mui/material/List';
import ListItem from '@mui/material/ListItem';
import ListItemText from '@mui/material/ListItemText';
import Stack from '@mui/material/Stack';
import Divider from '@mui/material/Divider';
import { AdapterDayjs } from '@mui/x-date-pickers/AdapterDayjs';
import { LocalizationProvider } from '@mui/x-date-pickers/LocalizationProvider';
import { DatePicker } from '@mui/x-date-pickers/DatePicker';
import dayjs, { Dayjs } from 'dayjs';
import { type TimeOfDay } from '../../utils/timeUtils';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import VideoFileIcon from '@mui/icons-material/VideoFile';
import Snackbar from '@mui/material/Snackbar';
import Tooltip from '@mui/material/Tooltip';
import { getApiErrorMessage, resolveImageUrl } from '../../api/api';
import { fetchUnknownsForObserverDate } from '../../api/timeline';
import type { UnknownDetection } from '../../api/timeline';
import {
  confirmDetection,
  deleteReviewQueueVideos,
  fetchBirdDirectory,
  speciesDirectoryItems,
  fetchRecentCorrections,
  previewReviewQueueDelete,
  updateDetectionSpecies,
  type ReviewQueueDeletePreview,
} from '../../api/speciesOverviewDetections';
import { queryKeys } from '../../api/queryKeys';
import { formatLocalDateTime } from '../../util';
import { SpeciesIcon } from '../../components/SpeciesIcon';
import { useProtectedArea } from '../../contexts/ProtectedAreaContext';
import { PageHelp } from '../../components/PageHelp';
import { unknownsHelpConfig } from '../../page-help-config';

function reviewReasonLabel(t: (key: string) => string, reason?: string) {
  switch (reason) {
    case 'low_confidence':
      return t('unknowns.reviewReasonLowConfidence');
    case 'generic_bird':
      return t('unknowns.reviewReasonGenericBird');
    case 'classifier_uncertainty':
      return t('unknowns.reviewReasonClassifierUncertainty');
    case 'semantic_review_required':
      return t('unknowns.reviewReasonOperatorFlagged');
    case 'bbox_rejected':
      return t('unknowns.reviewReasonBboxRejected');
    default:
      return '';
  }
}

function reviewStateLabel(t: (key: string) => string, state?: string) {
  switch (state) {
    case 'pending':
      return t('unknowns.reviewStatePending');
    case 'semantic_review_required':
      return t('unknowns.reviewStateExpert');
    case 'reviewed':
      return t('unknowns.reviewStateReviewed');
    default:
      return t('unknowns.reviewStatePending');
  }
}

export function UnknownCard({
  detection,
  speciesList,
  onCorrect,
  onConfirm,
  canEdit,
  videoListReturnPath,
  selected,
  onToggleSelected,
}: {
  detection: UnknownDetection;
  speciesList: { id: number; name: string }[];
  onCorrect: (detectionId: number, speciesId: number) => void;
  onConfirm: (detectionId: number) => void;
  canEdit: boolean;
  videoListReturnPath: string;
  selected: boolean;
  onToggleSelected: (detectionId: number) => void;
}) {
  const { t } = useTranslation();
  const [selectedSpeciesId, setSelectedSpeciesId] = useState<number | ''>('');
  const [correcting, setCorrecting] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const reviewReason = reviewReasonLabel(t, detection.review_reason);

  const pendingSpeciesChange =
    selectedSpeciesId !== '' &&
    Number(selectedSpeciesId) !== Number(detection.species_id);

  const handleCorrect = async () => {
    if (selectedSpeciesId === '' || correcting) return;
    const sid = Number(selectedSpeciesId);
    if (!Number.isFinite(sid)) return;
    setCorrecting(true);
    try {
      await onCorrect(detection.id, sid);
      setSelectedSpeciesId('');
    } finally {
      setCorrecting(false);
    }
  };

  const handleConfirm = async () => {
    if (confirming) return;
    setConfirming(true);
    try {
      await onConfirm(detection.id);
    } finally {
      setConfirming(false);
    }
  };

  return (
    <Card sx={{ mb: 2 }}>
      <CardContent>
        <Box display="flex" flexWrap="wrap" gap={2} alignItems="flex-start">
          <Box
            sx={{
              width: 64,
              height: 64,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              bgcolor: 'action.hover',
              borderRadius: 1,
              overflow: 'hidden',
            }}
          >
            {detection.image_url ? (
              <Box
                component="img"
                src={resolveImageUrl(detection.image_url)}
                alt={detection.species_name}
                sx={{ width: '100%', height: '100%', objectFit: 'cover' }}
              />
            ) : (
              <SpeciesIcon speciesName={detection.species_name} size={40} />
            )}
          </Box>
          <Box flex={1} minWidth={0}>
            <Typography variant="subtitle1" fontWeight={600}>
              {detection.species_name}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              {formatLocalDateTime(detection.start_time)}
            </Typography>
            <Box display="flex" gap={1} flexWrap="wrap" sx={{ mt: 0.5 }}>
              <Chip
                label={`${Math.round(detection.confidence * 100)}%`}
                size="small"
                color="warning"
              />
              {detection.detection_provider && (
                <Chip
                  label={detection.detection_provider}
                  size="small"
                  variant="outlined"
                />
              )}
              {detection.review_state && (
                <Chip
                  label={reviewStateLabel(t, detection.review_state)}
                  size="small"
                  color="info"
                  variant="outlined"
                />
              )}
              {reviewReason && (
                <Chip
                  label={reviewReason}
                  size="small"
                  color="warning"
                  variant="outlined"
                />
              )}
            </Box>
          </Box>
          <CardActionArea
            component={RouterLink}
            to={`/videos/${detection.video_id}`}
            state={{ from: videoListReturnPath }}
            sx={{
              flexShrink: 0,
              borderRadius: 1,
              maxWidth: 120,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              p: 1.5,
            }}
          >
            <Box
              display="flex"
              flexDirection="column"
              alignItems="center"
              gap={0.5}
            >
              <VideoFileIcon color="primary" />
              <Typography variant="caption">
                {t('unknowns.viewVideo')}
              </Typography>
            </Box>
          </CardActionArea>
          <Box display="flex" flexDirection="column" gap={1} minWidth={200}>
            {canEdit && (
              <FormControlLabel
                control={
                  <Checkbox
                    checked={selected}
                    onChange={() => onToggleSelected(detection.id)}
                  />
                }
                label={t('unknowns.bulkSelect')}
              />
            )}
            {canEdit && (
              <>
                <FormControl size="small" fullWidth>
                  <InputLabel
                    id={`unknowns-correct-species-${detection.id}`}
                    shrink
                  >
                    {t('unknowns.correctSpecies')}
                  </InputLabel>
                  <Select
                    labelId={`unknowns-correct-species-${detection.id}`}
                    displayEmpty
                    value={selectedSpeciesId === '' ? '' : selectedSpeciesId}
                    label={t('unknowns.correctSpecies')}
                    renderValue={(v: number | string) => {
                      if (v === '' || v === undefined) {
                        return (
                          <Typography
                            component="span"
                            variant="body2"
                            color="text.secondary"
                          >
                            {t('unknowns.speciesSelectPlaceholder')}
                          </Typography>
                        );
                      }
                      const id = Number(v);
                      const row = speciesList.find((s) => Number(s.id) === id);
                      return row?.name ?? String(v);
                    }}
                    onChange={(e) => {
                      const v = e.target.value;
                      setSelectedSpeciesId(v === '' ? '' : Number(v));
                    }}
                    MenuProps={{ PaperProps: { sx: { maxHeight: 360 } } }}
                  >
                    <MenuItem value="">
                      <em>{t('unknowns.speciesSelectPlaceholder')}</em>
                    </MenuItem>
                    {speciesList.map((s) => (
                      <MenuItem key={s.id} value={s.id}>
                        {s.name}
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>
                <Button
                  variant="contained"
                  size="small"
                  disabled={
                    selectedSpeciesId === '' ||
                    !Number.isFinite(Number(selectedSpeciesId)) ||
                    Number(selectedSpeciesId) ===
                      Number(detection.species_id) ||
                    correcting
                  }
                  onClick={handleCorrect}
                >
                  {correcting ? '...' : t('unknowns.apply')}
                </Button>
                <Tooltip
                  title={
                    pendingSpeciesChange
                      ? t('unknowns.confirmBlockedPendingApply')
                      : t('unknowns.confirmCorrectHelp')
                  }
                >
                  <span>
                    <Button
                      variant="outlined"
                      size="small"
                      disabled={confirming || pendingSpeciesChange}
                      onClick={handleConfirm}
                    >
                      {confirming ? '...' : t('unknowns.confirmCorrect')}
                    </Button>
                  </span>
                </Tooltip>
              </>
            )}
          </Box>
        </Box>
      </CardContent>
    </Card>
  );
}

export type UnknownsPageProps = {
  /** Ряд чипов переключения режима (Записи / На проверке) — под заголовком страницы. */
  afterTitleSlot?: ReactNode;
};

export function UnknownsPage({ afterTitleSlot }: UnknownsPageProps) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const location = useLocation();
  const [searchParams, setSearchParams] = useSearchParams();
  const queueParam = (searchParams.get('queue') || '').trim().toLowerCase();
  const reviewReasonParam = (searchParams.get('review_reason') || '').trim().toLowerCase();
  const expertQueueEnabled = queueParam === 'expert' || location.pathname === '/review';
  const videoListReturnPath = `${location.pathname}${location.search}`;
  const queryClient = useQueryClient();
  const { canEdit } = useProtectedArea();

  const [selectedDate, setSelectedDate] = useState<Dayjs | null>(() => {
    const paramDate = searchParams.get('date');
    if (!paramDate) return dayjs().startOf('date');
    const parsed = dayjs(paramDate).startOf('date');
    return parsed.isValid() ? parsed : dayjs().startOf('date');
  });
  const [timeOfDay, setTimeOfDay] = useState<TimeOfDay>(() => {
    const value = (searchParams.get('time_of_day') || 'all')
      .trim()
      .toLowerCase();
    return ['all', 'night', 'morning', 'day', 'afternoon', 'evening'].includes(
      value,
    )
      ? (value as TimeOfDay)
      : 'all';
  });

  const unknownsListKey = useMemo(
    () =>
      queryKeys.unknowns.list(
        selectedDate?.format('YYYY-MM-DD') ?? '',
        timeOfDay,
        expertQueueEnabled ? 'expert' : 'default',
        reviewReasonParam || 'all',
      ),
    [selectedDate, timeOfDay, expertQueueEnabled, reviewReasonParam],
  );

  const {
    data: unknowns,
    isLoading,
    error,
  } = useQuery({
    queryKey: unknownsListKey,
    queryFn: () => {
      if (!selectedDate) return [];
      return fetchUnknownsForObserverDate(selectedDate.format('YYYY-MM-DD'), {
        timeOfDay,
        limit: 500,
        ...(expertQueueEnabled ? { queue: 'expert' as const } : {}),
        ...(reviewReasonParam ? { reviewReason: reviewReasonParam } : {}),
      });
    },
    enabled: !!selectedDate,
  });

  const { data: speciesList = [] } = useQuery({
    queryKey: queryKeys.species.directory,
    queryFn: async () => speciesDirectoryItems(await fetchBirdDirectory()),
    staleTime: 5 * 60 * 1000,
  });
  const { data: recentCorrections = [] } = useQuery({
    queryKey: queryKeys.corrections.recent,
    queryFn: () => fetchRecentCorrections(8),
    enabled: canEdit,
  });

  const [correctError, setCorrectError] = useState<string | null>(null);
  const [correctSuccess, setCorrectSuccess] = useState<string | null>(null);
  /** After correct/confirm: optional snackbar action to open this video (#81 phase B). */
  const [successVideoId, setSuccessVideoId] = useState<number | null>(null);
  const [selectedUnknownIds, setSelectedUnknownIds] = useState<number[]>([]);
  const [bulkPreview, setBulkPreview] =
    useState<ReviewQueueDeletePreview | null>(null);
  const [bulkConfirmText, setBulkConfirmText] = useState('');
  const [bulkActionError, setBulkActionError] = useState<string | null>(null);
  const [bulkDialogOpen, setBulkDialogOpen] = useState(false);

  const selectedUnknowns = useMemo(
    () =>
      (unknowns ?? []).filter((item) => selectedUnknownIds.includes(item.id)),
    [unknowns, selectedUnknownIds],
  );
  const selectedVideoIds = useMemo(
    () => [...new Set(selectedUnknowns.map((item) => item.video_id))],
    [selectedUnknowns],
  );
  const selectedDetectionCount = selectedUnknownIds.length;
  const selectedVideoCount = selectedVideoIds.length;

  const resolveVideoIdForDetection = (detectionId: number): number | null => {
    const list =
      queryClient.getQueryData<UnknownDetection[]>(unknownsListKey) ?? [];
    const row = list.find((u) => u.id === detectionId);
    return row?.video_id ?? null;
  };

  const clearSuccessSnackbar = () => {
    setCorrectSuccess(null);
    setSuccessVideoId(null);
  };

  const selectedDateKey = selectedDate?.format('YYYY-MM-DD');
  useEffect(() => {
    setSelectedUnknownIds([]);
    setBulkPreview(null);
    setBulkConfirmText('');
    setBulkActionError(null);
    setBulkDialogOpen(false);
  }, [selectedDateKey, timeOfDay]);

  useEffect(() => {
    if (!selectedDate) return;
    const dateStr = selectedDate.format('YYYY-MM-DD');
    if (
      searchParams.get('review') === '1' &&
      searchParams.get('date') === dateStr &&
      searchParams.get('time_of_day') === timeOfDay
    ) {
      return;
    }
    const next = new URLSearchParams(searchParams);
    next.set('review', '1');
    next.set('date', dateStr);
    next.set('time_of_day', timeOfDay);
    setSearchParams(next, { replace: true });
  }, [searchParams, selectedDate, setSearchParams, timeOfDay]);

  useEffect(() => {
    if (!unknowns || selectedUnknownIds.length === 0) return;
    const knownIds = new Set(unknowns.map((item) => item.id));
    const next = selectedUnknownIds.filter((id) => knownIds.has(id));
    if (next.length !== selectedUnknownIds.length) {
      setSelectedUnknownIds(next);
    }
  }, [unknowns, selectedUnknownIds]);

  const correctMutation = useMutation({
    mutationFn: ({
      detectionId,
      speciesId,
    }: {
      detectionId: number;
      speciesId: number;
    }) => updateDetectionSpecies(detectionId, speciesId, 'unknowns'),
    onSuccess: (data, variables) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.unknowns.all });
      queryClient.invalidateQueries({
        queryKey: queryKeys.timeline.unknownsCountAll,
      });
      queryClient.invalidateQueries({
        queryKey: queryKeys.timeline.speciesVisitsAll,
      });
      queryClient.invalidateQueries({ queryKey: queryKeys.overview.all });
      queryClient.invalidateQueries({
        queryKey: queryKeys.calendar.timelineTab,
      });
      queryClient.invalidateQueries({ queryKey: queryKeys.corrections.recent });
      const msg =
        data?.updated_count && data.updated_count > 1
          ? t('video.correctedInVideos', { count: data.updated_count })
          : t('unknowns.corrected');
      setSuccessVideoId(resolveVideoIdForDetection(variables.detectionId));
      setCorrectSuccess(msg);
    },
    onError: (err: unknown) => {
      setCorrectError(getApiErrorMessage(err, t('errors.loadSightings')));
    },
  });

  const confirmMutation = useMutation({
    mutationFn: (detectionId: number) =>
      confirmDetection(detectionId, 'unknowns'),
    onSuccess: (_data, detectionId) => {
      queryClient.setQueryData<UnknownDetection[] | undefined>(
        unknownsListKey,
        (prev) => (prev ?? []).filter((row) => row.id !== detectionId),
      );
      queryClient.invalidateQueries({ queryKey: queryKeys.unknowns.all });
      queryClient.invalidateQueries({
        queryKey: queryKeys.timeline.unknownsCountAll,
      });
      queryClient.invalidateQueries({
        queryKey: queryKeys.timeline.speciesVisitsAll,
      });
      queryClient.invalidateQueries({ queryKey: queryKeys.overview.all });
      queryClient.invalidateQueries({
        queryKey: queryKeys.calendar.timelineTab,
      });
      queryClient.invalidateQueries({ queryKey: queryKeys.corrections.recent });
      setSuccessVideoId(resolveVideoIdForDetection(detectionId));
      setCorrectSuccess(
        expertQueueEnabled
          ? t('unknowns.expertTaskDone')
          : t('unknowns.corrected'),
      );
    },
    onError: (err: unknown) => {
      setCorrectError(getApiErrorMessage(err, t('errors.loadSightings')));
    },
  });

  const previewBulkDeleteMutation = useMutation({
    mutationFn: async () => {
      if (!selectedDate) {
        throw new Error(t('unknowns.bulkDeleteNoDate'));
      }
      return previewReviewQueueDelete({
        date: selectedDate.format('YYYY-MM-DD'),
        timeOfDay,
        unknownIds: selectedUnknownIds,
      });
    },
    onSuccess: (data) => {
      setBulkPreview(data);
      setBulkConfirmText('');
      setBulkActionError(null);
      setBulkDialogOpen(true);
    },
    onError: (err: unknown) => {
      setBulkActionError(getApiErrorMessage(err, t('errors.loadSightings')));
    },
  });

  const deleteBulkMutation = useMutation({
    mutationFn: async () => {
      if (!selectedDate) {
        throw new Error(t('unknowns.bulkDeleteNoDate'));
      }
      return deleteReviewQueueVideos({
        date: selectedDate.format('YYYY-MM-DD'),
        timeOfDay,
        unknownIds: selectedUnknownIds,
        confirmText: bulkConfirmText.trim(),
      });
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: queryKeys.unknowns.all });
      await queryClient.invalidateQueries({
        queryKey: queryKeys.timeline.unknownsCountAll,
      });
      await queryClient.invalidateQueries({
        queryKey: queryKeys.timeline.speciesVisitsAll,
      });
      await queryClient.invalidateQueries({ queryKey: queryKeys.overview.all });
      await queryClient.invalidateQueries({
        queryKey: queryKeys.calendar.timelineTab,
      });
      await queryClient.invalidateQueries({
        queryKey: queryKeys.calendar.migration,
      });
      setSelectedUnknownIds([]);
      setBulkPreview(null);
      setBulkDialogOpen(false);
      setBulkConfirmText('');
      setBulkActionError(null);
    },
    onError: (err: unknown) => {
      setBulkActionError(
        getApiErrorMessage(err, t('unknowns.bulkDeleteFailed')),
      );
    },
  });

  const handleCorrect = async (detectionId: number, speciesId: number) => {
    setCorrectError(null);
    try {
      await correctMutation.mutateAsync({ detectionId, speciesId });
    } catch {
      // onError уже устанавливает correctError
    }
  };

  const handleConfirm = async (detectionId: number) => {
    setCorrectError(null);
    try {
      await confirmMutation.mutateAsync(detectionId);
    } catch {
      // onError уже устанавливает correctError
    }
  };

  const toggleUnknownSelection = (detectionId: number) => {
    setSelectedUnknownIds((current) => {
      if (current.includes(detectionId)) {
        return current.filter((id) => id !== detectionId);
      }
      return [...current, detectionId];
    });
  };

  const clearBulkSelection = () => {
    setSelectedUnknownIds([]);
    setBulkPreview(null);
    setBulkConfirmText('');
    setBulkActionError(null);
  };

  const openBulkPreview = async () => {
    setBulkActionError(null);
    if (!selectedUnknownIds.length) {
      setBulkActionError(t('unknowns.bulkDeleteNoSelection'));
      return;
    }
    try {
      await previewBulkDeleteMutation.mutateAsync();
    } catch {
      // onError handles message
    }
  };

  const handleBulkDelete = async () => {
    setBulkActionError(null);
    if (!bulkPreview) {
      setBulkActionError(t('unknowns.bulkDeletePreviewRequired'));
      return;
    }
    try {
      await deleteBulkMutation.mutateAsync();
    } catch {
      // onError handles message
    }
  };

  if (isLoading)
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
        <CircularProgress />
      </Box>
    );
  if (error)
    return (
      <Alert severity="error" variant="outlined">
        {t('timeline.errorLoad')}
      </Alert>
    );

  return (
    <>
      <PageHelp {...unknownsHelpConfig} />
      {afterTitleSlot}
      <Alert severity="info" variant="outlined" sx={{ mb: 2 }}>
        <Stack
          direction={{ xs: 'column', sm: 'row' }}
          spacing={1}
          alignItems={{ xs: 'flex-start', sm: 'center' }}
          justifyContent="space-between"
        >
          <Box>
            <Typography variant="body2" fontWeight={600}>
              {canEdit
                ? t('unknowns.roleSplitTitle')
                : t('unknowns.guestBrowseTitle')}
            </Typography>
            <Typography variant="caption" color="text.secondary">
              {canEdit
                ? t('unknowns.roleSplitHint')
                : t('unknowns.guestBrowseHint')}
            </Typography>
          </Box>
          {canEdit && (
            <Button
              component={RouterLink}
              to="/labelling"
              size="small"
              variant="outlined"
            >
              {t('unknowns.openGeometryQueue')}
            </Button>
          )}
        </Stack>
      </Alert>
      <Box
        display="flex"
        flexWrap="wrap"
        alignItems="center"
        gap={2}
        sx={{ mb: 3, '& > :not(style)': { minWidth: 160 } }}
      >
        <LocalizationProvider dateAdapter={AdapterDayjs}>
          <DatePicker
            label={t('timeline.selectDate')}
            value={selectedDate}
            onChange={(v) => setSelectedDate(v)}
            maxDate={dayjs()}
          />
        </LocalizationProvider>
        <FormControl sx={{ minWidth: 160 }}>
          <InputLabel id="unknowns-timeofday-label">
            {t('timeline.timeOfDay')}
          </InputLabel>
          <Select
            labelId="unknowns-timeofday-label"
            value={timeOfDay}
            onChange={(e) => setTimeOfDay(e.target.value as TimeOfDay)}
            label={t('timeline.timeOfDay')}
          >
            <MenuItem value="all">{t('timeline.timeAllDay')}</MenuItem>
            <MenuItem value="night">{t('timeline.timeNight')}</MenuItem>
            <MenuItem value="morning">{t('timeline.timeMorning')}</MenuItem>
            <MenuItem value="day">{t('timeline.timeDay')}</MenuItem>
            <MenuItem value="afternoon">{t('timeline.timeAfternoon')}</MenuItem>
            <MenuItem value="evening">{t('timeline.timeEvening')}</MenuItem>
          </Select>
        </FormControl>
      </Box>

      {canEdit && unknowns && unknowns.length > 0 && (
        <>
          {bulkActionError && !bulkDialogOpen && (
            <Alert
              severity="error"
              variant="outlined"
              sx={{ mb: 2 }}
              onClose={() => setBulkActionError(null)}
            >
              {bulkActionError}
            </Alert>
          )}
          <Alert severity="warning" variant="outlined" sx={{ mb: 2 }}>
            <Stack
              direction={{ xs: 'column', sm: 'row' }}
              spacing={1}
              alignItems={{ xs: 'flex-start', sm: 'center' }}
              justifyContent="space-between"
            >
              <Box>
                <Typography variant="body2" fontWeight={600}>
                  {t('unknowns.bulkDeleteSummary', {
                    detectionCount: selectedDetectionCount,
                    videoCount: selectedVideoCount,
                  })}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  {t('unknowns.bulkDeleteHint', {
                    phrase:
                      bulkPreview?.confirmation_phrase || 'permanent_full',
                  })}
                </Typography>
              </Box>
              <Stack direction="row" spacing={1} flexWrap="wrap">
                <Button
                  variant="outlined"
                  color="warning"
                  onClick={() => void openBulkPreview()}
                  disabled={
                    previewBulkDeleteMutation.isPending ||
                    selectedDetectionCount === 0
                  }
                >
                  {previewBulkDeleteMutation.isPending
                    ? t('unknowns.bulkDeletePreviewing')
                    : t('unknowns.bulkDeletePreview')}
                </Button>
                <Button
                  variant="text"
                  onClick={clearBulkSelection}
                  disabled={selectedDetectionCount === 0}
                >
                  {t('unknowns.bulkDeleteClear')}
                </Button>
              </Stack>
            </Stack>
          </Alert>
        </>
      )}

      {canEdit && recentCorrections.length > 0 && (
        <Alert severity="info" variant="outlined" sx={{ mb: 2 }}>
          <Typography variant="body2" sx={{ fontWeight: 600, mb: 0.5 }}>
            {t('unknowns.recentCorrectionsTitle')}
          </Typography>
          <Box component="ul" sx={{ m: 0, pl: 2 }}>
            {recentCorrections.slice(0, 5).map((row) => (
              <Typography component="li" variant="body2" key={row.id}>
                {formatLocalDateTime(row.created_at)} —{' '}
                {row.action === 'confirm_species'
                  ? t('unknowns.recentCorrectionConfirm')
                  : t('unknowns.recentCorrectionUpdate', {
                      from: row.from_species_name || t('common.na'),
                      to: row.to_species_name || t('common.na'),
                    })}{' '}
                ({row.source})
              </Typography>
            ))}
          </Box>
        </Alert>
      )}

      {unknowns?.length === 0 ? (
        <Alert severity="info" variant="outlined">
          {t('unknowns.empty')}
        </Alert>
      ) : (
        <Box
          sx={{
            mb: 2,
            display: 'flex',
            flexWrap: 'wrap',
            alignItems: 'center',
            gap: 2,
            justifyContent: 'space-between',
          }}
        >
          <Box>
            <Typography variant="body2" color="text.secondary">
              {t('unknowns.count', { count: unknowns?.length ?? 0 })}
            </Typography>
            {unknowns?.length === 500 && (
              <Typography
                variant="caption"
                color="text.secondary"
                display="block"
                sx={{ mt: 0.5 }}
              >
                {t('unknowns.limitReached')}
              </Typography>
            )}
          </Box>
          {canEdit && unknowns && unknowns.length > 0 && (
            <FormControlLabel
              control={
                <Checkbox
                  checked={
                    unknowns.length > 0 &&
                    selectedUnknownIds.length === unknowns.length
                  }
                  indeterminate={
                    selectedUnknownIds.length > 0 &&
                    selectedUnknownIds.length < unknowns.length
                  }
                  onChange={(_, checked) => {
                    if (checked) {
                      setSelectedUnknownIds(unknowns.map((u) => u.id));
                    } else {
                      setSelectedUnknownIds([]);
                    }
                  }}
                />
              }
              label={t('unknowns.bulkSelectAll')}
            />
          )}
        </Box>
      )}

      {unknowns?.map((d) => (
        <UnknownCard
          key={`${d.id}-${d.species_id}`}
          detection={d}
          speciesList={speciesList}
          onCorrect={handleCorrect}
          onConfirm={handleConfirm}
          canEdit={canEdit}
          videoListReturnPath={videoListReturnPath}
          selected={selectedUnknownIds.includes(d.id)}
          onToggleSelected={toggleUnknownSelection}
        />
      ))}
      <Dialog
        open={bulkDialogOpen}
        onClose={() => setBulkDialogOpen(false)}
        fullWidth
        maxWidth="md"
      >
        <DialogTitle>{t('unknowns.bulkDeleteDialogTitle')}</DialogTitle>
        <DialogContent dividers>
          {bulkActionError && (
            <Alert severity="error" variant="outlined" sx={{ mb: 2 }}>
              {bulkActionError}
            </Alert>
          )}
          {!bulkPreview ? (
            <Alert severity="info" variant="outlined">
              {t('unknowns.bulkDeletePreviewRequired')}
            </Alert>
          ) : (
            <Stack spacing={2}>
              <Alert severity="warning" variant="outlined">
                {t('unknowns.bulkDeleteDialogWarning', {
                  videoCount: bulkPreview.video_count,
                  unknownCount: bulkPreview.unknown_count,
                })}
              </Alert>
              {bulkPreview.missing_video_ids.length > 0 && (
                <Alert severity="info" variant="outlined">
                  {t('unknowns.bulkDeleteMissingVideos', {
                    count: bulkPreview.missing_video_ids.length,
                    ids: bulkPreview.missing_video_ids.join(', '),
                  })}
                </Alert>
              )}
              <TextField
                label={t('unknowns.bulkDeleteConfirmLabel')}
                value={bulkConfirmText}
                onChange={(e) => setBulkConfirmText(e.target.value)}
                helperText={t('unknowns.bulkDeleteConfirmHelp', {
                  phrase: bulkPreview.confirmation_phrase,
                })}
                fullWidth
              />
              <Divider />
              <List dense disablePadding>
                {bulkPreview.videos.map((video) => (
                  <ListItem
                    key={video.video_id}
                    alignItems="flex-start"
                    divider
                  >
                    <ListItemText
                      primary={t('unknowns.bulkDeleteVideoItem', {
                        videoId: video.video_id,
                        count: video.unknown_count,
                      })}
                      secondary={
                        <>
                          <Typography
                            component="span"
                            variant="body2"
                            color="text.secondary"
                          >
                            {video.video_path || t('common.na')}
                          </Typography>
                          <br />
                          <Typography
                            component="span"
                            variant="caption"
                            color="text.secondary"
                          >
                            {t('unknowns.bulkDeleteVideoMeta', {
                              species:
                                video.species_names.join(', ') ||
                                t('common.na'),
                              reasons:
                                video.review_reasons.join(', ') ||
                                t('common.na'),
                              fileExists: video.file_exists
                                ? t('common.yes')
                                : t('common.no'),
                            })}
                          </Typography>
                        </>
                      }
                    />
                  </ListItem>
                ))}
              </List>
            </Stack>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setBulkDialogOpen(false)}>
            {t('common.close')}
          </Button>
          <Button
            variant="contained"
            color="warning"
            onClick={() => void handleBulkDelete()}
            disabled={
              deleteBulkMutation.isPending ||
              !bulkPreview ||
              bulkConfirmText.trim() !== bulkPreview.confirmation_phrase
            }
          >
            {deleteBulkMutation.isPending
              ? t('unknowns.bulkDeleteRunning')
              : t('unknowns.bulkDeleteAction')}
          </Button>
        </DialogActions>
      </Dialog>
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
        autoHideDuration={successVideoId != null ? 10000 : 4000}
        onClose={clearSuccessSnackbar}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
        action={
          successVideoId != null ? (
            <Button
              color="inherit"
              size="small"
              onClick={() => {
                navigate(`/videos/${successVideoId}`, {
                  state: { from: videoListReturnPath },
                });
                clearSuccessSnackbar();
              }}
            >
              {t('unknowns.openVideoAfterCorrect')}
            </Button>
          ) : undefined
        }
      >
        <Alert
          severity="success"
          variant="filled"
          elevation={6}
          onClose={clearSuccessSnackbar}
        >
          {correctSuccess}
        </Alert>
      </Snackbar>
    </>
  );
}

export default UnknownsPage;
