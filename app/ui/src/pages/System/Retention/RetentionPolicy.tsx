import { type FormEvent, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import axios from 'axios';
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import FormControlLabel from '@mui/material/FormControlLabel';
import LinearProgress from '@mui/material/LinearProgress';
import MenuItem from '@mui/material/MenuItem';
import Stack from '@mui/material/Stack';
import Switch from '@mui/material/Switch';
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

type FormData = Omit<RetentionConfig, 'last_run' | 'last_deleted_count' | 'last_freed_bytes' | 'last_mode'>;

function retentionModeLabel(t: (key: string) => string, mode: RetentionMode | string): string {
  const map: Record<RetentionMode, string> = {
    cascade: 'system.retentionModeOptionCascade',
    files_only: 'system.retentionModeOptionFilesOnly',
    disabled: 'system.retentionModeOptionDisabled',
  };
  const k = map[mode as RetentionMode];
  return k ? t(k) : String(mode);
}

function toFormData(config: RetentionConfig): FormData {
  return {
    mode: config.mode,
    days: config.days ?? null,
    max_gb: config.max_gb ?? null,
    dataset_max_age_days: config.dataset_max_age_days,
    migration_max_age_days: config.migration_max_age_days,
    protect_favorites: config.protect_favorites,
    min_age_hours: config.min_age_hours,
    batch_size: config.batch_size,
  };
}

/** Политика хранения записей: превью/запуск (режим из конфига можно переопределить на время запроса). */
export function RetentionPolicy() {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const [runMode, setRunMode] = useState<RetentionMode>('cascade');
  const [formData, setFormData] = useState<FormData | null>(null);

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

  useEffect(() => {
    if (configQuery.data) {
      setFormData({
        mode: configQuery.data.mode,
        days: configQuery.data.days ?? null,
        max_gb: configQuery.data.max_gb ?? null,
        dataset_max_age_days: configQuery.data.dataset_max_age_days,
        migration_max_age_days: configQuery.data.migration_max_age_days,
        protect_favorites: configQuery.data.protect_favorites,
        min_age_hours: configQuery.data.min_age_hours,
        batch_size: configQuery.data.batch_size,
      });
    }
  }, [configQuery.data]);

  const updateMutation = useMutation({
    mutationFn: async (data: FormData) => {
      const res = await axios.put<RetentionConfig>(
        `${BASE_API_URL}/system/retention`,
        data,
      );
      return res.data;
    },
    onSuccess: (updated) => {
      void qc.invalidateQueries({ queryKey: queryKeys.system.retentionConfig });
      setFormData(toFormData(updated));
      setRunMode(updated.mode);
    },
    onError: (error) => {
      console.error('Failed to update retention config', error);
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
  const savedFormData = toFormData(cfg);
  const hasLocalChanges =
    !!formData && JSON.stringify(formData) !== JSON.stringify(savedFormData);

  const setField = <K extends keyof FormData>(key: K, value: FormData[K]) => {
    setFormData((prev) => (prev ? { ...prev, [key]: value } : prev));
  };

  const nullableNumber = (value: string): number | null =>
    value === '' ? null : Number(value);

  const boundedNumber = (value: string, fallback: number, min: number): number =>
    Math.max(min, Number.isFinite(Number(value)) ? Number(value) : fallback);

  const onSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (formData) {
      updateMutation.mutate(formData);
    }
  };

  return (
    <Box component="form" onSubmit={onSubmit} noValidate>
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

      <Stack spacing={2} sx={{ maxWidth: 600 }}>
        <TextField
          select
          size="small"
          label={t('system.retentionModeConfigLabel')}
          value={formData?.mode ?? cfg.mode}
          onChange={(e) => setField('mode', e.target.value as RetentionMode)}
          fullWidth
          disabled={updateMutation.isPending}
          helperText={t('system.retentionModeConfigHelper')}
        >
          <MenuItem value="cascade">{retentionModeLabel(t, 'cascade')}</MenuItem>
          <MenuItem value="files_only">{retentionModeLabel(t, 'files_only')}</MenuItem>
          <MenuItem value="disabled">{retentionModeLabel(t, 'disabled')}</MenuItem>
        </TextField>

        <TextField
          label={t('system.retentionDays')}
          size="small"
          type="number"
          inputProps={{ min: 0, step: 1 }}
          value={formData?.days ?? ''}
          onChange={(e) => {
            setField('days', nullableNumber(e.target.value));
          }}
          fullWidth
          disabled={updateMutation.isPending}
          helperText={t('system.retentionDaysHelper')}
        />

        <TextField
          label={t('system.retentionMaxGb')}
          size="small"
          type="number"
          inputProps={{ min: 0, step: 1 }}
          value={formData?.max_gb ?? ''}
          onChange={(e) => {
            setField('max_gb', nullableNumber(e.target.value));
          }}
          fullWidth
          disabled={updateMutation.isPending}
          helperText={t('system.retentionMaxGbHelper')}
        />

        <TextField
          label={t('system.retentionDatasetTtl')}
          size="small"
          type="number"
          inputProps={{ min: 0, step: 1 }}
          value={formData?.dataset_max_age_days ?? 0}
          onChange={(e) =>
            setField('dataset_max_age_days', boundedNumber(e.target.value, 0, 0))
          }
          fullWidth
          disabled={updateMutation.isPending}
          helperText={t('system.retentionDatasetTtlHelper')}
        />

        <TextField
          label={t('system.retentionMigrationTtl')}
          size="small"
          type="number"
          inputProps={{ min: 0, step: 1 }}
          value={formData?.migration_max_age_days ?? 0}
          onChange={(e) =>
            setField('migration_max_age_days', boundedNumber(e.target.value, 0, 0))
          }
          fullWidth
          disabled={updateMutation.isPending}
          helperText={t('system.retentionMigrationTtlHelper')}
        />

        <Box>
          <FormControlLabel
            control={
              <Switch
                checked={formData?.protect_favorites ?? true}
                onChange={(e) => setField('protect_favorites', e.target.checked)}
                disabled={updateMutation.isPending}
              />
            }
            label={t('system.retentionProtectFavorites')}
          />
          <Typography variant="caption" color="text.secondary" display="block" sx={{ mt: -0.5, mb: 0.5 }}>
            {t('system.retentionProtectFavoritesHelper')}
          </Typography>
        </Box>

        <TextField
          label={t('system.retentionMinAgeHours')}
          size="small"
          type="number"
          inputProps={{ min: 0, step: 1 }}
          value={formData?.min_age_hours ?? 1}
          onChange={(e) =>
            setField('min_age_hours', boundedNumber(e.target.value, 1, 0))
          }
          fullWidth
          disabled={updateMutation.isPending}
          helperText={t('system.retentionMinAgeHoursHelper')}
        />

        <TextField
          label={t('system.retentionBatch')}
          size="small"
          type="number"
          inputProps={{ min: 1, step: 1 }}
          value={formData?.batch_size ?? 50}
          onChange={(e) =>
            setField('batch_size', boundedNumber(e.target.value, 50, 1))
          }
          fullWidth
          disabled={updateMutation.isPending}
          helperText={t('system.retentionBatchHelper')}
        />

        <Stack direction="row" spacing={1}>
          <Button
            type="submit"
            variant="contained"
            color="primary"
            disabled={!hasLocalChanges || updateMutation.isPending}
          >
            {t('system.save')}
          </Button>
          <Button
            variant="outlined"
            onClick={() => setFormData(savedFormData)}
            disabled={updateMutation.isPending}
          >
            {t('system.cancel')}
          </Button>
        </Stack>

        {updateMutation.isError && (
          <Alert severity="error">
            {updateMutation.error instanceof Error
              ? updateMutation.error.message
              : t('system.saveError')}
          </Alert>
        )}

        {updateMutation.isSuccess && (
          <Alert severity="success">{t('system.saveSuccess')}</Alert>
        )}
      </Stack>

      <Stack spacing={1.5} sx={{ mt: 3 }}>
        <TextField
          select
          size="small"
          label={t('system.retentionModeRunLabel')}
          value={runMode}
          onChange={(e) => setRunMode(e.target.value as RetentionMode)}
          fullWidth
          disabled={runMutation.isPending}
          helperText={t('system.retentionModeRunHelper')}
        >
          <MenuItem value="cascade">{retentionModeLabel(t, 'cascade')}</MenuItem>
          <MenuItem value="files_only">{retentionModeLabel(t, 'files_only')}</MenuItem>
          <MenuItem value="disabled">{retentionModeLabel(t, 'disabled')}</MenuItem>
        </TextField>
        <Typography variant="subtitle2" gutterBottom>
          {t('system.retentionPreview')
            + (runMode === 'disabled' ? ` — ${t('system.retentionDisabled')}` : '')}
        </Typography>
        <Typography variant="caption" color="text.secondary">
          {t('system.retentionConfigFromServer')}: {retentionModeLabel(t, cfg.mode)},{' '}
          {t('system.retentionDays')}:{' '}
          {cfg.days ?? '—'}, {t('system.retentionMaxGb')}: {cfg.max_gb ?? '—'},{' '}
          {t('system.retentionDatasetTtl')}: {cfg.dataset_max_age_days},{' '}
          {t('system.retentionMigrationTtl')}: {cfg.migration_max_age_days},{' '}
          {t('system.retentionProtectFavorites')}:{' '}
          {cfg.protect_favorites ? t('system.retentionBoolYes') : t('system.retentionBoolNo')},{' '}
          {t('system.retentionMinAgeHours')}: {cfg.min_age_hours},{' '}
          {t('system.retentionBatch')}: {cfg.batch_size}
        </Typography>

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
      </Stack>
    </Box>
  );
}
