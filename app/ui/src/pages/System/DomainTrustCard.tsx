import { useTranslation } from 'react-i18next';
import { useQuery } from '@tanstack/react-query';
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Chip from '@mui/material/Chip';
import LinearProgress from '@mui/material/LinearProgress';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';
import type { DomainStrictQuality } from '../../api/domainHealth';
import { fetchDomainHealth } from '../../api/domainHealth';
import { queryKeys } from '../../api/queryKeys';
import { SystemCardShell } from './SystemCardShell';

const STRICT_GATE_KEYS: (keyof DomainStrictQuality)[] = [
  'duplicate_video_groups_ok',
  'duplicate_detection_groups_ok',
  'duplicate_clip_candidates_ok',
  'visit_species_mismatches_ok',
  'video_detections_with_frames_ratio_ok',
  'video_detections_primary_yolo_ratio_ok',
];

/** Maps strict_quality keys (without `_ok`) for i18n */
function gateSlug(key: keyof DomainStrictQuality): string {
  if (key === 'strict_quality_ready') return 'strict_quality_ready';
  return key.replace(/_ok$/, '');
}

function pct(n: number | null | undefined, digits = 1): string {
  if (n === null || n === undefined || Number.isNaN(n)) return '—';
  return `${(n * 100).toFixed(digits)}`;
}

