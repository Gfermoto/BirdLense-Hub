import React from 'react';
import { useTranslation } from 'react-i18next';
import Card from '@mui/material/Card';
import CardContent from '@mui/material/CardContent';
import Typography from '@mui/material/Typography';
import Stack from '@mui/material/Stack';
import Grid from '@mui/material/Grid2';
import Chip from '@mui/material/Chip';
import Alert from '@mui/material/Alert';
import LinearProgress from '@mui/material/LinearProgress';
import type { YoloDetectorHealthStatus } from '../../api/systemAuditMetrics';
import { useYoloDetectorHealthQuery } from '../../hooks/useSystemQueries';

function statusColor(status: YoloDetectorHealthStatus): 'success' | 'warning' | 'error' {
  if (status === 'blind') return 'error';
  if (status === 'degraded') return 'warning';
  return 'success';
}

function statusLabel(status: YoloDetectorHealthStatus, t: (k: string) => string): string {
  if (status === 'blind') return t('system.yoloDetector.statusBlind');
  if (status === 'degraded') return t('system.yoloDetector.statusDegraded');
  return t('system.yoloDetector.statusHealthy');
}

export const YoloDetectorHealthCard: React.FC = () => {
  const { t } = useTranslation();
  const query = useYoloDetectorHealthQuery(24);

  if (query.isLoading) return <LinearProgress />;
  if (query.error) {
    return <Alert severity="error">{t('system.yoloDetector.loadError')}</Alert>;
  }

  const data = query.data;
  const health = data?.health;
  const status = health?.status ?? 'healthy';
  const hints = data?.config_hints ?? {};

  return (
    <Card>
      <CardContent>
        <Typography variant="h5" sx={{ mb: 1 }}>
          {t('system.yoloDetector.title')}
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          {t('system.yoloDetector.description')}
        </Typography>

        {!data?.processor_snapshot_present ? (
          <Alert severity="warning" sx={{ mb: 2 }}>
            {t('system.yoloDetector.noSnapshot')}
          </Alert>
        ) : null}

        {health?.yolo_blind_alert ? (
          <Alert severity="error" sx={{ mb: 2 }}>
            {t('system.yoloDetector.alertActive')}
          </Alert>
        ) : null}

        <Grid container spacing={1.5} sx={{ mb: 2 }}>
          <Grid size={{ xs: 12, sm: 6, md: 3 }}>
            <Chip color={statusColor(status)} label={statusLabel(status, t)} />
          </Grid>
          <Grid size={{ xs: 12, sm: 6, md: 3 }}>
            <Chip
              variant="outlined"
              label={`${t('system.yoloDetector.phase')}: ${health?.yolo_blind_phase ?? 'none'}`}
            />
          </Grid>
          <Grid size={{ xs: 12, sm: 6, md: 3 }}>
            <Chip
              variant="outlined"
              label={`${t('system.yoloDetector.tracksSession')}: ${health?.yolo_frames_with_tracks_session ?? 0}`}
            />
          </Grid>
          <Grid size={{ xs: 12, sm: 6, md: 3 }}>
            <Chip
              variant="outlined"
              label={`${t('system.yoloDetector.frigateOnly')}: ${health?.session_extended_by_frigate_only ?? 0}`}
            />
          </Grid>
        </Grid>

        <Stack direction="row" flexWrap="wrap" gap={1} sx={{ mb: 1 }}>
          <Chip size="small" label={`imgsz: ${String(hints.binary_imgsz ?? '—')}`} />
          <Chip size="small" label={`backend: ${String(hints.inference_backend ?? '—')}`} />
          <Chip size="small" label={`device: ${String(hints.inference_device ?? '—')}`} />
          <Chip size="small" label={`min_conf: ${String(hints.min_confidence_binary ?? '—')}`} />
          <Chip size="small" label={`lores: ${String(hints.lores_wh ?? '—')}`} />
          {health?.stream_probe_fps != null ? (
            <Chip
              size="small"
              label={`probe: ${health.stream_probe_width ?? '?'}×${health.stream_probe_height ?? '?'} @ ${health.stream_probe_fps} fps`}
            />
          ) : null}
        </Stack>

        {(health?.reasons?.length ?? 0) > 0 ? (
          <Typography variant="caption" color="text.secondary" component="div">
            {t('system.yoloDetector.reasons')}: {health?.reasons?.join(', ')}
          </Typography>
        ) : null}

        <Typography variant="caption" color="text.secondary" display="block" sx={{ mt: 1 }}>
          {t('system.yoloDetector.runbookHint')}{' '}
          <code>{data?.runbook_path ?? 'docs/ru/yolo-blind-runbook.ru.md'}</code>
        </Typography>
      </CardContent>
    </Card>
  );
};
