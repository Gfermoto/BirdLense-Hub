import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import axios from 'axios';
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Card from '@mui/material/Card';
import CardContent from '@mui/material/CardContent';
import Chip from '@mui/material/Chip';
import Collapse from '@mui/material/Collapse';
import Divider from '@mui/material/Divider';
import LinearProgress from '@mui/material/LinearProgress';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';
import BuildIcon from '@mui/icons-material/Build';
import CloudSyncIcon from '@mui/icons-material/CloudSync';
import PlaylistAddCheckIcon from '@mui/icons-material/PlaylistAddCheck';
import { BASE_API_URL } from '../../api/client';
import { queryKeys } from '../../api/queryKeys';
import { ConfirmDialog } from '../../components/ConfirmDialog';
import { RetentionPolicy } from './Retention/RetentionPolicy';

interface ScanResult {
  imported?: number;
  message?: string;
}

interface MaintenancePreview {
  orphaned?: number;
  synced_would_update?: number;
  updated?: number;
  dry_run?: boolean;
  message?: string;
}

export function DatabaseMaintenanceCard() {
  const { t } = useTranslation();
  const qc = useQueryClient();

  const [scanResult, setScanResult] = useState<ScanResult | null>(null);
  const [cleanPreview, setCleanPreview] = useState<MaintenancePreview | null>(
    null,
  );
  const [realignPreview, setRealignPreview] =
    useState<MaintenancePreview | null>(null);
  const [confirmOpen, setConfirmOpen] = useState<null | 'clean' | 'realign'>(
    null,
  );
  const [error, setError] = useState<string | null>(null);
  const [applyResult, setApplyResult] = useState<string | null>(null);

  const scanMutation = useMutation<ScanResult, Error, void>({
    mutationFn: async () => {
      const { data } = await axios.post<ScanResult>(
        `${BASE_API_URL}/system/recordings/scan`,
      );
      return data;
    },
    onSuccess: (data) => {
      setScanResult(data);
      qc.invalidateQueries({ queryKey: queryKeys.storage.stats });
      qc.invalidateQueries({ queryKey: queryKeys.video.listAll });
      qc.invalidateQueries({ queryKey: queryKeys.overview.all });
      qc.invalidateQueries({ queryKey: queryKeys.timeline.speciesVisitsAll });
      qc.invalidateQueries({ queryKey: queryKeys.calendar.timelineTab });
      qc.invalidateQueries({ queryKey: queryKeys.calendar.migration });
      qc.invalidateQueries({ queryKey: queryKeys.birdDirectory.all });
      qc.invalidateQueries({ queryKey: queryKeys.species.directory });
      qc.invalidateQueries({ queryKey: queryKeys.speciesSummary.all });
    },
    onError: (err) => setError(err.message),
  });

  const cleanPreviewMutation = useMutation<MaintenancePreview, Error, void>({
    mutationFn: async () => {
      const { data } = await axios.post<MaintenancePreview>(
        `${BASE_API_URL}/system/clean-orphaned-visits`,
        { dry_run: true },
      );
      return data;
    },
    onSuccess: (data) => {
      setCleanPreview(data);
      setError(null);
    },
    onError: (err) => setError(err.message),
  });

  const cleanApplyMutation = useMutation<MaintenancePreview, Error, void>({
    mutationFn: async () => {
      const { data } = await axios.post<MaintenancePreview>(
        `${BASE_API_URL}/system/clean-orphaned-visits`,
        { dry_run: false },
      );
      return data;
    },
    onSuccess: (data) => {
      setCleanPreview(null);
      setApplyResult(data.message ?? t('system.dbMaintenanceDone'));
      qc.invalidateQueries({ queryKey: queryKeys.video.listAll });
      qc.invalidateQueries({ queryKey: queryKeys.timeline.speciesVisitsAll });
      qc.invalidateQueries({ queryKey: queryKeys.overview.all });
      qc.invalidateQueries({ queryKey: queryKeys.calendar.timelineTab });
      qc.invalidateQueries({ queryKey: queryKeys.calendar.migration });
      qc.invalidateQueries({ queryKey: queryKeys.birdDirectory.all });
      qc.invalidateQueries({ queryKey: queryKeys.species.directory });
      qc.invalidateQueries({ queryKey: queryKeys.speciesSummary.all });
      setTimeout(() => setApplyResult(null), 8000);
    },
    onError: (err) => setError(err.message),
  });

  const realignPreviewMutation = useMutation<MaintenancePreview, Error, void>({
    mutationFn: async () => {
      const { data } = await axios.post<MaintenancePreview>(
        `${BASE_API_URL}/system/realign-visit-times`,
        { dry_run: true },
      );
      return data;
    },
    onSuccess: (data) => {
      setRealignPreview(data);
      setError(null);
    },
    onError: (err) => setError(err.message),
  });

  const realignApplyMutation = useMutation<MaintenancePreview, Error, void>({
    mutationFn: async () => {
      const { data } = await axios.post<MaintenancePreview>(
        `${BASE_API_URL}/system/realign-visit-times`,
        { dry_run: false },
      );
      return data;
    },
    onSuccess: (data) => {
      setRealignPreview(null);
      setApplyResult(data.message ?? t('system.dbMaintenanceDone'));
      qc.invalidateQueries({ queryKey: queryKeys.video.listAll });
      qc.invalidateQueries({ queryKey: queryKeys.timeline.speciesVisitsAll });
      qc.invalidateQueries({ queryKey: queryKeys.overview.all });
      qc.invalidateQueries({ queryKey: queryKeys.calendar.timelineTab });
      qc.invalidateQueries({ queryKey: queryKeys.calendar.migration });
      qc.invalidateQueries({ queryKey: queryKeys.birdDirectory.all });
      qc.invalidateQueries({ queryKey: queryKeys.species.directory });
      qc.invalidateQueries({ queryKey: queryKeys.speciesSummary.all });
      setTimeout(() => setApplyResult(null), 8000);
    },
    onError: (err) => setError(err.message),
  });

  const handleConfirmApply = () => {
    setConfirmOpen(null);
    if (confirmOpen === 'clean') cleanApplyMutation.mutate();
    if (confirmOpen === 'realign') realignApplyMutation.mutate();
  };

  const isAnyLoading =
    scanMutation.isPending ||
    cleanPreviewMutation.isPending ||
    cleanApplyMutation.isPending ||
    realignPreviewMutation.isPending ||
    realignApplyMutation.isPending;

  const confirmTitle =
    confirmOpen === 'clean'
      ? t('system.dbCleanOrphanedTitle')
      : t('system.dbRealignTitle');
  const confirmDesc =
    confirmOpen === 'clean'
      ? t('system.dbCleanOrphanedConfirmDesc', {
          orphaned: cleanPreview?.orphaned ?? 0,
          synced: cleanPreview?.synced_would_update ?? 0,
        })
      : t('system.dbRealignConfirmDesc', {
          updated: realignPreview?.updated ?? 0,
        });

  return (
    <Card>
      <CardContent>
        <Typography variant="h6" gutterBottom>
          {t('system.dbMaintenanceTitle')}
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          {t('system.dbMaintenanceSubtitle')}
        </Typography>

        {isAnyLoading && <LinearProgress sx={{ mb: 2 }} />}
        {error && (
          <Alert severity="error" variant="outlined" sx={{ mb: 2 }} onClose={() => setError(null)}>
            {error}
          </Alert>
        )}
        {applyResult && (
          <Alert severity="success" variant="outlined" sx={{ mb: 2 }}>
            {applyResult}
          </Alert>
        )}

        <Stack spacing={2}>
          {/* 1. Scan recordings */}
          <Box>
            <Stack
              direction="row"
              alignItems="center"
              justifyContent="space-between"
              sx={{ mb: 0.5 }}
            >
              <Box>
                <Typography variant="subtitle2">
                  {t('system.dbScanRecordingsTitle')}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  {t('system.dbScanRecordingsDesc')}
                </Typography>
              </Box>
              <Button
                size="small"
                variant="outlined"
                startIcon={<CloudSyncIcon />}
                disabled={isAnyLoading}
                onClick={() => {
                  setError(null);
                  setScanResult(null);
                  scanMutation.mutate();
                }}
              >
                {t('system.dbScanAction')}
              </Button>
            </Stack>
            <Collapse in={!!scanResult}>
              <Alert severity="success" variant="outlined" icon={false} sx={{ py: 0.5, mt: 1 }}>
                {scanResult?.message}
                {typeof scanResult?.imported === 'number' && (
                  <Chip
                    size="small"
                    label={t('system.dbScanImported', {
                      n: scanResult.imported,
                    })}
                    sx={{ ml: 1 }}
                  />
                )}
              </Alert>
            </Collapse>
          </Box>

          <Divider />

          {/* Retention (TTL / modes) — рядом с обслуживанием записей */}
          <RetentionPolicy />

          <Divider />

          {/* 2. Clean orphaned visits */}
          <Box>
            <Stack
              direction="row"
              alignItems="center"
              justifyContent="space-between"
              sx={{ mb: 0.5 }}
            >
              <Box>
                <Typography variant="subtitle2">
                  {t('system.dbCleanOrphanedTitle')}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  {t('system.dbCleanOrphanedDesc')}
                </Typography>
              </Box>
              <Stack direction="row" spacing={1}>
                <Button
                  size="small"
                  variant="outlined"
                  startIcon={<PlaylistAddCheckIcon />}
                  disabled={isAnyLoading}
                  onClick={() => {
                    setError(null);
                    setCleanPreview(null);
                    cleanPreviewMutation.mutate();
                  }}
                >
                  {t('system.dbPreviewAction')}
                </Button>
                {cleanPreview && (
                  <Button
                    size="small"
                    variant="contained"
                    color="warning"
                    startIcon={<BuildIcon />}
                    disabled={isAnyLoading}
                    onClick={() => setConfirmOpen('clean')}
                  >
                    {t('system.dbApplyAction')}
                  </Button>
                )}
              </Stack>
            </Stack>
            <Collapse in={!!cleanPreview}>
              {cleanPreview && (
                <Alert
                  severity="info"
                  variant="outlined"
                  icon={false}
                  sx={{ py: 0.5, mt: 1 }}
                >
                  {cleanPreview.orphaned === 0 &&
                  (cleanPreview.synced_would_update ?? 0) === 0
                    ? t('system.dbCleanNothingToClean')
                    : t('system.dbCleanPreviewResult', {
                        orphaned: cleanPreview.orphaned,
                        synced: cleanPreview.synced_would_update ?? 0,
                      })}
                </Alert>
              )}
            </Collapse>
          </Box>

          <Divider />

          {/* 3. Realign visit times */}
          <Box>
            <Stack
              direction="row"
              alignItems="center"
              justifyContent="space-between"
              sx={{ mb: 0.5 }}
            >
              <Box>
                <Typography variant="subtitle2">
                  {t('system.dbRealignTitle')}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  {t('system.dbRealignDesc')}
                </Typography>
              </Box>
              <Stack direction="row" spacing={1}>
                <Button
                  size="small"
                  variant="outlined"
                  startIcon={<PlaylistAddCheckIcon />}
                  disabled={isAnyLoading}
                  onClick={() => {
                    setError(null);
                    setRealignPreview(null);
                    realignPreviewMutation.mutate();
                  }}
                >
                  {t('system.dbPreviewAction')}
                </Button>
                {realignPreview && (
                  <Button
                    size="small"
                    variant="contained"
                    color="warning"
                    startIcon={<BuildIcon />}
                    disabled={isAnyLoading}
                    onClick={() => setConfirmOpen('realign')}
                  >
                    {t('system.dbApplyAction')}
                  </Button>
                )}
              </Stack>
            </Stack>
            <Collapse in={!!realignPreview}>
              {realignPreview && (
                <Alert
                  severity="info"
                  variant="outlined"
                  icon={false}
                  sx={{ py: 0.5, mt: 1 }}
                >
                  {realignPreview.updated === 0
                    ? t('system.dbRealignNothingToFix')
                    : t('system.dbRealignPreviewResult', {
                        updated: realignPreview.updated,
                      })}
                </Alert>
              )}
            </Collapse>
          </Box>
        </Stack>
      </CardContent>

      <ConfirmDialog
        open={confirmOpen !== null}
        title={confirmTitle}
        description={confirmDesc}
        confirmLabel={t('system.dbApplyAction')}
        cancelLabel={t('common.cancel')}
        confirmColor="warning"
        onConfirm={handleConfirmApply}
        onCancel={() => setConfirmOpen(null)}
      />
    </Card>
  );
}
