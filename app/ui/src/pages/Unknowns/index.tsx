import { useState } from 'react';
import { Link } from 'react-router-dom';
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
import { DateTimePicker } from '@mui/x-date-pickers/DateTimePicker';
import dayjs, { Dayjs } from 'dayjs';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import VideoFileIcon from '@mui/icons-material/VideoFile';
import {
  fetchUnknowns,
  fetchBirdDirectory,
  updateDetectionSpecies,
  resolveImageUrl,
  type UnknownDetection,
} from '../../api/api';
import { SpeciesIcon } from '../../components/SpeciesIcon';
import { useProtectedArea } from '../../contexts/ProtectedAreaContext';
import { PageHelp } from '../../components/PageHelp';
import { unknownsHelpConfig } from '../../page-help-config';

function UnknownCard({
  detection,
  speciesList,
  onCorrect,
  canEdit,
}: {
  detection: UnknownDetection;
  speciesList: { id: number; name: string }[];
  onCorrect: (detectionId: number, speciesId: number) => void;
  canEdit: boolean;
}) {
  const { t } = useTranslation();
  const [selectedSpeciesId, setSelectedSpeciesId] = useState<number | ''>('');
  const [correcting, setCorrecting] = useState(false);

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
          {canEdit && (
            <Box display="flex" flexDirection="column" gap={1} minWidth={200}>
              <FormControl size="small" fullWidth>
                <InputLabel>{t('unknowns.correctSpecies')}</InputLabel>
                <Select
                  value={selectedSpeciesId}
                  label={t('unknowns.correctSpecies')}
                  onChange={(e) => setSelectedSpeciesId(e.target.value as number | '')}
                >
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
                disabled={selectedSpeciesId === '' || correcting}
                onClick={handleCorrect}
              >
                {correcting ? '...' : t('unknowns.apply')}
              </Button>
            </Box>
          )}
        </Box>
      </CardContent>
    </Card>
  );
}

export function UnknownsPage() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const { requiresPassword, unlocked } = useProtectedArea();
  const canEdit = !requiresPassword || unlocked;

  const [dateTime, setDateTime] = useState<Dayjs | null>(() => dayjs());

  const { data: unknowns, isLoading, error } = useQuery({
    queryKey: ['unknowns', dateTime],
    queryFn: () => {
      if (!dateTime) return [];
      const isTimeSelected = dateTime.hour() !== 0 || dateTime.minute() !== 0;
      return fetchUnknowns(
        dateTime.startOf(isTimeSelected ? 'hour' : 'date'),
        dateTime.endOf(isTimeSelected ? 'hour' : 'date'),
      );
    },
    enabled: !!dateTime,
  });

  const { data: speciesList = [] } = useQuery({
    queryKey: ['species'],
    queryFn: () => fetchBirdDirectory(),
  });

  const correctMutation = useMutation({
    mutationFn: ({ detectionId, speciesId }: { detectionId: number; speciesId: number }) =>
      updateDetectionSpecies(detectionId, speciesId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['unknowns'] });
    },
  });

  const handleCorrect = (detectionId: number, speciesId: number) =>
    correctMutation.mutateAsync({ detectionId, speciesId });

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
      <Box display="flex" alignItems="center" gap={1} mb={2}>
        <Typography variant="h5" fontWeight={600}>
          {t('unknowns.title')}
        </Typography>
      </Box>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        {t('unknowns.intro')}
      </Typography>
      <Box sx={{ mb: 3 }}>
        <LocalizationProvider dateAdapter={AdapterDayjs}>
          <DateTimePicker
            label={t('timeline.selectDateTime')}
            value={dateTime}
            onChange={(v) => setDateTime(v)}
            maxDateTime={dayjs()}
            views={['year', 'month', 'day', 'hours']}
          />
        </LocalizationProvider>
      </Box>

      {!canEdit && (
        <Alert severity="info" sx={{ mb: 2 }}>
          {t('unknowns.passwordRequired')}
        </Alert>
      )}

      {unknowns?.length === 0 ? (
        <Alert severity="info">{t('unknowns.empty')}</Alert>
      ) : (
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          {t('unknowns.count', { count: unknowns?.length ?? 0 })}
        </Typography>
      )}

      {unknowns?.map((d) => (
        <UnknownCard
          key={d.id}
          detection={d}
          speciesList={speciesList}
          onCorrect={handleCorrect}
          canEdit={canEdit}
        />
      ))}
    </>
  );
}

export default UnknownsPage;
