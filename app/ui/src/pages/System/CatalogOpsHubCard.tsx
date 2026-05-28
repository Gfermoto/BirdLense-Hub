import { useTranslation } from 'react-i18next';
import { useQuery } from '@tanstack/react-query';
import { Link as RouterLink } from 'react-router-dom';
import Alert from '@mui/material/Alert';
import Button from '@mui/material/Button';
import Chip from '@mui/material/Chip';
import LinearProgress from '@mui/material/LinearProgress';
import Stack from '@mui/material/Stack';
import axios from 'axios';
import { BASE_API_URL } from '../../api/api';
import { fetchBirdDirectory } from '../../api/speciesOverviewDetections';
import { fetchProcessorBackpressure } from '../../api/systemAuditMetrics';
import { queryKeys } from '../../api/queryKeys';
import { YoloDetectorHealthCard } from './YoloDetectorHealthCard';
import { SystemCardShell } from './SystemCardShell';

type JobsListResponse = {
  jobs?: Array<{ id: string; status: string; label?: string }>;
};

export function CatalogOpsHubCard() {
  const { t } = useTranslation();
  const catalogQ = useQuery({
    queryKey: [...queryKeys.speciesDirectory.list, 'allowlist', 'hub'],
    queryFn: () => fetchBirdDirectory({ scope: 'allowlist', meta: true }),
    staleTime: 60_000,
  });
  const jobsQ = useQuery({
    queryKey: ['system', 'jobs'],
    queryFn: async () => {
      const r = await axios.get<JobsListResponse>(`${BASE_API_URL}/jobs`);
      return r.data;
    },
    staleTime: 10_000,
    refetchInterval: 15_000,
  });
  const bpQ = useQuery({
    queryKey: ['system', 'backpressure'],
    queryFn: fetchProcessorBackpressure,
    staleTime: 10_000,
    refetchInterval: 15_000,
  });

  const meta =
    catalogQ.data && typeof catalogQ.data === 'object' && 'meta' in catalogQ.data
      ? (catalogQ.data as { meta?: Record<string, unknown> }).meta
      : undefined;
  const cards = (meta?.catalog_cards as Record<string, unknown> | undefined) ?? {};
  const runningJobs =
    jobsQ.data?.jobs?.filter((j) => j.status === 'running').map((j) => j.id) ?? [];

  return (
    <SystemCardShell
      id="catalog-ops-hub"
      title={t('system.catalogOpsHubTitle')}
      description={t('system.catalogOpsHubDescription')}
    >
      <Stack spacing={2}>
        {catalogQ.isLoading ? <LinearProgress /> : null}
        {meta ? (
          <Stack direction="row" flexWrap="wrap" gap={1}>
            <Chip
              size="small"
              color="primary"
              label={t('system.catalogOpsCompletion', {
                pct: cards.completion_percent ?? meta.allowlist_incomplete,
                complete: cards.complete_cards ?? '—',
                total: cards.allowlist_total ?? meta.allowlist_total,
              })}
            />
            <Chip
              size="small"
              variant="outlined"
              label={t('system.catalogOpsAudio', {
                with: meta.catalog_with_audio ?? 0,
                missing: meta.catalog_missing_audio ?? 0,
              })}
            />
          </Stack>
        ) : null}
        {runningJobs.length > 0 ? (
          <Alert severity="info">
            {t('system.catalogOpsRunningJobs', { jobs: runningJobs.join(', ') })}
          </Alert>
        ) : null}
        {bpQ.data?.gauges ? (
          <Stack direction="row" flexWrap="wrap" gap={1}>
            {bpQ.data.gauges.classification_queue_depth != null ? (
              <Chip
                size="small"
                variant="outlined"
                label={t('system.backpressureClassifierQueue', {
                  depth: bpQ.data.gauges.classification_queue_depth,
                  max: bpQ.data.gauges.classification_queue_maxsize ?? '—',
                })}
              />
            ) : null}
            {bpQ.data.gauges.finalize_queue_depth != null ? (
              <Chip
                size="small"
                variant="outlined"
                color={
                  bpQ.data.gauges.finalize_queue_saturated ? 'warning' : 'default'
                }
                label={t('system.backpressureFinalizeQueue', {
                  depth: bpQ.data.gauges.finalize_queue_depth,
                })}
              />
            ) : null}
          </Stack>
        ) : null}
        <YoloDetectorHealthCard />
        <Stack direction="row" flexWrap="wrap" gap={1}>
          <Button component={RouterLink} to="/species" variant="outlined" size="small">
            {t('system.catalogOpsOpenCatalog')}
          </Button>
          <Button
            component={RouterLink}
            to="/species-directory"
            variant="outlined"
            size="small"
          >
            {t('system.catalogOpsOpenQuality')}
          </Button>
        </Stack>
      </Stack>
    </SystemCardShell>
  );
}
