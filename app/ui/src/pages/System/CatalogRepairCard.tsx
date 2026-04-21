import { useTranslation } from 'react-i18next';
import { useEffect, useLayoutEffect, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Chip from '@mui/material/Chip';
import LinearProgress from '@mui/material/LinearProgress';
import Typography from '@mui/material/Typography';
import {
  fetchCatalogRepairStatus,
  getApiErrorMessage,
  startCatalogRepair,
} from '../../api/api';
import { SystemCardShell } from './SystemCardShell';

export function CatalogRepairCard() {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const [actionError, setActionError] = useState<string | null>(null);
  const { data, isLoading, error } = useQuery({
    queryKey: ['catalog-repair-status'],
    queryFn: fetchCatalogRepairStatus,
    staleTime: 5_000,
    refetchInterval: (q) =>
      q.state.data?.status === 'running' ? 4_000 : 20_000,
    // Иначе во вкладке в фоне таймер «следующий прогон» замирает на десятки минут.
    refetchIntervalInBackground: true,
  });

  const startMutation = useMutation({
    mutationFn: (limit: number) => startCatalogRepair(limit),
    onSuccess: async () => {
      setActionError(null);
      await qc.invalidateQueries({ queryKey: ['catalog-repair-status'] });
    },
    onError: (mutationError: unknown) => {
      setActionError(
        getApiErrorMessage(mutationError, t('system.catalogRepairStartFailed')),
      );
    },
  });

  const scheduleNextSec = data?.schedule?.next_run_in_sec;
  const [nextRunAnchorMs, setNextRunAnchorMs] = useState(() => Date.now());
  const [nextRunAnchorSec, setNextRunAnchorSec] = useState(0);
  useLayoutEffect(() => {
    if (scheduleNextSec == null) return;
    setNextRunAnchorMs(Date.now());
    setNextRunAnchorSec(Math.max(0, scheduleNextSec));
  }, [scheduleNextSec]);

  const [, setTick] = useState(0);
  useEffect(() => {
    if (!data?.schedule?.autorun_enabled || scheduleNextSec == null) return;
    const id = window.setInterval(() => setTick((n) => n + 1), 1000);
    return () => window.clearInterval(id);
  }, [data?.schedule?.autorun_enabled, scheduleNextSec]);

  if (isLoading) return <LinearProgress />;
  if (error || !data)
    return (
      <Alert severity="warning" variant="outlined">{t('system.catalogRepairLoadError')}</Alert>
    );

  const liveNextSec = Math.max(
    0,
    nextRunAnchorSec - Math.floor((Date.now() - nextRunAnchorMs) / 1000),
  );
  const nextRunMin = Math.ceil(liveNextSec / 60);
  const running = data.status === 'running';
  const cov = data.coverage_now ?? {
    completion_percent: 0,
    complete_cards: 0,
    allowlist_total: 0,
    allowlist_lines_matched: 0,
    species_matched: 0,
    with_image: 0,
    with_description: 0,
  };
  const hasIssue = Boolean(
    actionError || data.error || data.status === 'error',
  );
  const statusLabel = hasIssue
    ? t('system.jobStatus.error')
    : running
      ? t('system.catalogRepairRunning')
      : t('system.catalogRepairReady');

  return (
    <SystemCardShell
      title={t('system.catalogRepairTitle')}
      description={t('system.catalogRepairWhatItDoes')}
      statusLabel={statusLabel}
      statusTone={hasIssue ? 'error' : running ? 'warning' : 'success'}
      actions={
        <Button
          size="small"
          variant="contained"
          disabled={running || startMutation.isPending}
          onClick={() => startMutation.mutate(6000)}
        >
          {running
            ? t('system.catalogRepairRunning')
            : t('system.catalogRepairStart')}
        </Button>
      }
    >
      <Box>
        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, mb: 1.5 }}>
          <Chip
            size="small"
            label={t('system.catalogRepairCompletion', {
              p: cov.completion_percent,
            })}
          />
          <Chip
            size="small"
            variant="outlined"
            label={t('system.catalogRepairSpeciesMatched', {
              lines: cov.allowlist_lines_matched ?? cov.species_matched ?? 0,
              total: cov.allowlist_total,
              unique: cov.species_matched ?? 0,
            })}
          />
          <Chip
            size="small"
            variant="outlined"
            label={t('system.catalogRepairCompleteCards', {
              n: cov.complete_cards,
              total: cov.allowlist_total,
            })}
          />
          <Chip
            size="small"
            variant="outlined"
            label={t('system.catalogRepairWithImage', { n: cov.with_image })}
          />
          <Chip
            size="small"
            variant="outlined"
            label={t('system.catalogRepairWithDescription', {
              n: cov.with_description,
            })}
          />
          {data.schedule?.autorun_enabled && (
            <Chip
              size="small"
              variant="outlined"
              label={t('system.catalogRepairNextRun', { n: nextRunMin })}
            />
          )}
        </Box>

        {running && <LinearProgress sx={{ mb: 1.5 }} />}
        {actionError ? (
          <Alert severity="error" variant="outlined" sx={{ mb: 1.5 }}>
            {actionError}
          </Alert>
        ) : null}
        {data.error && (
          <Alert severity="warning" variant="outlined" sx={{ mb: 1.5 }}>
            {data.error}
          </Alert>
        )}
        {data.result && (
          <>
            <Typography variant="body2" color="text.secondary">
              {t('system.catalogRepairLastRun', {
                checked: data.result.checked,
                fixed: data.result.metadata_fixed,
                swapped: data.result.images_replaced_from_inat,
                science: data.result.images_realigned_allowlist_science ?? 0,
                missing: data.result.still_missing,
              })}
            </Typography>
            {data.result.enrich_exceptions ? (
              <Typography variant="body2" color="warning.main" sx={{ mt: 0.5 }}>
                {t('system.catalogRepairEnrichErrors', {
                  n: data.result.enrich_exceptions,
                })}
              </Typography>
            ) : null}
          </>
        )}
      </Box>
    </SystemCardShell>
  );
}
