import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import Paper from '@mui/material/Paper';
import Chip from '@mui/material/Chip';
import Avatar from '@mui/material/Avatar';
import Button from '@mui/material/Button';
import Dialog from '@mui/material/Dialog';
import DialogTitle from '@mui/material/DialogTitle';
import DialogContent from '@mui/material/DialogContent';
import DialogContentText from '@mui/material/DialogContentText';
import DialogActions from '@mui/material/DialogActions';
import FavoriteIcon from '@mui/icons-material/Favorite';
import AccessTimeIcon from '@mui/icons-material/AccessTime';
import DownloadIcon from '@mui/icons-material/Download';
import DeleteIcon from '@mui/icons-material/Delete';
import { Video } from '../../types';
import { WeatherCard } from '../../components/WeatherCard';
import { resolveImageUrl, deleteVideo } from '../../api/api';
import { useProtectedArea } from '../../contexts/ProtectedAreaContext';
import { BASE_API_URL } from '../../api/api';

export const VideoInfo = ({ video }: { video: Video }) => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { unlocked } = useProtectedArea();
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const downloadUrl = unlocked ? `${BASE_API_URL}/videos/${video.id}/download` : null;

  const deleteMutation = useMutation({
    mutationFn: () => deleteVideo(video.id),
    onSuccess: () => {
      setDeleteDialogOpen(false);
      queryClient.invalidateQueries({ queryKey: ['unknowns'] });
      queryClient.invalidateQueries({ queryKey: ['timeline'] });
      queryClient.invalidateQueries({ queryKey: ['speciesVisits'] });
      queryClient.invalidateQueries({ queryKey: ['overview'] });
      queryClient.invalidateQueries({ queryKey: ['migration-calendar'] });
      queryClient.invalidateQueries({ queryKey: ['bird-directory'] });
      navigate('/');
    },
  });
  const { processor_version, start_time, end_time, favorite, weather, food } =
    video;

  const formatDate = (date: string | Date) =>
    new Date(date).toLocaleString(undefined, {
      dateStyle: 'medium',
      timeStyle: 'short',
    });

  const duration = Math.round(
    (new Date(end_time).getTime() - new Date(start_time).getTime()) / 1000,
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

      <Dialog open={deleteDialogOpen} onClose={() => !deleteMutation.isPending && setDeleteDialogOpen(false)}>
        <DialogTitle>{t('videoInfo.deleteConfirmTitle')}</DialogTitle>
        <DialogContent>
          <DialogContentText>{t('videoInfo.deleteConfirmText')}</DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDeleteDialogOpen(false)} disabled={deleteMutation.isPending}>
            {t('common.cancel')}
          </Button>
          <Button
            color="error"
            variant="contained"
            onClick={() => deleteMutation.mutate()}
            disabled={deleteMutation.isPending}
          >
            {deleteMutation.isPending ? t('common.deleting') : t('common.delete')}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Favorite Badge */}
      {favorite && (
        <Chip
          icon={<FavoriteIcon />}
          label={t('videoInfo.favorite')}
          color="primary"
          size="small"
          sx={{ alignSelf: 'flex-start' }}
        />
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
        </Box>
      </Paper>

      {/* Weather Card */}
      <WeatherCard
        weather={weather}
        date={start_time ? new Date(start_time).toISOString().slice(0, 10) : undefined}
      />

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
