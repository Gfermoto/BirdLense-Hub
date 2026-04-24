import { useState } from 'react';
import Box from '@mui/material/Box';
import Grid from '@mui/material/Grid2';
import Typography from '@mui/material/Typography';
import Button from '@mui/material/Button';
import ToggleButton from '@mui/material/ToggleButton';
import ToggleButtonGroup from '@mui/material/ToggleButtonGroup';
import { useTranslation } from 'react-i18next';
import { useQuery } from '@tanstack/react-query';
import { fetchCameras } from '../../api/camerasHealth';
import { queryKeys } from '../../api/queryKeys';
import { PageHeader } from '../../components/PageHeader';
import { PageLoadingState, PageMessageState } from '../../components/PageState';
import { useDocumentTitle } from '../../hooks/useDocumentTitle';

type StreamMode = 'go2rtc' | 'mjpeg';

/** Go2RTC iframe (RTC/MSE) или MJPEG img — fallback при 502/go2rtc недоступен. */
const CameraStream = ({
  streamUrl,
  streamUrlMjpeg,
  name,
  mode,
}: {
  streamUrl: string;
  streamUrlMjpeg?: string;
  name: string;
  mode: StreamMode;
}) => {
  const useMjpeg = mode === 'mjpeg' && streamUrlMjpeg;
  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: 280 }}>
      <Typography variant="subtitle2" sx={{ mb: 0.5 }}>
        {name}
      </Typography>
      {useMjpeg ? (
        <Box
          component="img"
          src={streamUrlMjpeg}
          alt={name}
          sx={{
            flex: 1,
            minHeight: 200,
            objectFit: 'contain',
            borderRadius: 1,
            bgcolor: 'black',
          }}
        />
      ) : (
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
      )}
    </Box>
  );
};

export const LivePage = () => {
  const { t } = useTranslation();
  useDocumentTitle(t('nav.liveView'));
  const [streamMode, setStreamMode] = useState<StreamMode>('go2rtc');
  const {
    data: cameras,
    isLoading,
    error,
    refetch,
  } = useQuery({
    queryKey: queryKeys.live.cameras,
    queryFn: fetchCameras,
  });

  if (isLoading) {
    return <PageLoadingState label={t('live.loading')} />;
  }

  if (error) {
    return (
      <PageMessageState
        title={t('nav.liveView')}
        message={t('live.errorLoad')}
        severity="error"
        action={
          <Button variant="outlined" onClick={() => refetch()}>
            {t('common.retry')}
          </Button>
        }
      />
    );
  }

  const cams = cameras ?? [];
  const hasMjpeg = cams.some((c) => c.stream_url_mjpeg);

  // Адаптивная сетка: 1 камера — на всю ширину, 2 — в 2 колонки, 3–4 — в 4, 5+ — в 6
  const numCols =
    cams.length <= 1 ? 1 : cams.length <= 2 ? 2 : cams.length <= 4 ? 4 : 6;
  const gridSize = 12 / numCols;

  return (
    <Box>
      <PageHeader
        title={t('live.title')}
        description={t('live.streamTitle')}
        actions={
          hasMjpeg ? (
            <ToggleButtonGroup
              value={streamMode}
              exclusive
              onChange={(_, v: StreamMode | null) =>
                v != null && setStreamMode(v)
              }
              size="medium"
              aria-label={t('live.streamModeAria')}
              sx={{
                '& .MuiToggleButton-root': { minHeight: 40, px: 1.75 },
              }}
            >
              <ToggleButton value="go2rtc">{t('live.modeGo2rtc')}</ToggleButton>
              <ToggleButton value="mjpeg">{t('live.modeMjpeg')}</ToggleButton>
            </ToggleButtonGroup>
          ) : null
        }
        sx={{ mb: 3 }}
      />
      {cams.length === 0 ? (
        <PageMessageState message={t('live.noCameras')} />
      ) : (
        <Grid container spacing={2}>
          {cams.map((cam) => (
            <Grid key={cam.id} size={{ xs: 12, sm: 6, md: gridSize }}>
              <CameraStream
                streamUrl={cam.stream_url}
                streamUrlMjpeg={cam.stream_url_mjpeg}
                name={cam.name}
                mode={streamMode}
              />
            </Grid>
          ))}
        </Grid>
      )}
    </Box>
  );
};
