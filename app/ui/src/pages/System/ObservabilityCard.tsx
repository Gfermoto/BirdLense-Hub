import { useTranslation } from 'react-i18next';
import { useQuery } from '@tanstack/react-query';
import {
  Alert,
  Box,
  Card,
  CardContent,
  Chip,
  LinearProgress,
  Typography,
} from '@mui/material';
import { fetchObservability } from '../../api/api';

const PREVIEW_ORDER = ['best_frame', 'bbox_crop', 'full_frame', 'none', 'unknown'] as const;

export function ObservabilityCard() {
  const { t } = useTranslation();
  const { data, isLoading, error } = useQuery({
    queryKey: ['system-observability'],
    queryFn: fetchObservability,
    staleTime: 30_000,
  });

  const origin = typeof window !== 'undefined' ? window.location.origin : '';
  const abs = (p: string) => (p.startsWith('http') ? p : `${origin}${p}`);

  if (isLoading) return <LinearProgress />;
  if (error || !data) return <Alert severity="warning">{t('system.observabilityLoadError')}</Alert>;

  const counts = data.notify_preview_24h || {};

  return (
    <Card>
      <CardContent>
        <Typography variant="h6" sx={{ mb: 1 }}>
          {t('system.observabilityTitle')}
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          {t('system.observabilityHint')}
        </Typography>

        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, mb: 2 }}>
          {PREVIEW_ORDER.map((key) => (
            <Chip
              key={key}
              size="small"
              variant="outlined"
              label={`${t(`system.previewSource.${key}`)}: ${counts[key] ?? 0}`}
            />
          ))}
        </Box>

        <Typography variant="subtitle2" sx={{ mb: 0.5 }}>
          {t('system.hubMetricsForHeimdall')}
        </Typography>
        <Typography variant="body2" component="div" sx={{ wordBreak: 'break-all', mb: 0.5 }}>
          <strong>Prometheus:</strong> {abs(data.hub_metrics.prometheus_text)}
        </Typography>
        <Typography variant="body2" component="div" sx={{ wordBreak: 'break-all', mb: 0.5 }}>
          <strong>JSON:</strong> {abs(data.hub_metrics.json_summary)}
        </Typography>
        <Typography variant="caption" color="text.secondary">
          {t('system.hubMetricsHeimdallNote')}
        </Typography>
      </CardContent>
    </Card>
  );
}
