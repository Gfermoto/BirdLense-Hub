import { type ReactNode, useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import Alert from '@mui/material/Alert';
import Accordion from '@mui/material/Accordion';
import AccordionDetails from '@mui/material/AccordionDetails';
import AccordionSummary from '@mui/material/AccordionSummary';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
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
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import { useTranslation } from 'react-i18next';
import {
  type BirdnetFifoDialogSnapshot,
  type BirdnetFifoPayload,
  type SystemJobStatus,
  backfillSpeciesRegistry,
  downloadLatestFusionEvalReport,
  downloadLatestFusionExport,
  enrichSpeciesRegistryMetadata,
  fetchBirdnetFifoSnapshot,
  fetchFusionEvalStatus,
  fetchFusionExportStatus,
  materializeSpeciesAllowlist,
  mergeDuplicateSpecies,
  previewBrokenVideosPurge,
  previewNoSpeciesVideosPurge,
  purgeBrokenVideosBatch,
  purgeNoSpeciesVideosBatch,
  reconcileSpeciesCatalog,
  seedSpeciesRegistry,
  startFusionEval,
  startFusionExport,
} from '../../api/api';
import { SystemCardShell } from './SystemCardShell';

function statusLabel(status?: SystemJobStatus | null): string {
  if (!status) return 'idle';
  if (status.error) return 'error';
  if (status.status === 'running') return 'running';
  if (status.status === 'done') return 'done';
  return status.status || 'idle';
}

function formatAgoCompact(seconds: number, t: (key: string, options?: Record<string, unknown>) => string): string {
  const s = Math.max(0, Math.floor(seconds));
  if (s < 60) return t('system.automationBirdnetFifoAgoSeconds', { n: s });
  if (s < 3600) return t('system.automationBirdnetFifoAgoMinutes', { n: Math.floor(s / 60) });
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  if (m <= 0) return t('system.automationBirdnetFifoAgoHoursOnly', { n: h });
  return t('system.automationBirdnetFifoAgoHoursMinutes', { h, m });
}

type ActionDef = {
  label: string;
  hint: string;
  onRun: () => Promise<Record<string, unknown> | null>;
  color?: 'warning' | 'error';
};

function ActionButton({
  action,
  busy,
  runAction,
}: {
  action: ActionDef;
  busy: boolean;
  runAction: (action: ActionDef) => Promise<void>;
}) {
  return (
    <Tooltip title={action.hint} describeChild>
      <span>
        <Button
          variant="outlined"
          color={action.color}
          disabled={busy}
          onClick={() => {
            void runAction(action);
          }}
        >
          {action.label}
        </Button>
      </span>
    </Tooltip>
  );
}

function useActionRunner() {
  const [runningLabel, setRunningLabel] = useState<string | null>(null);
  const [lastInfo, setLastInfo] = useState<string | null>(null);

  const runAction = async (action: ActionDef) => {
    try {
      setRunningLabel(action.label);
      setLastInfo(`${action.label}: ...`);
      const data = await action.onRun();
      if (data === null) {
        setLastInfo(null);
        return;
      }
      setLastInfo(`${action.label}: ${JSON.stringify(data)}`);
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      setLastInfo(`${action.label}: ${message}`);
    } finally {
      setRunningLabel((current) => (current === action.label ? null : current));
    }
  };

  return {
    runningLabel,
    lastInfo,
    clearInfo: () => setLastInfo(null),
    runAction,
  };
}

function getJobStatusLabel(
  t: (key: string, options?: Record<string, unknown>) => string,
  status?: SystemJobStatus | null,
): string {
  const raw = statusLabel(status);
  return t(`system.jobStatus.${raw}`, { defaultValue: raw });
}

function fmtNum(v: unknown, digits = 4): string {
  if (typeof v === 'number' && Number.isFinite(v)) return v.toFixed(digits).replace(/\.?0+$/, '') || '0';
  if (typeof v === 'string' && v.trim() !== '') {
    const n = Number(v);
    if (Number.isFinite(n)) return n.toFixed(digits).replace(/\.?0+$/, '') || '0';
  }
  return '—';
}

function FusionExportResultBlock({ result }: { result: Record<string, unknown> }) {
  const { t } = useTranslation();
  const rows = result.rows_written;
  const path = result.output_path != null ? String(result.output_path) : '';
  const src = result.source != null ? String(result.source) : '';
  return (
    <Box>
      <Typography variant="subtitle2" sx={{ mb: 0.5 }}>
        {t('system.automationFusionExportSummaryTitle')}
      </Typography>
      {typeof rows === 'number' ? (
        <Typography variant="body2">{t('system.automationFusionExportRows', { count: rows })}</Typography>
      ) : null}
      {src ? (
        <Typography variant="caption" color="text.secondary" display="block" sx={{ mt: 0.5 }}>
          {src}
        </Typography>
      ) : null}
      {path ? (
        <Typography variant="body2" sx={{ mt: 0.5, fontFamily: 'monospace', fontSize: '0.8rem', wordBreak: 'break-all' }}>
          {path}
        </Typography>
      ) : null}
    </Box>
  );
}

type ThresholdRow = { coverage?: unknown; precision?: unknown; recall?: unknown; risk?: unknown; count?: unknown };

function FusionEvalReportBlock({ result }: { result: Record<string, unknown> }) {
  const { t } = useTranslation();
  const thresholds = result.thresholds;
  const thEntries =
    thresholds && typeof thresholds === 'object'
      ? Object.entries(thresholds as Record<string, ThresholdRow>).sort(([a], [b]) => Number(a) - Number(b))
      : [];
  const bins = Array.isArray(result.bins) ? (result.bins as Record<string, unknown>[]) : [];
  const slices = result.slices && typeof result.slices === 'object' ? (result.slices as Record<string, unknown>) : null;
  const reportRows = result.eval_report_csv_rows;
  const nFlat = typeof reportRows === 'number' ? reportRows : null;

  return (
    <Stack spacing={1.5} sx={{ width: '100%' }}>
      <Typography variant="subtitle2">{t('system.automationFusionEvalSummaryTitle')}</Typography>
      <Stack direction="row" flexWrap="wrap" gap={2}>
        <Typography variant="body2">
          {t('system.automationFusionEvalColN')}: <strong>{fmtNum(result.n, 0)}</strong>
        </Typography>
        <Typography variant="body2">
          {t('system.automationFusionEvalColPositiveRate')}: <strong>{fmtNum(result.positive_rate)}</strong>
        </Typography>
        <Typography variant="body2">
          {t('system.automationFusionEvalColBrier')}: <strong>{fmtNum(result.brier)}</strong>
        </Typography>
        <Typography variant="body2">
          {t('system.automationFusionEvalColEce')}: <strong>{fmtNum(result.ece)}</strong>
        </Typography>
        <Typography variant="body2">
          {t('system.automationFusionEvalColAcc05')}: <strong>{fmtNum(result.accuracy_at_0_5)}</strong>
        </Typography>
      </Stack>
      {result.source_csv ? (
        <Typography variant="caption" color="text.secondary" display="block" sx={{ fontFamily: 'monospace' }}>
          {t('system.automationFusionEvalSourceCsv')}: {String(result.source_csv)}
        </Typography>
      ) : null}
      {result.eval_report_csv_path ? (
        <Typography variant="caption" color="text.secondary" display="block" sx={{ fontFamily: 'monospace' }}>
          {t('system.automationFusionEvalReportCsv')}: {String(result.eval_report_csv_path)}
          {nFlat != null ? ` · ${t('system.automationFusionEvalReportRows', { count: nFlat })}` : ''}
        </Typography>
      ) : null}

      {thEntries.length > 0 ? (
        <Box>
          <Typography variant="subtitle2" sx={{ mb: 0.5 }}>
            {t('system.automationFusionEvalThresholds')}
          </Typography>
          <TableContainer component={Paper} variant="outlined" sx={{ maxWidth: '100%' }}>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>{t('system.automationFusionEvalColThreshold')}</TableCell>
                  <TableCell align="right">{t('system.automationFusionEvalColCoverage')}</TableCell>
                  <TableCell align="right">{t('system.automationFusionEvalColPrecision')}</TableCell>
                  <TableCell align="right">{t('system.automationFusionEvalColRecall')}</TableCell>
                  <TableCell align="right">{t('system.automationFusionEvalColRisk')}</TableCell>
                  <TableCell align="right">{t('system.automationFusionEvalColCount')}</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {thEntries.map(([key, row]) => (
                  <TableRow key={key}>
                    <TableCell>{key}</TableCell>
                    <TableCell align="right">{fmtNum(row?.coverage)}</TableCell>
                    <TableCell align="right">{fmtNum(row?.precision)}</TableCell>
                    <TableCell align="right">{fmtNum(row?.recall)}</TableCell>
                    <TableCell align="right">{fmtNum(row?.risk)}</TableCell>
                    <TableCell align="right">{fmtNum(row?.count, 0)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        </Box>
      ) : null}

      {bins.length > 0 ? (
        <Accordion variant="outlined" disableGutters>
          <AccordionSummary expandIcon={<ExpandMoreIcon />}>
            <Typography variant="subtitle2">{t('system.automationFusionEvalBins')}</Typography>
          </AccordionSummary>
          <AccordionDetails>
            <TableContainer>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>{t('system.automationFusionEvalColBin')}</TableCell>
                    <TableCell align="right">{t('system.automationFusionEvalColLo')}</TableCell>
                    <TableCell align="right">{t('system.automationFusionEvalColHi')}</TableCell>
                    <TableCell align="right">{t('system.automationFusionEvalColCount')}</TableCell>
                    <TableCell align="right">{t('system.automationFusionEvalColConf')}</TableCell>
                    <TableCell align="right">{t('system.automationFusionEvalColAcc')}</TableCell>
                    <TableCell align="right">{t('system.automationFusionEvalColGap')}</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {bins.map((b, i) => (
                    <TableRow key={i}>
                      <TableCell>{String(b.bin ?? i)}</TableCell>
                      <TableCell align="right">{fmtNum(b.lo)}</TableCell>
                      <TableCell align="right">{fmtNum(b.hi)}</TableCell>
                      <TableCell align="right">{fmtNum(b.count, 0)}</TableCell>
                      <TableCell align="right">{fmtNum(b.confidence)}</TableCell>
                      <TableCell align="right">{fmtNum(b.accuracy)}</TableCell>
                      <TableCell align="right">{fmtNum(b.gap)}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          </AccordionDetails>
        </Accordion>
      ) : null}

      {slices && Object.keys(slices).length > 0 ? (
        <Accordion variant="outlined" disableGutters>
          <AccordionSummary expandIcon={<ExpandMoreIcon />}>
            <Typography variant="subtitle2">{t('system.automationFusionEvalSlices')}</Typography>
          </AccordionSummary>
          <AccordionDetails>
            <Stack spacing={2}>
              {Object.entries(slices).map(([field, byVal]) =>
                typeof byVal === 'object' && byVal !== null ? (
                  <Box key={field}>
                    <Typography variant="caption" color="text.secondary" display="block" sx={{ mb: 0.5 }}>
                      {field}
                    </Typography>
                    {Object.entries(byVal as Record<string, Record<string, unknown>>).map(([sliceVal, sub]) => (
                      <Box key={`${field}:${sliceVal}`} sx={{ mb: 1, pl: 1, borderLeft: '2px solid', borderColor: 'divider' }}>
                        <Typography variant="body2" sx={{ fontWeight: 600 }}>
                          {sliceVal}
                        </Typography>
                        <Typography variant="caption" display="block">
                          n={fmtNum(sub.n, 0)} · ECE={fmtNum(sub.ece)} · Brier={fmtNum(sub.brier)} · acc@0.5=
                          {fmtNum(sub.accuracy_at_0_5)}
                        </Typography>
                      </Box>
                    ))}
                  </Box>
                ) : null,
              )}
            </Stack>
          </AccordionDetails>
        </Accordion>
      ) : null}
    </Stack>
  );
}

export function AutomationFusionCard() {
  const { t } = useTranslation();
  const [fusionExportPolling, setFusionExportPolling] = useState(false);
  const [fusionEvalPolling, setFusionEvalPolling] = useState(false);
  const [lastInfo, setLastInfo] = useState<string | null>(null);

  const fusionExportQuery = useQuery({
    queryKey: ['fusion-export-status'],
    queryFn: fetchFusionExportStatus,
    refetchInterval: (q) =>
      q.state.data?.status === 'running' || fusionExportPolling ? 2_500 : false,
    staleTime: 0,
  });
  const fusionEvalQuery = useQuery({
    queryKey: ['fusion-eval-status'],
    queryFn: fetchFusionEvalStatus,
    refetchInterval: (q) =>
      q.state.data?.status === 'running' || fusionEvalPolling ? 2_500 : false,
    staleTime: 0,
  });

  const fusionExportMutation = useMutation({
    mutationFn: startFusionExport,
    onSuccess: (data) => {
      setFusionExportPolling(true);
      setLastInfo(data.message || t('system.automationFusionExportStarted'));
    },
    onError: (error: unknown) => {
      setLastInfo(
        error instanceof Error ? error.message : t('system.automationFusionExportFailed'),
      );
    },
  });
  const fusionEvalMutation = useMutation({
    mutationFn: startFusionEval,
    onSuccess: (data) => {
      setFusionEvalPolling(true);
      setLastInfo(data.message || t('system.automationFusionEvalStarted'));
    },
    onError: (error: unknown) => {
      setLastInfo(
        error instanceof Error ? error.message : t('system.automationFusionEvalFailed'),
      );
    },
  });

  useEffect(() => {
    if (fusionExportQuery.isError) {
      setFusionExportPolling(false);
      return;
    }
    if (fusionExportQuery.data?.status && fusionExportQuery.data.status !== 'running') {
      setFusionExportPolling(false);
    }
  }, [fusionExportQuery.data?.status, fusionExportQuery.isError]);

  useEffect(() => {
    if (fusionEvalQuery.isError) {
      setFusionEvalPolling(false);
      return;
    }
    if (fusionEvalQuery.data?.status && fusionEvalQuery.data.status !== 'running') {
      setFusionEvalPolling(false);
    }
  }, [fusionEvalQuery.data?.status, fusionEvalQuery.isError]);

  const running =
    fusionExportMutation.isPending ||
    fusionEvalMutation.isPending ||
    fusionExportQuery.data?.status === 'running' ||
    fusionEvalQuery.data?.status === 'running';
  const hasError = Boolean(
    fusionExportMutation.isError ||
      fusionEvalMutation.isError ||
      fusionExportQuery.isError ||
      fusionEvalQuery.isError ||
      fusionExportQuery.data?.error ||
      fusionEvalQuery.data?.error ||
      fusionExportQuery.data?.status === 'error' ||
      fusionEvalQuery.data?.status === 'error',
  );
  const statusLabelText = hasError
    ? t('system.jobStatus.error')
    : running
      ? t('system.jobStatus.running')
      : t('system.readinessReady');

  return (
    <SystemCardShell
      title={t('system.automationFusionPanelTitle')}
      description={t('system.automationFusionPanelHint')}
      statusLabel={statusLabelText}
      statusTone={hasError ? 'error' : running ? 'warning' : 'success'}
      footer={
        <Stack direction="row" flexWrap="wrap" gap={1}>
          <AlertChip
            label={`${t('system.automationFusionExportStatus')}: ${getJobStatusLabel(t, fusionExportQuery.data)}`}
          />
          <AlertChip
            label={`${t('system.automationFusionEvalStatus')}: ${getJobStatusLabel(t, fusionEvalQuery.data)}`}
          />
        </Stack>
      }
    >
      <Stack spacing={2}>
        {running ? <LinearProgress /> : null}
        {lastInfo ? (
          <Alert severity="info" onClose={() => setLastInfo(null)}>
            {lastInfo}
          </Alert>
        ) : null}
        {fusionExportQuery.isError ? (
          <Alert severity="error">{t('system.automationFusionExportFailed')}</Alert>
        ) : null}
        {fusionEvalQuery.isError ? (
          <Alert severity="error">{t('system.automationFusionEvalFailed')}</Alert>
        ) : null}
        <Stack direction="row" flexWrap="wrap" gap={1}>
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
              <Button variant="outlined" onClick={downloadLatestFusionExport}>
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
          <Tooltip title={t('system.automationFusionEvalDownloadHint')} describeChild>
            <span>
              <Button variant="outlined" onClick={() => downloadLatestFusionEvalReport()}>
                {t('system.automationFusionEvalDownload')}
              </Button>
            </span>
          </Tooltip>
        </Stack>
        {fusionExportQuery.data?.error ? (
          <Alert severity="error">{fusionExportQuery.data.error}</Alert>
        ) : null}
        {fusionExportQuery.data?.result && !fusionExportQuery.data?.error ? (
          <Alert severity="success" sx={{ '& .MuiAlert-message': { width: '100%' } }}>
            <FusionExportResultBlock result={fusionExportQuery.data.result as Record<string, unknown>} />
          </Alert>
        ) : null}
        {fusionEvalQuery.data?.error ? <Alert severity="error">{fusionEvalQuery.data.error}</Alert> : null}
        {fusionEvalQuery.data?.result && !fusionEvalQuery.data?.error ? (
          <Alert severity="success" sx={{ '& .MuiAlert-message': { width: '100%' } }}>
            <FusionEvalReportBlock result={fusionEvalQuery.data.result as Record<string, unknown>} />
          </Alert>
        ) : null}
      </Stack>
    </SystemCardShell>
  );
}

export function AutomationDiagnosticsCard() {
  const { t } = useTranslation();
  const [birdnetFifoOpen, setBirdnetFifoOpen] = useState(false);
  const [birdnetFifoRaw, setBirdnetFifoRaw] = useState<BirdnetFifoPayload | null>(null);
  const [birdnetFifoError, setBirdnetFifoError] = useState<string | null>(null);
  const [birdnetFifoLoading, setBirdnetFifoLoading] = useState(false);

  const openBirdnetFifoDialog = async () => {
    setBirdnetFifoOpen(true);
    setBirdnetFifoLoading(true);
    setBirdnetFifoError(null);
    setBirdnetFifoRaw(null);
    try {
      setBirdnetFifoRaw(await fetchBirdnetFifoSnapshot());
    } catch (error) {
      setBirdnetFifoError(error instanceof Error ? error.message : String(error));
    } finally {
      setBirdnetFifoLoading(false);
    }
  };

  return (
    <>
      <SystemCardShell
        title={t('system.automationDiagnosticsPanelTitle')}
        description={t('system.automationDiagnosticsPanelHint')}
      >
        <Stack spacing={2}>
          <Typography variant="body2" color="text.secondary">
            {t('system.automationBirdnetFifoSnapshotHint')}
          </Typography>
          <Stack direction="row" flexWrap="wrap" gap={1}>
            <Button
              variant="outlined"
              disabled={birdnetFifoLoading}
              onClick={() => {
                void openBirdnetFifoDialog();
              }}
            >
              {t('system.automationBirdnetFifoSnapshot')}
            </Button>
          </Stack>
        </Stack>
      </SystemCardShell>
      <BirdnetFifoDialog
        open={birdnetFifoOpen}
        loading={birdnetFifoLoading}
        error={birdnetFifoError}
        data={birdnetFifoRaw}
        onClose={() => setBirdnetFifoOpen(false)}
      />
    </>
  );
}

export function AutomationMaintenanceCard() {
  const { t } = useTranslation();
  const { runningLabel, lastInfo, clearInfo, runAction } = useActionRunner();
  const actions = useMemo<ActionDef[]>(
    () => [
      {
        label: t('system.automationRegistrySeed'),
        hint: t('system.automationRegistrySeedHint'),
        onRun: seedSpeciesRegistry,
        color: 'warning',
      },
      {
        label: t('system.automationRegistryBackfill'),
        hint: t('system.automationRegistryBackfillHint'),
        onRun: backfillSpeciesRegistry,
        color: 'warning',
      },
      {
        label: t('system.automationRegistryEnrich'),
        hint: t('system.automationRegistryEnrichHint'),
        onRun: enrichSpeciesRegistryMetadata,
        color: 'warning',
      },
      {
        label: t('system.automationRegistryMaterialize'),
        hint: t('system.automationRegistryMaterializeHint'),
        onRun: materializeSpeciesAllowlist,
        color: 'warning',
      },
      {
        label: t('system.automationMergeDuplicateSpecies'),
        hint: t('system.automationMergeDuplicateSpeciesHint'),
        onRun: mergeDuplicateSpecies,
        color: 'warning',
      },
      {
        label: t('system.automationSpeciesCatalogReconcile'),
        hint: t('system.automationSpeciesCatalogReconcileHint'),
        onRun: reconcileSpeciesCatalog,
        color: 'warning',
      },
    ],
    [t],
  );

  return (
    <SystemCardShell
      title={t('system.automationMaintenancePanelTitle')}
      description={t('system.automationAdminMaintenanceHint')}
      statusLabel={runningLabel ? t('system.catalogRepairRunning') : t('system.heroActionReview')}
      statusTone={runningLabel ? 'warning' : 'default'}
    >
      <Stack spacing={2}>
        {runningLabel ? <LinearProgress /> : null}
        {lastInfo ? (
          <Alert severity="info" onClose={clearInfo}>
            {lastInfo}
          </Alert>
        ) : null}
        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
          {actions.map((action) => (
            <ActionButton
              key={action.label}
              action={action}
              busy={runningLabel !== null}
              runAction={runAction}
            />
          ))}
        </Box>
      </Stack>
    </SystemCardShell>
  );
}

export function AutomationDangerZoneCard() {
  const { t } = useTranslation();
  const { runningLabel, lastInfo, clearInfo, runAction } = useActionRunner();
  const actions = useMemo<ActionDef[]>(
    () => [
      {
        label: t('system.automationBrokenVideosPurgePreview'),
        hint: t('system.automationBrokenVideosPurgePreviewHint'),
        onRun: previewBrokenVideosPurge,
        color: 'warning',
      },
      {
        label: t('system.automationBrokenVideosPurgeBatch'),
        hint: t('system.automationBrokenVideosPurgeBatchHint'),
        onRun: () => {
          const phrase = window.prompt(
            t('system.automationBrokenVideosPurgePrompt'),
            '',
          );
          if (phrase === null || !phrase.trim()) return Promise.resolve(null);
          return purgeBrokenVideosBatch(phrase.trim());
        },
        color: 'error',
      },
      {
        label: t('system.automationNoSpeciesVideosPurgePreview'),
        hint: t('system.automationNoSpeciesVideosPurgePreviewHint'),
        onRun: previewNoSpeciesVideosPurge,
        color: 'warning',
      },
      {
        label: t('system.automationNoSpeciesVideosPurgeBatch'),
        hint: t('system.automationNoSpeciesVideosPurgeBatchHint'),
        onRun: () => {
          const phrase = window.prompt(
            t('system.automationNoSpeciesVideosPurgePrompt'),
            '',
          );
          if (phrase === null || !phrase.trim()) return Promise.resolve(null);
          return purgeNoSpeciesVideosBatch(phrase.trim());
        },
        color: 'error',
      },
    ],
    [t],
  );

  return (
    <SystemCardShell
      id="system-danger-zone"
      title={t('system.automationDangerZone')}
      description={t('system.automationDangerNote')}
      statusLabel={t('system.automationDangerZone')}
      statusTone="error"
    >
      <Stack spacing={2}>
        <Alert severity="warning">{t('system.automationDangerNote')}</Alert>
        {runningLabel ? <LinearProgress /> : null}
        {lastInfo ? (
          <Alert severity="info" onClose={clearInfo}>
            {lastInfo}
          </Alert>
        ) : null}
        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
          {actions.map((action) => (
            <ActionButton
              key={action.label}
              action={action}
              busy={runningLabel !== null}
              runAction={runAction}
            />
          ))}
        </Box>
      </Stack>
    </SystemCardShell>
  );
}

function BirdnetFifoDialog({
  open,
  loading,
  error,
  data,
  onClose,
}: {
  open: boolean;
  loading: boolean;
  error: string | null;
  data: BirdnetFifoPayload | null;
  onClose: () => void;
}) {
  const { t } = useTranslation();
  const snapshot = (data?.snapshot || null) as BirdnetFifoDialogSnapshot | null;

  const fillPercent = Math.min(
    100,
    Math.round(
      ((typeof snapshot?.fifo_fill_ratio === 'number'
        ? snapshot.fifo_fill_ratio
        : snapshot?.fifo_cap
          ? Number(snapshot.queue_len || 0) / Number(snapshot.fifo_cap)
          : 0) as number) * 100,
    ),
  );

  const copyJson = async () => {
    if (!data) return;
    try {
      await navigator.clipboard.writeText(JSON.stringify(data, null, 2));
    } catch {
      // ignore clipboard failures
    }
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="lg" fullWidth>
      <DialogTitle sx={{ pb: 0.5 }}>
        {t('system.automationBirdnetFifoDialogTitle')}
        <Typography
          variant="caption"
          color="text.secondary"
          display="block"
          sx={{ mt: 0.75, fontWeight: 400 }}
        >
          {t('system.automationBirdnetFifoUiReviewHint')}
        </Typography>
      </DialogTitle>
      <DialogContent dividers>
        {loading ? (
          <Stack alignItems="center" py={3}>
            <CircularProgress size={32} />
          </Stack>
        ) : null}
        {!loading && error ? <Alert severity="error">{error}</Alert> : null}
        {!loading && !error && data && !data.available ? (
          <Alert severity="warning">{t('system.automationBirdnetFifoUnavailable')}</Alert>
        ) : null}
        {!loading && !error && snapshot ? (
          <Stack spacing={2.5}>
            <Paper variant="outlined" sx={{ p: 1.5 }}>
              <Typography variant="subtitle2" gutterBottom>
                {t('system.automationBirdnetFifoBufferTitle')}
              </Typography>
              <LinearProgress
                variant="determinate"
                value={fillPercent}
                sx={{ height: 8, borderRadius: 1, mb: 1 }}
              />
              <Typography variant="body2" color="text.secondary">
                {t('system.automationBirdnetFifoBufferHint', {
                  pct: fillPercent,
                  cur: snapshot.queue_len ?? 0,
                  cap: snapshot.fifo_cap ?? 0,
                })}
              </Typography>
            </Paper>
            <Box>
              <Typography variant="subtitle1" gutterBottom sx={{ fontWeight: 600 }}>
                {t('system.automationBirdnetFifoTableSectionTitle', {
                  hours:
                    snapshot.species_hearing?.active_within_hours != null
                      ? Math.round(Number(snapshot.species_hearing.active_within_hours))
                      : 24,
                })}
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
                {t('system.automationBirdnetFifoTableSectionHint')}
              </Typography>
              {(snapshot.species_fifo_table || []).length > 0 ? (
                <TableContainer component={Paper} variant="outlined" sx={{ maxHeight: 420 }}>
                  <Table size="small" stickyHeader>
                    <TableHead>
                      <TableRow>
                        <HeaderCell>{t('system.automationBirdnetFifoTableColMqtt')}</HeaderCell>
                        <HeaderCell>{t('system.automationBirdnetFifoTableColVideo')}</HeaderCell>
                        <HeaderCell align="right">
                          {t('system.automationBirdnetFifoTableColCount')}
                        </HeaderCell>
                        <HeaderCell>{t('system.automationBirdnetFifoTableColSci')}</HeaderCell>
                        <HeaderCell>{t('system.automationBirdnetFifoTableColLast')}</HeaderCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {(snapshot.species_fifo_table || []).map((row) => {
                        const active = row.active === 1;
                        return (
                          <TableRow
                            key={row.display_label}
                            hover
                            sx={{
                              '&:nth-of-type(even)': { bgcolor: 'action.hover' },
                              ...(active
                                ? { boxShadow: (theme) => `inset 3px 0 0 ${theme.palette.success.main}` }
                                : {}),
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
                <Typography variant="body2">
                  {t('system.automationBirdnetFifoTechnicalAccordion')}
                </Typography>
              </AccordionSummary>
              <AccordionDetails>
                <Button
                  size="small"
                  variant="outlined"
                  onClick={() => {
                    void copyJson();
                  }}
                  disabled={!data}
                  sx={{ mb: 1 }}
                >
                  {t('system.automationBirdnetFifoCopyJson')}
                </Button>
                <Typography variant="caption" color="text.secondary" display="block">
                  {t('system.automationBirdnetFifoHearingExplain', {
                    hours:
                      snapshot.species_hearing?.active_within_hours != null
                        ? Math.round(Number(snapshot.species_hearing.active_within_hours))
                        : 24,
                  })}
                </Typography>
              </AccordionDetails>
            </Accordion>
          </Stack>
        ) : null}
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>{t('system.automationBirdnetFifoDialogClose')}</Button>
      </DialogActions>
    </Dialog>
  );
}

function HeaderCell({
  children,
  align,
}: {
  children: ReactNode;
  align?: 'right' | 'left' | 'center' | 'inherit' | 'justify';
}) {
  return (
    <TableCell
      align={align}
      sx={(theme) => ({
        fontWeight: 600,
        backgroundColor: theme.palette.background.paper,
        zIndex: 3,
        borderBottom: `1px solid ${theme.palette.divider}`,
      })}
    >
      {children}
    </TableCell>
  );
}

function AlertChip({ label }: { label: string }) {
  return (
    <Paper
      variant="outlined"
      sx={{ px: 1.25, py: 0.75, borderRadius: 999, display: 'inline-flex' }}
    >
      <Typography variant="caption" color="text.secondary">
        {label}
      </Typography>
    </Paper>
  );
}