export function DomainTrustCard() {
  const { t } = useTranslation();
  const { data, isLoading, error } = useQuery({
    queryKey: queryKeys.systemPanels.domainHealth,
    queryFn: fetchDomainHealth,
    staleTime: 60_000,
  });

  if (isLoading) return <LinearProgress />;
  if (error || !data) {
    return (
      <Alert severity="warning" variant="outlined">
        {t('system.domainTrustLoadError')}
      </Alert>
    );
  }

  const degraded = Boolean(data.snapshot_degraded);
  const sq = data.strict_quality;
  const metrics = data.metrics ?? {};
  const thresholds = data.thresholds ?? {};

  const gapSec = thresholds.clip_duplicate_gap_seconds ?? '—';
  const yoloMin = 80;
  const framesMin = 90;

  const dupClipCount = metrics.duplicate_clip_candidates_24h ?? 0;
  const yoloRatio = metrics.video_detections_primary_yolo_ratio_24h;
  const framesRatio = metrics.video_detections_with_frames_ratio_24h;
  const trackStability = metrics.track_stability_score_avg_24h;
  const trackFragmentedRatio = metrics.track_rows_fragmented_ratio_24h;
  const lifecycleEnterRate = metrics.lifecycle_enter_rate_24h;
  const lifecycleRejectedOnlyRate = metrics.lifecycle_rejected_only_rate_24h;
  const trackRegression = Boolean(metrics.track_quality_regression_24h);
  const detections24h = Number(metrics.video_detections_24h ?? 0);
  const ratioSampleSkipped = detections24h <= 0;

  const failingReasons: { slug: string; body: string }[] = [];
  if (sq && !degraded) {
    for (const key of STRICT_GATE_KEYS) {
      if (sq[key] !== false) continue;
      const slug = gateSlug(key);
      let body = '';
      if (slug === 'duplicate_clip_candidates') {
        body = t('system.domainTrustGateFail.duplicate_clip_candidates', {
          gap: gapSec,
          count: dupClipCount,
        });
      } else if (slug === 'video_detections_primary_yolo_ratio') {
        body = t('system.domainTrustGateFail.video_detections_primary_yolo_ratio', {
          pct: pct(yoloRatio),
          min: yoloMin,
        });
      } else if (slug === 'video_detections_with_frames_ratio') {
        body = t(
          'system.domainTrustGateFail.video_detections_with_frames_ratio',
          {
            pct: pct(framesRatio),
            min: framesMin,
          },
        );
      } else {
        body = t(`system.domainTrustGateFail.${slug}`, {
          defaultValue: t('system.domainTrustGateFailGeneric'),
        });
      }
      failingReasons.push({ slug, body });
    }
  }

  const ready = Boolean(sq?.strict_quality_ready) && !degraded;

  return (
    <SystemCardShell
      id="domain-trust"
      title={t('system.domainTrustTitle')}
      description={t('system.domainTrustHint')}
      statusLabel={
        degraded
          ? t('system.domainTrustStatusDegraded')
          : ready
            ? t('system.domainTrustStatusGreen')
            : t('system.domainTrustStatusAttention')
      }
      statusTone={degraded ? 'error' : ready ? 'success' : 'warning'}
    >
      <Stack spacing={2}>
        <Alert severity="info" variant="outlined">
          {t('system.domainTrustNotLiveness')}
        </Alert>

        {degraded ? (
          <Alert severity="error" variant="outlined">
            {t('system.domainTrustSnapshotDegraded', {
              err: data.snapshot_error_class ?? '—',
            })}
          </Alert>
        ) : null}

        {!degraded && sq ? (
          <>
            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
              {STRICT_GATE_KEYS.map((key) => {
                const ok = sq[key];
                const slug = gateSlug(key);
                const isRatioGate =
                  key === 'video_detections_with_frames_ratio_ok' ||
                  key === 'video_detections_primary_yolo_ratio_ok';
                const skipped = ratioSampleSkipped && isRatioGate;
                const chipColor = skipped
                  ? 'info'
                  : ok
                    ? 'success'
                    : 'warning';
                const chipLabel = skipped
                  ? `${t(`system.domainTrustGate.${slug}`)}: ${t('system.domainTrustChipSkipped')}`
                  : `${t(`system.domainTrustGate.${slug}`)}: ${ok ? t('system.domainTrustChipPass') : t('system.domainTrustChipFail')}`;
                return (
                  <Chip
                    key={key}
                    size="small"
                    variant="outlined"
                    color={chipColor}
                    label={chipLabel}
                  />
                );
              })}
            </Box>

            <Typography variant="subtitle2">
              {t('system.domainTrustMetricsHeading')}
            </Typography>
            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
              <Chip
                size="small"
                variant="outlined"
                label={t('system.domainTrustMetricDupClipCandidates', {
                  n: dupClipCount,
                })}
              />
              <Chip
                size="small"
                variant="outlined"
                label={t('system.domainTrustMetricYoloPrimary', {
                  pct: pct(yoloRatio),
                })}
              />
              <Chip
                size="small"
                variant="outlined"
                label={t('system.domainTrustMetricFramesCoverage', {
                  pct: pct(framesRatio),
                })}
              />
              <Chip
                size="small"
                variant="outlined"
                label={t('system.domainTrustMetricTrackStability', {
                  pct: pct(trackStability),
                })}
              />
              <Chip
                size="small"
                variant="outlined"
                label={t('system.domainTrustMetricTrackFragmentation', {
                  pct: pct(trackFragmentedRatio),
                })}
              />
              <Chip
                size="small"
                variant="outlined"
                label={t('system.domainTrustMetricLifecycleEnterRate', {
                  pct: pct(lifecycleEnterRate),
                })}
              />
              <Chip
                size="small"
                variant="outlined"
                label={t('system.domainTrustMetricLifecycleRejectedRate', {
                  pct: pct(lifecycleRejectedOnlyRate),
                })}
              />
            </Box>

            {trackRegression ? (
              <Alert severity="warning" variant="outlined">
                {t('system.domainTrustTrackRegressionAlert')}
              </Alert>
            ) : null}

            {failingReasons.length > 0 ? (
              <Alert severity="warning" variant="outlined">
                <Typography variant="subtitle2" sx={{ mb: 1 }}>
                  {t('system.domainTrustAttentionHeading')}
                </Typography>
                <Stack component="ul" spacing={0.75} sx={{ m: 0, pl: 2 }}>
                  {failingReasons.map(({ slug, body }) => (
                    <Typography
                      key={slug}
                      component="li"
                      variant="body2"
                      color="text.secondary"
                    >
                      <strong>{t(`system.domainTrustGate.${slug}`)}:</strong>{' '}
                      {body}
                    </Typography>
                  ))}
                </Stack>
              </Alert>
            ) : null}

            <Typography variant="body2" color="text.secondary">
              {t('system.domainTrustThresholdsLine', {
                gap: gapSec,
                yolo: yoloMin,
                frames: framesMin,
              })}
            </Typography>
          </>
        ) : null}
      </Stack>
    </SystemCardShell>
  );
}
