import { useTranslation } from 'react-i18next';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Card from '@mui/material/Card';
import CardContent from '@mui/material/CardContent';
import Chip from '@mui/material/Chip';
import LinearProgress from '@mui/material/LinearProgress';
import Typography from '@mui/material/Typography';
import { fetchCatalogRepairStatus, startCatalogRepair } from '../../api/api';

export function CatalogRepairCard() {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const { data, isLoading, error } = useQuery({
    queryKey: ['catalog-repair-status'],
    queryFn: fetchCatalogRepairStatus,
    staleTime: 5_000,
    refetchInterval: (q) => (q.state.data?.status === 'running' ? 4_000 : 20_000),
  });

  const startMutation = useMutation({
    mutationFn: (limit: number) => startCatalogRepair(limit),
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ['catalog-repair-status'] });
    },
  });

  if (isLoading) return <LinearProgress />;
  if (error || !data) return <Alert severity="warning">{t('system.catalogRepairLoadError')}</Alert>;

  const running = data.status === 'running';
  const cov = data.coverage_now;
  const nextRunSec = Math.max(0, data.schedule?.next_run_in_sec ?? 0);
  const nextRunMin = Math.ceil(nextRunSec / 60);

  return (
    <Card>
      <CardContent>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', gap: 1, alignItems: 'center', mb: 1 }}>
          <Typography variant="h6">{t('system.catalogRepairTitle')}</Typography>
          <Button
            size="small"
            variant="contained"
            disabled={running || startMutation.isPending}
            onClick={() => startMutation.mutate(6000)}
          >
            {running ? t('system.catalogRepairRunning') : t('system.catalogRepairStart')}
          </Button>
        </Box>

        <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
          {t('system.catalogRepairWhatItDoes')}
        </Typography>

        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, mb: 1.5 }}>
          <Chip size="small" label={t('system.catalogRepairCompletion', { p: cov.completion_percent })} />
          <Chip size="small" variant="outlined" label={t('system.catalogRepairCompleteCards', { n: cov.complete_cards, total: cov.allowlist_total })} />
          <Chip size="small" variant="outlined" label={t('system.catalogRepairWithImage', { n: cov.with_image })} />
          <Chip size="small" variant="outlined" label={t('system.catalogRepairWithDescription', { n: cov.with_description })} />
          {data.schedule?.autorun_enabled && (
            <Chip
              size="small"
              variant="outlined"
              label={t('system.catalogRepairNextRun', { n: nextRunMin })}
            />
          )}
        </Box>

        {running && <LinearProgress sx={{ mb: 1.5 }} />}
        {data.error && <Alert severity="warning" sx={{ mb: 1.5 }}>{data.error}</Alert>}
        {data.result && (
          <Typography variant="body2" color="text.secondary">
            {t('system.catalogRepairLastRun', {
              checked: data.result.checked,
              fixed: data.result.metadata_fixed,
              swapped: data.result.images_replaced_from_inat,
              science: data.result.images_realigned_allowlist_science ?? 0,
              missing: data.result.still_missing,
            })}
          </Typography>
        )}
      </CardContent>
    </Card>
  );
}
