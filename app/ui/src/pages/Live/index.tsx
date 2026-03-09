import Box from '@mui/material/Box';
import Grid from '@mui/material/Grid2';
import Typography from '@mui/material/Typography';
import { useTranslation } from 'react-i18next';
import { useQuery } from '@tanstack/react-query';
import { fetchCameras } from '../../api/api';

/** Go2RTC iframe — формат (WebRTC/MSE) выбирает сам Go2RTC. */
const CameraStream = ({
  streamUrl,
  name,
}: {
  streamUrl: string;
  name: string;
}) => {
  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: 280 }}>
      <Typography variant="subtitle2" sx={{ mb: 0.5 }}>{name}</Typography>
      <Box
        component="iframe"
        src={streamUrl}
        title={name}
        sx={{
          flex: 1,
          minHeight: 200,
          border: 'none',
          borderRadius: 1,
          bgcolor: 'black',
        }}
      />
    </Box>
  );
};

export const LivePage = () => {
  const { t } = useTranslation();
  const { data: cameras, isLoading } = useQuery({
    queryKey: ['cameras'],
    queryFn: fetchCameras,
  });

  if (isLoading) {
    return (
      <Box>
        <Typography variant="h4" mb={3}>
          {t('live.streamTitle')}
        </Typography>
        <Typography>{t('live.loading')}</Typography>
      </Box>
    );
  }

  const cams = cameras ?? [];

  // Адаптивная сетка: 1 камера — на всю ширину, 2 — в 2 колонки, 3–4 — в 4, 5+ — в 6
  const numCols = cams.length <= 1 ? 1 : cams.length <= 2 ? 2 : cams.length <= 4 ? 4 : 6;
  const gridSize = 12 / numCols;

  return (
    <Box>
      <Typography variant="h4" mb={3}>
        {t('live.title')}
      </Typography>
      {cams.length === 0 ? (
        <Typography color="text.secondary">
          {t('live.noCameras')}
        </Typography>
      ) : (
      <Grid container spacing={2}>
        {cams.map((cam) => (
          <Grid key={cam.id} size={{ xs: 12, sm: 6, md: gridSize }}>
            <CameraStream
              streamUrl={cam.stream_url}
              name={cam.name}
            />
          </Grid>
        ))}
      </Grid>
      )}
    </Box>
  );
};
