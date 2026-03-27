import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import CircularProgress from '@mui/material/CircularProgress';
import Card from '@mui/material/Card';
import CardContent from '@mui/material/CardContent';
import CardActionArea from '@mui/material/CardActionArea';
import Chip from '@mui/material/Chip';
import Button from '@mui/material/Button';
import FormControl from '@mui/material/FormControl';
import InputLabel from '@mui/material/InputLabel';
import Select from '@mui/material/Select';
import MenuItem from '@mui/material/MenuItem';
import Alert from '@mui/material/Alert';
import { AdapterDayjs } from '@mui/x-date-pickers/AdapterDayjs';
import { LocalizationProvider } from '@mui/x-date-pickers/LocalizationProvider';
import { DatePicker } from '@mui/x-date-pickers/DatePicker';
import dayjs, { Dayjs } from 'dayjs';
import { getTimeRange, type TimeOfDay } from '../../utils/timeUtils';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import VideoFileIcon from '@mui/icons-material/VideoFile';
import Snackbar from '@mui/material/Snackbar';
import Tooltip from '@mui/material/Tooltip';
import {
  fetchUnknowns,
  fetchBirdDirectory,
  updateDetectionSpecies,
  confirmDetection,
  fetchRecentCorrections,
  resolveImageUrl,
  type UnknownDetection,
} from '../../api/api';
import { SpeciesIcon } from '../../components/SpeciesIcon';
import { useProtectedArea } from '../../contexts/ProtectedAreaContext';
import { PageHelp } from '../../components/PageHelp';
import { unknownsHelpConfig } from '../../page-help-config';
import { SettingsPasswordDialog } from '../../components/SettingsPasswordDialog';

