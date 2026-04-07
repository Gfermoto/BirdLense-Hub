import { useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import axios from 'axios';
import { Alert, Button, Card, CardContent, Chip, LinearProgress, Stack, Typography } from '@mui/material';
import { BASE_API_URL } from '../../api/api';

type JobStatus = {
  status: string;
  result?: Record<string, unknown> | null;
  error?: string | null;
  progress?: Record<string, unknown> | null;
};

function statusLabel(status?: JobStatus | null): string {
  if (!status) return 'idle';
  if (status.error) return 'error';
  if (status.status === 'running') return 'running';
  if (status.status === 'done') return 'done';
  return status.status || 'idle';
}

export function AutomationCard() {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const [fusionExportPolling, setFusionExportPolling] = useState(false);
  const [fusionEvalPolling, setFusionEvalPolling] = useState(false);
  const [proxyPolling, setProxyPolling] = useState(false);
  const [lastInfo, setLastInfo] = useState<string | null>(null);

  const fusionExportQuery = useQuery({
    queryKey: ['fusion-export-status'],
    queryFn: async (): Promise<JobStatus> => {
      const response = await axios.get(`${BASE_API_URL}/system/fusion/export/status`, {
        withCredentials: true,
      });
      return response.data;
    },
    enabled: fusionExportPolling,
    refetchInterval: (q) => (q.state.data?.status === 'running' ? 2_500 : false),
    staleTime: 0,
  });

  const fusionEvalQuery = useQuery({
    queryKey: ['fusion-eval-status'],
    queryFn: async (): Promise<JobStatus> => {
      const response = await axios.get(`${BASE_API_URL}/system/fusion/eval/status`, {
        withCredentials: true,
      });
      return response.data;
    },
    enabled: fusionEvalPolling,
    refetchInterval: (q) => (q.state.data?.status === 'running' ? 2_500 : false),
    staleTime: 0,
  });

  const proxyRefreshQuery = useQuery({
    queryKey: ['telegram-proxy-refresh-status'],
    queryFn: async (): Promise<JobStatus> => {
      const response = await axios.get(`${BASE_API_URL}/system/telegram-proxy/refresh/status`, {
        withCredentials: true,
      });
      return response.data;
    },
    enabled: proxyPolling,
    refetchInterval: (q) => (q.state.data?.status === 'running' ? 2_500 : false),
    staleTime: 0,
  });

  const trackRegenMutation = useMutation({
    mutationFn: async () => {
      const response = await axios.post(
        `${BASE_API_URL}/system/regenerate-tracks`,
        { force: false },
        { withCredentials: true },
      );
      return response.data as { message?: string };
    },
    onSuccess: (data) => {
      setLastInfo(data.message || t('system.automationTrackRegenStarted'));
      qc.invalidateQueries({ queryKey: ['system-regenerate-tracks-status'] });
    },
  });

  const fusionExportMutation = useMutation({
    mutationFn: async () => {
      const response = await axios.post(
        `${BASE_API_URL}/system/fusion/export`,
        {},
        { withCredentials: true },
      );
      return response.data as { message?: string };
    },
    onSuccess: (data) => {
      setFusionExportPolling(true);
      setLastInfo(data.message || t('system.automationFusionExportStarted'));
    },
  });

  const fusionEvalMutation = useMutation({
    mutationFn: async () => {
      const response = await axios.post(
        `${BASE_API_URL}/system/fusion/eval`,
        {},
        { withCredentials: true },
      );
      return response.data as { message?: string };
    },
    onSuccess: (data) => {
      setFusionEvalPolling(true);
      setLastInfo(data.message || t('system.automationFusionEvalStarted'));
    },
  });

  const proxyRefreshMutation = useMutation({
    mutationFn: async () => {
      const response = await axios.post(
        `${BASE_API_URL}/system/telegram-proxy/refresh`,
        {},
        { withCredentials: true },
      );
      return response.data as { message?: string };
    },
    onSuccess: (data) => {
      setProxyPolling(true);
      setLastInfo(data.message || t('system.automationProxyRefreshStarted'));
    },
  });

  const maintenanceMutations = useMemo(
    () => ({
      seed: async () =>
        (
          await axios.post(
            `${BASE_API_URL}/system/species-registry/seed`,
            {},
            { withCredentials: true },
          )
        ).data,
      backfill: async () =>
        (
          await axios.post(
            `${BASE_API_URL}/system/species-registry/backfill`,
            { dry_run: false },
            { withCredentials: true },
          )
        ).data,
      enrich: async () =>
        (
          await axios.post(
            `${BASE_API_URL}/system/species-registry/enrich-metadata/start`,
            { limit: 300, retry_failed_only: false },
            { withCredentials: true },
          )
        ).data,
      materialize: async () =>
        (
          await axios.post(
            `${BASE_API_URL}/system/species-registry/materialize-allowlist`,
            { dry_run: false, fill_metadata: true },
            { withCredentials: true },
          )
        ).data,
      merge: async () =>
        (
          await axios.post(
            `${BASE_API_URL}/system/merge-duplicate-species`,
            {},
            { withCredentials: true },
          )
        ).data,
      reconcile: async () =>
        (
          await axios.post(
            `${BASE_API_URL}/system/species-catalog/reconcile`,
            { dry_run: false },
            { withCredentials: true },
          )
        ).data,
    }),
    [],
  );

  useEffect(() => {
    if (fusionExportQuery.data?.status && fusionExportQuery.data.status !== 'running') {
      setFusionExportPolling(false);
    }
  }, [fusionExportQuery.data]);

  useEffect(() => {
    if (fusionEvalQuery.data?.status && fusionEvalQuery.data.status !== 'running') {
      setFusionEvalPolling(false);
    }
  }, [fusionEvalQuery.data]);

  useEffect(() => {
    if (proxyRefreshQuery.data?.status && proxyRefreshQuery.data.status !== 'running') {
      setProxyPolling(false);
    }
  }, [proxyRefreshQuery.data]);

  const downloadFusionExport = () => {
    window.open(`${BASE_API_URL}/system/fusion/export/download`, '_blank', 'noopener,noreferrer');
  };

  const runMaintenanceAction = async (
    label: string,
    fn: () => Promise<Record<string, unknown>>,
  ) => {
    try {
      const data = await fn();
      setLastInfo(`${label}: ${JSON.stringify(data)}`);
      return data;
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      setLastInfo(`${label}: ${message}`);
      throw error;
    }
  };

  return (
    <Card>
      <CardContent>
        <Typography variant="h6" sx={{ mb: 1 }}>
          {t('system.automationTitle')}
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          {t('system.automationHint')}
        </Typography>

        {(fusionExportQuery.data?.status === 'running' ||
          fusionEvalQuery.data?.status === 'running' ||
          proxyRefreshQuery.data?.status === 'running' ||
          trackRegenMutation.isPending) && <LinearProgress sx={{ mb: 2 }} />}

        {lastInfo && (
          <Alert severity="info" sx={{ mb: 2 }} onClose={() => setLastInfo(null)}>
            {lastInfo}
          </Alert>
        )}

        <Stack direction="row" flexWrap="wrap" gap={1} sx={{ mb: 2 }}>
          <Button
            variant="contained"
            onClick={() => fusionExportMutation.mutate()}
            disabled={fusionExportMutation.isPending || fusionExportQuery.data?.status === 'running'}
          >
            {t('system.automationFusionExport')}
          </Button>
          <Button
            variant="outlined"
            onClick={downloadFusionExport}
          >
            {t('system.automationFusionExportDownload')}
          </Button>
          <Button
            variant="contained"
            onClick={() => fusionEvalMutation.mutate()}
            disabled={fusionEvalMutation.isPending || fusionEvalQuery.data?.status === 'running'}
          >
            {t('system.automationFusionEval')}
          </Button>
          <Button
            variant="outlined"
            onClick={() => proxyRefreshMutation.mutate()}
            disabled={proxyRefreshMutation.isPending || proxyRefreshQuery.data?.status === 'running'}
          >
            {t('system.automationTelegramProxyRefresh')}
          </Button>
          <Button
            variant="outlined"
            onClick={() => trackRegenMutation.mutate()}
            disabled={trackRegenMutation.isPending}
          >
            {t('system.automationBulkTrackRegen')}
          </Button>
        </Stack>

        <Stack direction="row" flexWrap="wrap" gap={1} sx={{ mb: 2 }}>
          <Button
            variant="outlined"
            onClick={() => {
              void runMaintenanceAction(t('system.automationRegistrySeed'), maintenanceMutations.seed).catch(() => undefined);
            }}
          >
            {t('system.automationRegistrySeed')}
          </Button>
          <Button
            variant="outlined"
            onClick={() => {
              void runMaintenanceAction(t('system.automationRegistryBackfill'), maintenanceMutations.backfill).catch(() => undefined);
            }}
          >
            {t('system.automationRegistryBackfill')}
          </Button>
          <Button
            variant="outlined"
            onClick={() => {
              void runMaintenanceAction(t('system.automationRegistryEnrich'), maintenanceMutations.enrich).catch(() => undefined);
            }}
          >
            {t('system.automationRegistryEnrich')}
          </Button>
          <Button
            variant="outlined"
            onClick={() => {
              void runMaintenanceAction(t('system.automationRegistryMaterialize'), maintenanceMutations.materialize).catch(() => undefined);
            }}
          >
            {t('system.automationRegistryMaterialize')}
          </Button>
          <Button
            variant="outlined"
            onClick={() => {
              void runMaintenanceAction(t('system.automationMergeDuplicateSpecies'), maintenanceMutations.merge).catch(() => undefined);
            }}
          >
            {t('system.automationMergeDuplicateSpecies')}
          </Button>
          <Button
            variant="outlined"
            onClick={() => {
              void runMaintenanceAction(t('system.automationSpeciesCatalogReconcile'), maintenanceMutations.reconcile).catch(() => undefined);
            }}
          >
            {t('system.automationSpeciesCatalogReconcile')}
          </Button>
        </Stack>

        <Stack direction="row" flexWrap="wrap" gap={1}>
          <Chip size="small" variant="outlined" label={`${t('system.automationFusionExportStatus')}: ${statusLabel(fusionExportQuery.data)}`} />
          <Chip size="small" variant="outlined" label={`${t('system.automationFusionEvalStatus')}: ${statusLabel(fusionEvalQuery.data)}`} />
          <Chip size="small" variant="outlined" label={`${t('system.automationProxyRefreshStatus')}: ${statusLabel(proxyRefreshQuery.data)}`} />
          <Chip size="small" variant="outlined" label={`${t('system.automationTrackRegenStatus')}: ${trackRegenMutation.isPending ? 'running' : 'idle'}`} />
        </Stack>

        {(fusionExportQuery.data?.result || fusionExportQuery.data?.error) && (
          <Alert severity={fusionExportQuery.data?.error ? 'error' : 'success'} sx={{ mt: 2 }}>
            {fusionExportQuery.data?.error
              ? fusionExportQuery.data.error
              : JSON.stringify(fusionExportQuery.data.result)}
          </Alert>
        )}

        {(fusionEvalQuery.data?.result || fusionEvalQuery.data?.error) && (
          <Alert severity={fusionEvalQuery.data?.error ? 'error' : 'success'} sx={{ mt: 2 }}>
            {fusionEvalQuery.data?.error
              ? fusionEvalQuery.data.error
              : JSON.stringify(fusionEvalQuery.data.result)}
          </Alert>
        )}

        {(proxyRefreshQuery.data?.result || proxyRefreshQuery.data?.error) && (
          <Alert severity={proxyRefreshQuery.data?.error ? 'error' : 'success'} sx={{ mt: 2 }}>
            {proxyRefreshQuery.data?.error
              ? proxyRefreshQuery.data.error
              : JSON.stringify(proxyRefreshQuery.data.result)}
          </Alert>
        )}

        {trackRegenMutation.error && (
          <Alert severity="error" sx={{ mt: 2 }}>
            {trackRegenMutation.error instanceof Error
              ? trackRegenMutation.error.message
              : t('system.automationTrackRegenError')}
          </Alert>
        )}
      </CardContent>
    </Card>
  );
}
