import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import axios from 'axios';
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Collapse from '@mui/material/Collapse';
import LinearProgress from '@mui/material/LinearProgress';
import MenuItem from '@mui/material/MenuItem';
import Stack from '@mui/material/Stack';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';
import BuildIcon from '@mui/icons-material/Build';
import CloudSyncIcon from '@mui/icons-material/CloudSync';
import { BASE_API_URL } from '../../../api/client';
import { queryKeys } from '../../../api/queryKeys';

type RetentionMode = 'cascade' | 'files_only' | 'disabled';

interface RetentionConfig {
  mode: RetentionMode;
  days?: number | null;
  max_gb?: number | null;
  dataset_max_age_days: number;
  migration_max_age_days: number;
  protect_favorites: boolean;
  min_age_hours: number;
  batch_size: number;
  last_run?: string | null;
  last_deleted_count?: number;
  last_freed_bytes?: number;
  last_mode?: string;
}

interface RetentionRunResponse {
  message?: string;
  deletedCount?: number;
  deletedSize?: number;
  dryRun?: boolean;
  mode?: string;
}

/** Политика хранения записей: превью/запуск (режим из конфига можно переопределить на время запроса). */
export function RetentionPolicy() {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const [runMode, setRunMode] = useState<RetentionMode>('cascade');

  const configQuery = useQuery({
    queryKey: queryKeys.system.retentionConfig,
    queryFn: async () => {
      const { data } = await axios.get<RetentionConfig>(
        `${BASE_API_URL}/system/retention`,
      );
      return data;
    },
    refetchOnWindowFocus: false,
  });

  useEffect(() => {
    if (configQuery.data?.mode) {
      setRunMode(configQuery.data.mode);
    }
  }, [configQuery.data?.mode]);

  const runMutation = useMutation({
    mutationFn: async (dry_run: boolean) => {
      const { data } = await axios.post<RetentionRunResponse>(
        `${BASE_API_URL}/system/retention`,
        { dry_run, mode: runMode },
      );
      return data;
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: queryKeys.system.retentionConfig });
    },
  });

  if (configQuery.isLoading) {
    return <LinearProgress />;
  }

  if (configQuery.error || !configQuery.data) {
    return (
      <Alert severity="error">{t('system.retentionConfigError')}</Alert>
    );
  }

  const cfg = configQuery.data;

  return (
    <Box>
      <Typography variant="subtitle2" gutterBottom>
        {t('system.retentionTitle')}
      </Typography>
      <Typography
        variant="caption"
        color="text.secondary"
        display="block"
        sx={{ mb: 1.5 }}
      >
        {t('system.retentionSubtitle')}
      </Typography>

      <Stack spacing={1.5} sx={{ mb: 2 }}>
        <TextField
          select
          size="small"
          label={t('system.retentionModeRunLabel')}
          value={runMode}
          onChange={(e) => setRunMode(e.target.value as RetentionMode)}
          fullWidth
        >
          <MenuItem value="cascade">cascade</MenuItem>
          <MenuItem value="files_only">files_only</MenuItem>
          <MenuItem value="disabled">disabled</MenuItem>
        </TextField>
        <Typography variant="caption" color="text.secondary">
          {t('system.retentionConfigFromServer')}: {cfg.mode}, {t('system.retentionDays')}:{' '}
          {cfg.days ?? '—'}, {t('system.retentionMaxGb')}: {cfg.max_gb ?? '—'},{' '}
          {t('system.retentionDatasetTtl')}: {cfg.dataset_max_age_days},{' '}
          {t('system.retentionMigrationTtl')}: {cfg.migration_max_age_days},{' '}
          {t('system.retentionProtectFavorites')}: {String(cfg.protect_favorites)},{' '}
          {t('system.retentionMinAgeHours')}: {cfg.min_age_hours},{' '}
          {t('system.retentionBatch')}: {cfg.batch_size}
        </Typography>
      </Stack>

      {runMutation.isError && (
        <Alert severity="error" sx={{ mb: 1 }}>
          {runMutation.error.message}
        </Alert>
      )}

      {runMutation.isSuccess && runMutation.data && (
        <Alert
          severity={runMutation.data.dryRun ? 'info' : 'success'}
          sx={{ mb: 1 }}
        >
          {runMutation.data.message}
          {runMutation.data.deletedCount != null && (
            <Typography component="span" variant="body2" sx={{ display: 'block', mt: 0.5 }}>
              {t('system.retentionResultCounts', {
                n: runMutation.data.deletedCount,
                mb: Math.round((runMutation.data.deletedSize ?? 0) / 1024 / 1024),
              })}
            </Typography>
          )}
        </Alert>
      )}

      <Stack direction="row" spacing={1}>
        <Button
          size="small"
          variant="outlined"
          startIcon={<CloudSyncIcon />}
          disabled={runMutation.isPending}
          onClick={() => runMutation.mutate(true)}
        >
          {t('system.dbPreviewAction')}
        </Button>
        <Button
          size="small"
          variant="contained"
          color="warning"
          startIcon={<BuildIcon />}
          disabled={runMutation.isPending}
          onClick={() => runMutation.mutate(false)}
        >
          {t('system.dbApplyAction')}
        </Button>
      </Stack>

      <Collapse in={!!cfg.last_run}>
        <Alert severity="info" variant="outlined" icon={false} sx={{ mt: 1.5, py: 0.5 }}>
          <Typography variant="caption" display="block">
            {t('system.retentionLastRun')}:{' '}
            {cfg.last_run ? new Date(cfg.last_run).toLocaleString() : '—'}
          </Typography>
          {cfg.last_mode != null && (
            <Typography variant="caption" display="block">
              {t('system.retentionLastStats', {
                mode: cfg.last_mode,
                n: cfg.last_deleted_count ?? 0,
                mb: Math.round((cfg.last_freed_bytes ?? 0) / 1024 / 1024),
              })}
            </Typography>
          )}
        </Alert>
      </Collapse>
    </Box>
  );
}
