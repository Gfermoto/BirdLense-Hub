import { useQuery } from '@tanstack/react-query';
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Card from '@mui/material/Card';
import CardContent from '@mui/material/CardContent';
import Chip from '@mui/material/Chip';
import LinearProgress from '@mui/material/LinearProgress';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';
import { useTranslation } from 'react-i18next';
import {
  fetchCatalogRepairStatus,
  fetchConfigAudit,
  fetchObservability,
  fetchReadiness,
} from '../../api/api';
import { queryKeys } from '../../api/queryKeys';

type SystemHeroProps = {
  advanced: boolean;
};

function firstNumber(record: Record<string, number> | undefined, keys: string[]): number {
  if (!record) return 0;
  return keys.reduce((sum, key) => sum + Number(record[key] ?? 0), 0);
}

export function SystemHero({ advanced }: SystemHeroProps) {
  const { t } = useTranslation();
  const readinessQ = useQuery({
    queryKey: queryKeys.system.readiness,
    queryFn: fetchReadiness,
    refetchInterval: 30_000,
  });
  const configAuditQ = useQuery({
    queryKey: ['config-audit'],
    queryFn: fetchConfigAudit,
    staleTime: 30_000,
  });
  const observabilityQ = useQuery({
    queryKey: ['system-observability'],
    queryFn: fetchObservability,
    staleTime: 30_000,
  });
  const catalogRepairQ = useQuery({
    queryKey: ['catalog-repair-status'],
    queryFn: fetchCatalogRepairStatus,
    staleTime: 5_000,
    refetchInterval: (q) => (q.state.data?.status === 'running' ? 4_000 : 20_000),
  });

  const loading =
    readinessQ.isLoading ||
    configAuditQ.isLoading ||
    observabilityQ.isLoading ||
    catalogRepairQ.isLoading;
  if (loading) return <LinearProgress />;

  if (!readinessQ.data || !configAuditQ.data || !observabilityQ.data || !catalogRepairQ.data) {
    return <Alert severity="warning">{t('system.heroLoadError')}</Alert>;
  }

  const readiness = readinessQ.data;
  const configAudit = configAuditQ.data;
  const observability = observabilityQ.data;
  const catalogRepair = catalogRepairQ.data;
  const configWarnings = Array.isArray(configAudit.config_warnings)
    ? configAudit.config_warnings.length
    : 0;
  const deprecatedKeys = Array.isArray(configAudit.deprecated_keys_present)
    ? configAudit.deprecated_keys_present.length
    : 0;
  const deliveryFailures = firstNumber(observability.notify_delivery_24h, ['failed']);
  const fallbackEvents = firstNumber(observability.notify_fallback_24h, [
    'decode_failed',
    'telegram_photo_failed',
    'telegram_text_failed',
    'unexpected_error',
  ]);
  const catalogCompletion = Number(catalogRepair.coverage_now?.completion_percent ?? 0);
  const catalogRunning = catalogRepair.status === 'running';
  const needsAttention =
    !readiness.ready ||
    configWarnings > 0 ||
    deprecatedKeys > 0 ||
    deliveryFailures > 0 ||
    fallbackEvents > 0 ||
    catalogRunning ||
    catalogCompletion < 75;

  const issues = [
    !readiness.ready ? t('system.heroIssueReadiness') : null,
    configWarnings > 0 ? t('system.heroIssueWarnings', { count: configWarnings }) : null,
    deprecatedKeys > 0 ? t('system.heroIssueDeprecated', { count: deprecatedKeys }) : null,
    deliveryFailures > 0 ? t('system.heroIssueDelivery', { count: deliveryFailures }) : null,
    fallbackEvents > 0 ? t('system.heroIssueFallbacks', { count: fallbackEvents }) : null,
    catalogRunning ? t('system.heroIssueCatalogRunning') : null,
    !catalogRunning && catalogCompletion < 75
      ? t('system.heroIssueCatalogCoverage', { percent: catalogCompletion.toFixed(0) })
      : null,
  ].filter(Boolean) as string[];

  return (
    <Card
      sx={{
        width: '100%',
        minWidth: 0,
        maxWidth: '100%',
        boxSizing: 'border-box',
        background:
          needsAttention
            ? 'linear-gradient(135deg, rgba(245, 158, 11, 0.14), rgba(30, 41, 59, 0.96))'
            : 'linear-gradient(135deg, rgba(16, 185, 129, 0.16), rgba(30, 41, 59, 0.96))',
      }}
    >
      <CardContent sx={{ display: 'grid', gap: 2.5 }}>
        <Stack
          direction={{ xs: 'column', lg: 'row' }}
          spacing={2}
          justifyContent="space-between"
          alignItems={{ xs: 'flex-start', lg: 'center' }}
        >
          <Box>
            <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap>
              <Typography variant="h5">{t('system.heroTitle')}</Typography>
              <Chip
                color={needsAttention ? 'warning' : 'success'}
                label={
                  needsAttention
                    ? t('system.heroNeedsAttention')
                    : t('system.heroHealthy')
                }
              />
            </Stack>
            <Typography variant="body1" sx={{ mt: 1 }}>
              {needsAttention ? t('system.heroSummaryDegraded') : t('system.heroSummaryHealthy')}
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mt: 0.75 }}>
              {t('system.readinessCheckedAt', { at: readiness.checked_at })}
            </Typography>
          </Box>
          <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1} useFlexGap flexWrap="wrap">
            <Button href="#system-overview" variant="contained">
              {t('system.heroActionOverview')}
            </Button>
            <Button href="#system-integrations" variant="outlined">
              {t('system.heroActionReview')}
            </Button>
            {advanced ? (
              <Button href="#system-workspace" variant="outlined" color="warning">
                {t('system.heroActionWorkspace')}
              </Button>
            ) : null}
          </Stack>
        </Stack>

        <Box
          sx={{
            display: 'grid',
            gap: 1,
            minWidth: 0,
            gridTemplateColumns: {
              xs: '1fr',
              sm: 'repeat(2, minmax(0, 1fr))',
              md: 'repeat(4, minmax(0, 1fr))',
            },
          }}
        >
          <MetricBlock
            label={t('system.heroMetricHealth')}
            value={readiness.ready ? t('system.readinessReady') : t('system.readinessDegraded')}
          />
          <MetricBlock
            label={t('system.heroMetricWarnings')}
            value={`${configWarnings + deprecatedKeys}`}
          />
          <MetricBlock
            label={t('system.heroMetricDelivery')}
            value={`${deliveryFailures}`}
          />
          <MetricBlock
            label={t('system.heroMetricCatalog')}
            value={catalogRunning ? t('system.catalogRepairRunning') : `${catalogCompletion.toFixed(0)}%`}
          />
        </Box>

        <Box>
          <Typography variant="subtitle2" sx={{ mb: 1 }}>
            {issues.length > 0 ? t('system.heroTopIssues') : t('system.heroNoIssues')}
          </Typography>
          {issues.length > 0 ? (
            <Stack spacing={1}>
              {issues.slice(0, 4).map((issue) => (
                <Alert key={issue} severity="warning" sx={{ py: 0 }}>
                  {issue}
                </Alert>
              ))}
            </Stack>
          ) : (
            <Typography variant="body2" color="text.secondary">
              {t('system.heroNoIssuesHint')}
            </Typography>
          )}
        </Box>
      </CardContent>
    </Card>
  );
}

function MetricBlock({ label, value }: { label: string; value: string }) {
  return (
    <Box
      sx={{
        p: 1.5,
        borderRadius: 2,
        bgcolor: 'rgba(15, 23, 42, 0.38)',
        border: '1px solid rgba(148, 163, 184, 0.14)',
      }}
    >
      <Typography variant="caption" color="text.secondary" display="block">
        {label}
      </Typography>
      <Typography variant="h6" sx={{ mt: 0.5 }}>
        {value}
      </Typography>
    </Box>
  );
}
