import { useTranslation } from 'react-i18next';
import { useQuery } from '@tanstack/react-query';
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Chip from '@mui/material/Chip';
import LinearProgress from '@mui/material/LinearProgress';
import Typography from '@mui/material/Typography';
import { fetchObservability } from '../../api/systemAuditMetrics';
import { queryKeys } from '../../api/queryKeys';
import { SystemCardShell } from './SystemCardShell';

const PREVIEW_ORDER = [
  'best_frame',
  'bbox_crop',
  'full_frame',
  'none',
  'unknown',
] as const;
const DELIVERY_ORDER = [
  'photo',
  'text_fallback',
  'text',
  'failed',
  'skipped',
  'unknown',
] as const;
const FALLBACK_ORDER = [
  'none',
  'no_preview',
  'decode_failed',
  'telegram_photo_failed',
  'notifications_disabled',
  'telegram_not_configured',
  'config_disabled',
  'unsafe_path',
  'read_failed',
  'telegram_text_failed',
  'unexpected_error',
  'unknown',
] as const;

function translatedOrFallback(
  t: (key: string) => string,
  key: string,
  fallback: string,
) {
  const value = t(key);
  return value === key ? fallback : value;
}

export function ObservabilityCard({ simple = false }: { simple?: boolean }) {
  const { t } = useTranslation();
  const { data, isLoading, error } = useQuery({
    queryKey: queryKeys.systemPanels.observability,
    queryFn: fetchObservability,
    staleTime: 30_000,
  });

  const origin = typeof window !== 'undefined' ? window.location.origin : '';
  const abs = (p?: string) => {
    if (!p) return '—';
    return p.startsWith('http') ? p : `${origin}${p}`;
  };

  if (isLoading) return <LinearProgress />;
  if (error || !data)
    return (
      <Alert severity="warning" variant="outlined">{t('system.observabilityLoadError')}</Alert>
    );

  const generatedCounts = data.notify_preview_generated_24h || {};
  const counts = data.notify_preview_24h || {};
  const fallbackCounts = data.notify_fallback_24h || {};
  const deliveryCounts = data.notify_delivery_24h || {};
  const ml7 = data.ml_health?.rolling_7d;
  const ml30 = data.ml_health?.rolling_30d;
  const lineage = data.model_lineage;
  const deliveryFailures = Number(deliveryCounts.failed ?? 0);
  const fallbackFailures =
    Number(fallbackCounts.decode_failed ?? 0) +
    Number(fallbackCounts.telegram_photo_failed ?? 0) +
    Number(fallbackCounts.telegram_text_failed ?? 0) +
    Number(fallbackCounts.unexpected_error ?? 0);
  const lineageFingerprint =
    typeof lineage?.config_fingerprint === 'string'
      ? lineage.config_fingerprint.slice(0, 12)
      : null;
  const artifactEntries = (
    lineage?.artifacts && typeof lineage.artifacts === 'object'
      ? Object.entries(lineage.artifacts)
      : []
  ).filter((entry) => {
    const [, value] = entry;
    return typeof value === 'object' && value !== null;
  });
  const artifactLabel = (key: string) =>
    translatedOrFallback(t, `system.modelLineageArtifact.${key}`, key);

  return (
    <SystemCardShell
      title={t('system.observabilityTitle')}
      description={t('system.observabilityHint')}
      statusLabel={
        deliveryFailures > 0 || fallbackFailures > 0
          ? t('system.configAuditNeedsReview')
          : t('system.readinessReady')
      }
      statusTone={
        deliveryFailures > 0 || fallbackFailures > 0 ? 'warning' : 'success'
      }
    >
      <Box>
        {!simple ? (
          <>
            <Typography variant="subtitle2" sx={{ mb: 0.75 }}>
              {t('system.observabilityGeneratedTitle')}
            </Typography>
            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, mb: 2 }}>
              {PREVIEW_ORDER.map((key) => (
                <Chip
                  key={`generated-${key}`}
                  size="small"
                  variant="outlined"
                  label={`${t(`system.previewSource.${key}`)}: ${generatedCounts[key] ?? 0}`}
                />
              ))}
            </Box>

            <Typography variant="subtitle2" sx={{ mb: 0.75 }}>
              {t('system.observabilityPreviewTitle')}
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
          </>
        ) : null}

        <Typography variant="subtitle2" sx={{ mb: 0.75 }}>
          {t('system.observabilityDeliveryTitle')}
        </Typography>
        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, mb: 2 }}>
          {DELIVERY_ORDER.map((key) => (
            <Chip
              key={key}
              size="small"
              variant="outlined"
              label={`${t(`system.delivery.${key}`)}: ${deliveryCounts[key] ?? 0}`}
            />
          ))}
        </Box>

        <Typography variant="subtitle2" sx={{ mb: 0.75 }}>
          {t('system.observabilityFallbackTitle')}
        </Typography>
        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, mb: 2 }}>
          {FALLBACK_ORDER.map((key) => (
            <Chip
              key={key}
              size="small"
              variant="outlined"
              label={`${t(`system.fallbackReason.${key}`)}: ${fallbackCounts[key] ?? 0}`}
            />
          ))}
        </Box>

        {!simple && ml7 && ml30 ? (
          <>
            <Typography variant="subtitle2" sx={{ mb: 0.75 }}>
              {t('system.mlHealthTitle')}
            </Typography>
            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, mb: 2 }}>
              <Chip
                size="small"
                variant="outlined"
                label={t('system.mlHealthCorrections7d', {
                  n: ml7.corrections_logged,
                })}
              />
              <Chip
                size="small"
                variant="outlined"
                label={t('system.mlHealthCorrectionRate7d', {
                  n: (ml7.correction_rate * 100).toFixed(1),
                })}
              />
              <Chip
                size="small"
                variant="outlined"
                label={t('system.mlHealthManualRate30d', {
                  n: (ml30.manual_annotation_rate * 100).toFixed(1),
                })}
              />
              <Chip
                size="small"
                variant="outlined"
                label={t('system.mlHealthUnknownRate30d', {
                  n: (ml30.unknown_rate * 100).toFixed(1),
                })}
              />
              <Chip
                size="small"
                variant="outlined"
                label={t('system.mlHealthGenericRate30d', {
                  n: (ml30.generic_rate * 100).toFixed(1),
                })}
              />
            </Box>
          </>
        ) : null}

        {!simple && lineageFingerprint ? (
          <>
            <Typography variant="subtitle2" sx={{ mb: 0.75 }}>
              {t('system.modelLineageTitle')}
            </Typography>
            <Typography variant="body2" sx={{ mb: 1 }}>
              {t('system.modelLineageFingerprint')}:{' '}
              <code>{lineageFingerprint}</code>
            </Typography>
            {artifactEntries.length > 0 ? (
              <>
                <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, mb: 1 }}>
                  {artifactEntries.map(([key, value]) => (
                    <Chip
                      key={key}
                      size="small"
                      color={value.exists ? 'success' : 'default'}
                      variant="outlined"
                      label={`${artifactLabel(key)}: ${value.exists ? t('system.statusPresent') : t('system.statusMissing')}`}
                    />
                  ))}
                </Box>
                <Typography
                  variant="caption"
                  color="text.secondary"
                  display="block"
                  sx={{ mb: 2 }}
                >
                  {t('system.modelLineageArtifactsHint')}
                </Typography>
              </>
            ) : (
              <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                {t('system.modelLineageNoArtifacts')}
              </Typography>
            )}
          </>
        ) : null}

        {!simple && data.hub_metrics ? (
          <>
            <Typography variant="subtitle2" sx={{ mb: 0.5 }}>
              {t('system.hubMetricsForHeimdall')}
            </Typography>
            <Typography
              variant="body2"
              component="div"
              sx={{ wordBreak: 'break-all', mb: 0.5 }}
            >
              <strong>{t('system.hubMetricsPrometheus')}:</strong>{' '}
              {abs(data.hub_metrics.prometheus_text)}
            </Typography>
            <Typography
              variant="body2"
              component="div"
              sx={{ wordBreak: 'break-all', mb: 0.5 }}
            >
              <strong>{t('system.hubMetricsJson')}:</strong>{' '}
              {abs(data.hub_metrics.json_summary)}
            </Typography>
            <Typography variant="caption" color="text.secondary">
              {t('system.hubMetricsHeimdallNote')}
            </Typography>
          </>
        ) : null}
      </Box>
    </SystemCardShell>
  );
}
