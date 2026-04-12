import { useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import axios from 'axios';
import Accordion from '@mui/material/Accordion';
import AccordionDetails from '@mui/material/AccordionDetails';
import AccordionSummary from '@mui/material/AccordionSummary';
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Card from '@mui/material/Card';
import CardContent from '@mui/material/CardContent';
import Chip from '@mui/material/Chip';
import CircularProgress from '@mui/material/CircularProgress';
import Dialog from '@mui/material/Dialog';
import DialogActions from '@mui/material/DialogActions';
import DialogContent from '@mui/material/DialogContent';
import DialogTitle from '@mui/material/DialogTitle';
import LinearProgress from '@mui/material/LinearProgress';
import Paper from '@mui/material/Paper';
import Stack from '@mui/material/Stack';
import Table from '@mui/material/Table';
import TableBody from '@mui/material/TableBody';
import TableCell from '@mui/material/TableCell';
import TableContainer from '@mui/material/TableContainer';
import TableHead from '@mui/material/TableHead';
import TableRow from '@mui/material/TableRow';
import Tooltip from '@mui/material/Tooltip';
import Typography from '@mui/material/Typography';
import type { TFunction } from 'i18next';
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

type BirdnetSpeciesFifoRow = {
  display_label: string;
  canonical_for_video: string;
  scientific_name?: string | null;
  active: number;
  last_heard_at?: string;
  seconds_since_heard?: number;
  event_count: number;
};

type BirdnetFifoDialogSnapshot = {
  queue_len?: number;
  fifo_cap?: number;
  fifo_fill_ratio?: number;
  mqtt_connected?: boolean;
  processor_pid?: number;
  species_hearing?: {
    active_within_hours?: number;
    by_species?: Record<string, { active?: number }>;
  };
  species_fifo_table?: BirdnetSpeciesFifoRow[];
  species_counts?: Record<string, number>;
};

function formatAgoCompact(seconds: number, t: TFunction): string {
  const s = Math.max(0, Math.floor(seconds));
  if (s < 60) return t('system.automationBirdnetFifoAgoSeconds', { n: s });
  if (s < 3600) return t('system.automationBirdnetFifoAgoMinutes', { n: Math.floor(s / 60) });
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  if (m <= 0) return t('system.automationBirdnetFifoAgoHoursOnly', { n: h });
  return t('system.automationBirdnetFifoAgoHoursMinutes', { h, m });
}

export function AutomationCard() {
  const { t } = useTranslation();
  const [fusionExportPolling, setFusionExportPolling] = useState(false);
  const [fusionEvalPolling, setFusionEvalPolling] = useState(false);
  const [maintenanceAction, setMaintenanceAction] = useState<string | null>(null);
  const [lastInfo, setLastInfo] = useState<string | null>(null);
  const [birdnetFifoOpen, setBirdnetFifoOpen] = useState(false);
  const [birdnetFifoLoading, setBirdnetFifoLoading] = useState(false);
  const [birdnetFifoError, setBirdnetFifoError] = useState<string | null>(null);
  const [birdnetFifoRaw, setBirdnetFifoRaw] = useState<Record<string, unknown> | null>(null);

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

  const birdnetFifoSnap = (birdnetFifoRaw?.snapshot || null) as BirdnetFifoDialogSnapshot | null;

  const openBirdnetFifoDialog = async () => {
    setBirdnetFifoOpen(true);
    setBirdnetFifoLoading(true);
    setBirdnetFifoError(null);
    setBirdnetFifoRaw(null);
    try {
      const { data } = await axios.get<Record<string, unknown>>(`${BASE_API_URL}/system/diagnostics/birdnet-fifo`, {
        withCredentials: true,
      });
      setBirdnetFifoRaw(data);
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      setBirdnetFifoError(msg || t('system.automationBirdnetFifoLoadError'));
    } finally {
      setBirdnetFifoLoading(false);
    }
  };

  const copyBirdnetFifoJson = async () => {
    if (!birdnetFifoRaw) return;
    try {
      await navigator.clipboard.writeText(JSON.stringify(birdnetFifoRaw, null, 2));
    } catch {
      /* ignore */
    }
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

        <Typography variant="subtitle2" sx={{ mb: 1 }}>
          {t('system.automationDiagnosticsTitle')}
        </Typography>
        <Stack direction="row" flexWrap="wrap" gap={1} sx={{ mb: 2 }}>
          <Tooltip title={t('system.automationBirdnetFifoSnapshotHint')} describeChild>
            <span>
              <Button
                variant="outlined"
                disabled={maintenanceAction !== null || birdnetFifoLoading}
                onClick={() => {
                  void openBirdnetFifoDialog();
                }}
              >
                {t('system.automationBirdnetFifoSnapshot')}
              </Button>
            </span>
          </Tooltip>
        </Stack>

        <Dialog
          open={birdnetFifoOpen}
          onClose={() => setBirdnetFifoOpen(false)}
          maxWidth="lg"
          fullWidth
        >
          <DialogTitle sx={{ pb: 0.5 }}>
            {t('system.automationBirdnetFifoDialogTitle')}
            <Typography variant="caption" color="text.secondary" display="block" sx={{ mt: 0.75, fontWeight: 400 }}>
              {t('system.automationBirdnetFifoUiReviewHint')}
            </Typography>
          </DialogTitle>
          <DialogContent dividers>
            {birdnetFifoLoading && (
              <Stack alignItems="center" py={3}>
                <CircularProgress size={32} />
              </Stack>
            )}
            {!birdnetFifoLoading && birdnetFifoError && (
              <Alert severity="error">{t('system.automationBirdnetFifoLoadError')}</Alert>
            )}
            {!birdnetFifoLoading && !birdnetFifoError && birdnetFifoRaw && !birdnetFifoRaw.available && (
              <Alert severity="warning">{t('system.automationBirdnetFifoUnavailable')}</Alert>
            )}
            {!birdnetFifoLoading && !birdnetFifoError && birdnetFifoSnap && (
              <Stack spacing={2.5}>
                <Paper variant="outlined" sx={{ p: 1.5 }}>
                  <Typography variant="subtitle2" gutterBottom>
                    {t('system.automationBirdnetFifoBufferTitle')}
                  </Typography>
                  <LinearProgress
                    variant="determinate"
                    value={Math.min(
                      100,
                      Math.round(
                        (typeof birdnetFifoSnap.fifo_fill_ratio === 'number'
                          ? birdnetFifoSnap.fifo_fill_ratio
                          : birdnetFifoSnap.fifo_cap
                            ? Number(birdnetFifoSnap.queue_len || 0) / Number(birdnetFifoSnap.fifo_cap)
                            : 0) * 100,
                      ),
                    )}
                    sx={{ height: 8, borderRadius: 1, mb: 1 }}
                  />
                  <Typography variant="body2" color="text.secondary">
                    {t('system.automationBirdnetFifoBufferHint', {
                      pct: Math.min(
                        100,
                        Math.round(
                          (typeof birdnetFifoSnap.fifo_fill_ratio === 'number'
                            ? birdnetFifoSnap.fifo_fill_ratio
                            : birdnetFifoSnap.fifo_cap
                              ? Number(birdnetFifoSnap.queue_len || 0) / Number(birdnetFifoSnap.fifo_cap)
                              : 0) * 100,
                        ),
                      ),
                      cur: birdnetFifoSnap.queue_len ?? 0,
                      cap: birdnetFifoSnap.fifo_cap ?? 0,
                    })}
                  </Typography>
                </Paper>
                <Box>
                  <Typography variant="subtitle1" gutterBottom sx={{ fontWeight: 600 }}>
                    {t('system.automationBirdnetFifoTableSectionTitle', {
                      hours:
                        birdnetFifoSnap.species_hearing?.active_within_hours != null
                          ? Math.round(Number(birdnetFifoSnap.species_hearing.active_within_hours))
                          : 24,
                    })}
                  </Typography>
                  <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
                    {t('system.automationBirdnetFifoTableSectionHint')}
                  </Typography>
                  {(birdnetFifoSnap.species_fifo_table || []).length > 0 ? (
                    <TableContainer
                      component={Paper}
                      variant="outlined"
                      sx={{ maxHeight: 420, bgcolor: 'background.paper' }}
                    >
                      <Table size="small" stickyHeader>
                        <TableHead>
                          <TableRow>
                            <TableCell
                              sx={(theme) => ({
                                fontWeight: 600,
                                backgroundColor: theme.palette.background.paper,
                                zIndex: 3,
                                borderBottom: `1px solid ${theme.palette.divider}`,
                              })}
                            >
                              {t('system.automationBirdnetFifoTableColMqtt')}
                            </TableCell>
                            <TableCell
                              sx={(theme) => ({
                                fontWeight: 600,
                                backgroundColor: theme.palette.background.paper,
                                zIndex: 3,
                                borderBottom: `1px solid ${theme.palette.divider}`,
                              })}
                            >
                              {t('system.automationBirdnetFifoTableColVideo')}
                            </TableCell>
                            <TableCell
                              align="right"
                              sx={(theme) => ({
                                fontWeight: 600,
                                backgroundColor: theme.palette.background.paper,
                                zIndex: 3,
                                borderBottom: `1px solid ${theme.palette.divider}`,
                              })}
                            >
                              {t('system.automationBirdnetFifoTableColCount')}
                            </TableCell>
                            <TableCell
                              sx={(theme) => ({
                                fontWeight: 600,
                                backgroundColor: theme.palette.background.paper,
                                zIndex: 3,
                                borderBottom: `1px solid ${theme.palette.divider}`,
                              })}
                            >
                              {t('system.automationBirdnetFifoTableColSci')}
                            </TableCell>
                            <TableCell
                              sx={(theme) => ({
                                fontWeight: 600,
                                backgroundColor: theme.palette.background.paper,
                                zIndex: 3,
                                borderBottom: `1px solid ${theme.palette.divider}`,
                              })}
                            >
                              {t('system.automationBirdnetFifoTableColLast')}
                            </TableCell>
                          </TableRow>
                        </TableHead>
                        <TableBody>
                          {(birdnetFifoSnap.species_fifo_table || []).map((row) => {
                            const on = row.active === 1;
                            return (
                              <TableRow
                                key={row.display_label}
                                hover
                                sx={{
                                  bgcolor: 'background.paper',
                                  '&:nth-of-type(even)': { bgcolor: 'action.hover' },
                                  ...(on ? { boxShadow: (theme) => `inset 3px 0 0 ${theme.palette.success.main}` } : {}),
                                }}
                              >
                                <TableCell sx={{ maxWidth: 200 }}>{row.display_label}</TableCell>
                                <TableCell sx={{ maxWidth: 200 }}>{row.canonical_for_video}</TableCell>
                                <TableCell align="right">{row.event_count}</TableCell>
                                <TableCell
                                  sx={{
                                    maxWidth: 160,
                                    fontFamily: 'ui-monospace, monospace',
                                    fontSize: '0.75rem',
                                  }}
                                >
                                  {row.scientific_name || '—'}
                                </TableCell>
                                <TableCell sx={{ whiteSpace: 'nowrap', fontSize: '0.8125rem' }}>
                                  {formatAgoCompact(row.seconds_since_heard ?? 0, t)}
                                </TableCell>
                              </TableRow>
                            );
                          })}
                        </TableBody>
                      </Table>
                    </TableContainer>
                  ) : (
                    <Typography variant="body2" color="text.secondary">
                      —
                    </Typography>
                  )}
                </Box>
                <Accordion disableGutters elevation={0} variant="outlined">
                  <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                    <Typography variant="body2">{t('system.automationBirdnetFifoTechnicalAccordion')}</Typography>
                  </AccordionSummary>
                  <AccordionDetails>
                    <Button size="small" variant="outlined" onClick={copyBirdnetFifoJson} disabled={!birdnetFifoRaw} sx={{ mb: 1 }}>
                      {t('system.automationBirdnetFifoCopyJson')}
                    </Button>
                    <Typography variant="caption" color="text.secondary" display="block" sx={{ mb: 0.5 }}>
                      {t('system.automationBirdnetFifoHearingExplain', {
                        hours:
                          birdnetFifoSnap.species_hearing?.active_within_hours != null
                            ? Math.round(Number(birdnetFifoSnap.species_hearing.active_within_hours))
                            : 24,
                      })}
                    </Typography>
                  </AccordionDetails>
                </Accordion>
              </Stack>
            )}
          </DialogContent>
          <DialogActions>
            <Button onClick={() => setBirdnetFifoOpen(false)}>{t('system.automationBirdnetFifoDialogClose')}</Button>
          </DialogActions>
        </Dialog>

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
