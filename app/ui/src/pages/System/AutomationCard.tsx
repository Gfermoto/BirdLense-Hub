import { useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import axios from 'axios';
import {
  Accordion,
  AccordionDetails,
  AccordionSummary,
  Alert,
  Button,
  Card,
  CardContent,
  Chip,
  LinearProgress,
  Stack,
  Tooltip,
  Typography,
} from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
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
  const [fusionExportPolling, setFusionExportPolling] = useState(false);
  const [fusionEvalPolling, setFusionEvalPolling] = useState(false);
  const [maintenanceAction, setMaintenanceAction] = useState<string | null>(null);
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
      brokenVideosPurgePreview: async () =>
        (
          await axios.post(
            `${BASE_API_URL}/system/diagnostics/broken-videos/purge`,
            { dry_run: true, max_scan: 200_000 },
            { withCredentials: true },
          )
        ).data,
      brokenVideosPurgeBatch: async (confirmText: string) =>
        (
          await axios.post(
            `${BASE_API_URL}/system/diagnostics/broken-videos/purge`,
            {
              dry_run: false,
              confirm_text: confirmText,
              limit: 500,
            },
            { withCredentials: true },
          )
        ).data,
      noSpeciesVideosPurgePreview: async () =>
        (
          await axios.post(
            `${BASE_API_URL}/system/diagnostics/no-species-videos/purge`,
            { dry_run: true },
            { withCredentials: true },
          )
        ).data,
      noSpeciesVideosPurgeBatch: async (confirmText: string) =>
        (
          await axios.post(
            `${BASE_API_URL}/system/diagnostics/no-species-videos/purge`,
            {
              dry_run: false,
              confirm_text: confirmText,
              limit: 500,
            },
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

  const downloadFusionExport = () => {
    window.open(`${BASE_API_URL}/system/fusion/export/download`, '_blank', 'noopener,noreferrer');
  };

  const runMaintenanceAction = async (
    label: string,
    fn: () => Promise<Record<string, unknown>>,
  ) => {
    try {
      setMaintenanceAction(label);
      setLastInfo(`${label}: ...`);
      const data = await fn();
      setLastInfo(`${label}: ${JSON.stringify(data)}`);
      return data;
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      setLastInfo(`${label}: ${message}`);
      throw error;
    } finally {
      setMaintenanceAction((current) => (current === label ? null : current));
    }
  };

  const confirmAndRunMaintenanceAction = async (
    label: string,
    hint: string,
    fn: () => Promise<Record<string, unknown>>,
  ) => {
    const confirmed = window.confirm(`${label}\n\n${hint}`);
    if (!confirmed) return;
    await runMaintenanceAction(label, fn);
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
          maintenanceAction !== null) && <LinearProgress sx={{ mb: 2 }} />}

        {lastInfo && (
          <Alert severity="info" sx={{ mb: 2 }} onClose={() => setLastInfo(null)}>
            {lastInfo}
          </Alert>
        )}

        <Alert severity="warning" sx={{ mb: 2 }}>
          {t('system.automationDangerNote')}
        </Alert>

        <Stack direction="row" flexWrap="wrap" gap={1} sx={{ mb: 2 }}>
          <Tooltip title={t('system.automationFusionExportHint')} describeChild>
            <span>
              <Button
                variant="contained"
                onClick={() => fusionExportMutation.mutate()}
                disabled={fusionExportMutation.isPending || fusionExportQuery.data?.status === 'running'}
              >
                {t('system.automationFusionExport')}
              </Button>
            </span>
          </Tooltip>
          <Tooltip title={t('system.automationFusionExportDownloadHint')} describeChild>
            <span>
              <Button variant="outlined" onClick={downloadFusionExport}>
                {t('system.automationFusionExportDownload')}
              </Button>
            </span>
          </Tooltip>
          <Tooltip title={t('system.automationFusionEvalHint')} describeChild>
            <span>
              <Button
                variant="contained"
                onClick={() => fusionEvalMutation.mutate()}
                disabled={fusionEvalMutation.isPending || fusionEvalQuery.data?.status === 'running'}
              >
                {t('system.automationFusionEval')}
              </Button>
            </span>
          </Tooltip>
        </Stack>

        <Accordion sx={{ mb: 2 }}>
          <AccordionSummary expandIcon={<ExpandMoreIcon />}>
            <Typography variant="subtitle2">{t('system.automationDangerZone')}</Typography>
          </AccordionSummary>
          <AccordionDetails>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
              {t('system.automationAdminMaintenanceHint')}
            </Typography>
            <Stack direction="row" flexWrap="wrap" gap={1}>
              <Tooltip title={t('system.automationRegistrySeedHint')} describeChild>
                <span>
                  <Button
                    variant="outlined"
                    color="warning"
                    disabled={maintenanceAction !== null}
                    onClick={() => {
                      void confirmAndRunMaintenanceAction(
                        t('system.automationRegistrySeed'),
                        t('system.automationRegistrySeedHint'),
                        maintenanceMutations.seed,
                      ).catch(() => undefined);
                    }}
                  >
                    {t('system.automationRegistrySeed')}
                  </Button>
                </span>
              </Tooltip>
              <Tooltip title={t('system.automationRegistryBackfillHint')} describeChild>
                <span>
                  <Button
                    variant="outlined"
                    color="warning"
                    disabled={maintenanceAction !== null}
                    onClick={() => {
                      void confirmAndRunMaintenanceAction(
                        t('system.automationRegistryBackfill'),
                        t('system.automationRegistryBackfillHint'),
                        maintenanceMutations.backfill,
                      ).catch(() => undefined);
                    }}
                  >
                    {t('system.automationRegistryBackfill')}
                  </Button>
                </span>
              </Tooltip>
              <Tooltip title={t('system.automationRegistryEnrichHint')} describeChild>
                <span>
                  <Button
                    variant="outlined"
                    color="warning"
                    disabled={maintenanceAction !== null}
                    onClick={() => {
                      void confirmAndRunMaintenanceAction(
                        t('system.automationRegistryEnrich'),
                        t('system.automationRegistryEnrichHint'),
                        maintenanceMutations.enrich,
                      ).catch(() => undefined);
                    }}
                  >
                    {t('system.automationRegistryEnrich')}
                  </Button>
                </span>
              </Tooltip>
              <Tooltip title={t('system.automationRegistryMaterializeHint')} describeChild>
                <span>
                  <Button
                    variant="outlined"
                    color="warning"
                    disabled={maintenanceAction !== null}
                    onClick={() => {
                      void confirmAndRunMaintenanceAction(
                        t('system.automationRegistryMaterialize'),
                        t('system.automationRegistryMaterializeHint'),
                        maintenanceMutations.materialize,
                      ).catch(() => undefined);
                    }}
                  >
                    {t('system.automationRegistryMaterialize')}
                  </Button>
                </span>
              </Tooltip>
              <Tooltip title={t('system.automationMergeDuplicateSpeciesHint')} describeChild>
                <span>
                  <Button
                    variant="outlined"
                    color="warning"
                    disabled={maintenanceAction !== null}
                    onClick={() => {
                      void confirmAndRunMaintenanceAction(
                        t('system.automationMergeDuplicateSpecies'),
                        t('system.automationMergeDuplicateSpeciesHint'),
                        maintenanceMutations.merge,
                      ).catch(() => undefined);
                    }}
                  >
                    {t('system.automationMergeDuplicateSpecies')}
                  </Button>
                </span>
              </Tooltip>
              <Tooltip title={t('system.automationSpeciesCatalogReconcileHint')} describeChild>
                <span>
                  <Button
                    variant="outlined"
                    color="warning"
                    disabled={maintenanceAction !== null}
                    onClick={() => {
                      void confirmAndRunMaintenanceAction(
                        t('system.automationSpeciesCatalogReconcile'),
                        t('system.automationSpeciesCatalogReconcileHint'),
                        maintenanceMutations.reconcile,
                      ).catch(() => undefined);
                    }}
                  >
                    {t('system.automationSpeciesCatalogReconcile')}
                  </Button>
                </span>
              </Tooltip>
              <Tooltip title={t('system.automationBrokenVideosPurgePreviewHint')} describeChild>
                <span>
                  <Button
                    variant="outlined"
                    color="warning"
                    disabled={maintenanceAction !== null}
                    onClick={() => {
                      void runMaintenanceAction(
                        t('system.automationBrokenVideosPurgePreview'),
                        maintenanceMutations.brokenVideosPurgePreview,
                      ).catch(() => undefined);
                    }}
                  >
                    {t('system.automationBrokenVideosPurgePreview')}
                  </Button>
                </span>
              </Tooltip>
              <Tooltip title={t('system.automationBrokenVideosPurgeBatchHint')} describeChild>
                <span>
                  <Button
                    variant="outlined"
                    color="error"
                    disabled={maintenanceAction !== null}
                    onClick={() => {
                      const phrase = window.prompt(
                        t('system.automationBrokenVideosPurgePrompt'),
                        'purge_all_broken_video_rows',
                      );
                      if (phrase === null) return;
                      const trimmed = phrase.trim();
                      if (!trimmed) return;
                      void runMaintenanceAction(
                        t('system.automationBrokenVideosPurgeBatch'),
                        () => maintenanceMutations.brokenVideosPurgeBatch(trimmed),
                      ).catch(() => undefined);
                    }}
                  >
                    {t('system.automationBrokenVideosPurgeBatch')}
                  </Button>
                </span>
              </Tooltip>
              <Tooltip title={t('system.automationNoSpeciesVideosPurgePreviewHint')} describeChild>
                <span>
                  <Button
                    variant="outlined"
                    color="warning"
                    disabled={maintenanceAction !== null}
                    onClick={() => {
                      void runMaintenanceAction(
                        t('system.automationNoSpeciesVideosPurgePreview'),
                        maintenanceMutations.noSpeciesVideosPurgePreview,
                      ).catch(() => undefined);
                    }}
                  >
                    {t('system.automationNoSpeciesVideosPurgePreview')}
                  </Button>
                </span>
              </Tooltip>
              <Tooltip title={t('system.automationNoSpeciesVideosPurgeBatchHint')} describeChild>
                <span>
                  <Button
                    variant="outlined"
                    color="error"
                    disabled={maintenanceAction !== null}
                    onClick={() => {
                      const phrase = window.prompt(
                        t('system.automationNoSpeciesVideosPurgePrompt'),
                        'purge_videos_without_species',
                      );
                      if (phrase === null) return;
                      const trimmed = phrase.trim();
                      if (!trimmed) return;
                      void runMaintenanceAction(
                        t('system.automationNoSpeciesVideosPurgeBatch'),
                        () => maintenanceMutations.noSpeciesVideosPurgeBatch(trimmed),
                      ).catch(() => undefined);
                    }}
                  >
                    {t('system.automationNoSpeciesVideosPurgeBatch')}
                  </Button>
                </span>
              </Tooltip>
            </Stack>
          </AccordionDetails>
        </Accordion>

        <Stack direction="row" flexWrap="wrap" gap={1}>
          <Chip size="small" variant="outlined" label={`${t('system.automationFusionExportStatus')}: ${statusLabel(fusionExportQuery.data)}`} />
          <Chip size="small" variant="outlined" label={`${t('system.automationFusionEvalStatus')}: ${statusLabel(fusionEvalQuery.data)}`} />
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

      </CardContent>
    </Card>
  );
}
