import { useTranslation } from 'react-i18next';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import Paper from '@mui/material/Paper';
import Chip from '@mui/material/Chip';
import Avatar from '@mui/material/Avatar';
import Button from '@mui/material/Button';
import FavoriteIcon from '@mui/icons-material/Favorite';
import AccessTimeIcon from '@mui/icons-material/AccessTime';
import DownloadIcon from '@mui/icons-material/Download';
import { Video } from '../../types';
import { WeatherCard } from '../../components/WeatherCard';
import { resolveImageUrl } from '../../api/api';
import { useProtectedArea } from '../../contexts/ProtectedAreaContext';
import { BASE_API_URL } from '../../api/api';

export const VideoInfo = ({ video }: { video: Video }) => {
  const { t } = useTranslation();
  const { unlocked } = useProtectedArea();
  const downloadUrl = unlocked ? `${BASE_API_URL}/videos/${video.id}/download` : null;
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
      {/* Download video — только для админа и помощника */}
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
      <WeatherCard weather={weather} />

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