function UnknownCard({
  detection,
  speciesList,
  onCorrect,
  onConfirm,
  canEdit,
}: {
  detection: UnknownDetection;
  speciesList: { id: number; name: string }[];
  onCorrect: (detectionId: number, speciesId: number) => void;
  onConfirm: (detectionId: number) => void;
  canEdit: boolean;
}) {
  const { t } = useTranslation();
  const [selectedSpeciesId, setSelectedSpeciesId] = useState<number | ''>('');
  const [correcting, setCorrecting] = useState(false);
  const [confirming, setConfirming] = useState(false);

  const handleCorrect = async () => {
    if (selectedSpeciesId === '' || correcting) return;
    setCorrecting(true);
    try {
      await onCorrect(detection.id, selectedSpeciesId as number);
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
              {new Date(detection.start_time).toLocaleString()}
            </Typography>
            <Box display="flex" gap={1} flexWrap="wrap" sx={{ mt: 0.5 }}>
              <Chip
                label={`${Math.round(detection.confidence * 100)}%`}
                size="small"
                color="warning"
              />
              {detection.detection_provider && (
                <Chip label={detection.detection_provider} size="small" variant="outlined" />
              )}
            </Box>
          </Box>
          <CardActionArea
            component={Link}
            to={`/videos/${detection.video_id}`}
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
            <Box display="flex" flexDirection="column" alignItems="center" gap={0.5}>
              <VideoFileIcon color="primary" />
              <Typography variant="caption">{t('unknowns.viewVideo')}</Typography>
            </Box>
          </CardActionArea>
          <Box display="flex" flexDirection="column" gap={1} minWidth={200}>
            <FormControl size="small" fullWidth>
              <InputLabel id={`unknowns-correct-species-${detection.id}`}>{t('unknowns.correctSpecies')}</InputLabel>
              <Select
                labelId={`unknowns-correct-species-${detection.id}`}
                value={selectedSpeciesId}
                label={t('unknowns.correctSpecies')}
                onChange={(e) => setSelectedSpeciesId(e.target.value as number | '')}
                disabled={!canEdit}
              >
                {speciesList.map((s) => (
                  <MenuItem key={s.id} value={s.id}>
                    {s.name}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
            <Tooltip title={!canEdit ? t('unknowns.passwordRequired') : ''}>
              <span>
                <Button
                  variant="contained"
                  size="small"
                  disabled={selectedSpeciesId === '' || correcting || !canEdit}
                  onClick={handleCorrect}
                >
                  {correcting ? '...' : t('unknowns.apply')}
                </Button>
              </span>
            </Tooltip>
            <Tooltip
              title={
                !canEdit
                  ? t('unknowns.passwordRequired')
                  : t('unknowns.confirmCorrectHelp')
              }
            >
              <span>
                <Button
                  variant="outlined"
                  size="small"
                  disabled={confirming || !canEdit}
                  onClick={handleConfirm}
                >
                  {confirming ? '...' : t('unknowns.confirmCorrect')}
                </Button>
              </span>
            </Tooltip>
            {!canEdit && (
              <Typography variant="caption" color="text.secondary">
                {t('unknowns.passwordRequired')}
              </Typography>
            )}
          </Box>
        </Box>
      </CardContent>
    </Card>
  );
}

export function UnknownsPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { requiresPassword, canEdit, setUnlocked } = useProtectedArea();
  const [showUnlockDialog, setShowUnlockDialog] = useState(false);

  const [selectedDate, setSelectedDate] = useState<Dayjs | null>(() => dayjs().startOf('date'));
  const [timeOfDay, setTimeOfDay] = useState<TimeOfDay>('all');

  const { data: unknowns, isLoading, error } = useQuery({
    queryKey: ['unknowns', selectedDate?.format('YYYY-MM-DD'), timeOfDay],
    queryFn: () => {
      if (!selectedDate) return [];
      const { start, end } = getTimeRange(selectedDate, timeOfDay);
      return fetchUnknowns(start, end, 500);
    },
    enabled: !!selectedDate,
  });

  const { data: speciesList = [] } = useQuery({
    queryKey: ['species'],
    queryFn: () => fetchBirdDirectory(),
  });
  const { data: recentCorrections = [] } = useQuery({
    queryKey: ['corrections-recent'],
    queryFn: () => fetchRecentCorrections(8),
    enabled: canEdit,
  });

  const [correctError, setCorrectError] = useState<string | null>(null);
  const [correctSuccess, setCorrectSuccess] = useState<string | null>(null);
  /** After correct/confirm: optional snackbar action to open this video (#81 phase B). */
  const [successVideoId, setSuccessVideoId] = useState<number | null>(null);

  const unknownsQueryKey = ['unknowns', selectedDate?.format('YYYY-MM-DD'), timeOfDay] as const;

  const resolveVideoIdForDetection = (detectionId: number): number | null => {
    const list = queryClient.getQueryData<UnknownDetection[]>(unknownsQueryKey) ?? [];
    const row = list.find((u) => u.id === detectionId);
    return row?.video_id ?? null;
  };

  const clearSuccessSnackbar = () => {
    setCorrectSuccess(null);
    setSuccessVideoId(null);
  };

  const correctMutation = useMutation({
    mutationFn: ({ detectionId, speciesId }: { detectionId: number; speciesId: number }) =>
      updateDetectionSpecies(detectionId, speciesId, 'unknowns'),
    onSuccess: (data, variables) => {
      queryClient.invalidateQueries({ queryKey: ['unknowns'] });
      queryClient.invalidateQueries({ queryKey: ['unknowns-count'] });
      queryClient.invalidateQueries({ queryKey: ['speciesVisits'] });
      queryClient.invalidateQueries({ queryKey: ['overview'] });
      queryClient.invalidateQueries({ queryKey: ['timeline'] });
      queryClient.invalidateQueries({ queryKey: ['migration-calendar'] });
      queryClient.invalidateQueries({ queryKey: ['bird-directory'] });
      queryClient.invalidateQueries({ queryKey: ['species'] });
      queryClient.invalidateQueries({ queryKey: ['speciesSummary'] });
      queryClient.invalidateQueries({ queryKey: ['corrections-recent'] });
      const msg = data?.updated_count && data.updated_count > 1
        ? t('video.correctedInVideos', { count: data.updated_count })
        : t('unknowns.corrected');
      setSuccessVideoId(resolveVideoIdForDetection(variables.detectionId));
      setCorrectSuccess(msg);
    },
    onError: (err: Error) => {
      setCorrectError(err.message || t('errors.loadSightings'));
    },
  });

  const confirmMutation = useMutation({
    mutationFn: (detectionId: number) => confirmDetection(detectionId, 'unknowns'),
    onSuccess: (_data, detectionId) => {
      queryClient.invalidateQueries({ queryKey: ['unknowns'] });
      queryClient.invalidateQueries({ queryKey: ['unknowns-count'] });
      queryClient.invalidateQueries({ queryKey: ['speciesVisits'] });
      queryClient.invalidateQueries({ queryKey: ['overview'] });
      queryClient.invalidateQueries({ queryKey: ['timeline'] });
      queryClient.invalidateQueries({ queryKey: ['migration-calendar'] });
      queryClient.invalidateQueries({ queryKey: ['corrections-recent'] });
      setSuccessVideoId(resolveVideoIdForDetection(detectionId));
      setCorrectSuccess(t('unknowns.corrected'));
    },
    onError: (err: Error) => {
      setCorrectError(err.message || t('errors.loadSightings'));
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

  if (isLoading)
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
        <CircularProgress />
      </Box>
    );
  if (error) return <Alert severity="error">{t('timeline.errorLoad')}</Alert>;

  return (
    <>
      <PageHelp {...unknownsHelpConfig} />
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
          <InputLabel id="unknowns-timeofday-label">{t('timeline.timeOfDay')}</InputLabel>
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

      {!canEdit && requiresPassword && (
        <Alert severity="info" sx={{ mb: 2 }}>
          {t('unknowns.passwordRequired')}{' '}
          <Button
            size="small"
            variant="outlined"
            onClick={() => setShowUnlockDialog(true)}
            sx={{ mr: 1 }}
          >
            {t('settings.passwordSubmit')}
          </Button>
          <Link to="/settings" style={{ fontWeight: 600 }}>
            {t('nav.settings')}
          </Link>
        </Alert>
      )}
      <SettingsPasswordDialog
        open={showUnlockDialog}
        onSuccess={(role) => {
          setUnlocked(true, role || 'admin');
          setShowUnlockDialog(false);
          queryClient.invalidateQueries({ queryKey: ['settings-check-access'] });
        }}
        onClose={() => setShowUnlockDialog(false)}
      />

      {canEdit && recentCorrections.length > 0 && (
        <Alert severity="info" sx={{ mb: 2 }}>
          <Typography variant="body2" sx={{ fontWeight: 600, mb: 0.5 }}>
            {t('unknowns.recentCorrectionsTitle')}
          </Typography>
          <Box component="ul" sx={{ m: 0, pl: 2 }}>
            {recentCorrections.slice(0, 5).map((row) => (
              <Typography component="li" variant="body2" key={row.id}>
                {new Date(row.created_at).toLocaleString()} — {row.action === 'confirm_species'
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
        <Alert severity="info">{t('unknowns.empty')}</Alert>
      ) : (
        <Box sx={{ mb: 2 }}>
          <Typography variant="body2" color="text.secondary">
            {t('unknowns.count', { count: unknowns?.length ?? 0 })}
          </Typography>
          {unknowns?.length === 500 && (
            <Typography variant="caption" color="text.secondary" display="block" sx={{ mt: 0.5 }}>
              {t('unknowns.limitReached')}
            </Typography>
          )}
        </Box>
      )}

      {unknowns?.map((d) => (
        <UnknownCard
          key={d.id}
          detection={d}
          speciesList={speciesList}
          onCorrect={handleCorrect}
          onConfirm={handleConfirm}
          canEdit={canEdit}
        />
      ))}
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
        autoHideDuration={successVideoId != null ? 10000 : 4000}
        onClose={clearSuccessSnackbar}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
        action={
          successVideoId != null ? (
            <Button
              color="inherit"
              size="small"
              onClick={() => {
                navigate(`/videos/${successVideoId}`);
                clearSuccessSnackbar();
              }}
            >
              {t('unknowns.openVideoAfterCorrect')}
            </Button>
          ) : undefined
        }
      >
        <Alert severity="success" onClose={clearSuccessSnackbar}>
          {correctSuccess}
        </Alert>
      </Snackbar>
    </>
  );
}

export default UnknownsPage;
