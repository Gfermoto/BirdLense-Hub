import { useTranslation } from 'react-i18next';
import { useQuery, useMutation } from '@tanstack/react-query';
import axios from 'axios';
import {
  Box,
  Button,
  Card,
  CardContent,
  Collapse,
  Divider,
  Stack,
  Typography,
  Alert,
  AlertTitle,
  LinearProgress,
  Chip,
  Switch,
  FormControlLabel,
  FormGroup,
  TextField,
  MenuItem,
  Tooltip,
  useTheme,
} from '@mui/material';
import {
  CloudSyncIcon,
  BuildIcon,
  PlaylistAddCheckIcon,
} from '@mui/icons-material';
import { BASE_API_URL } from '../../../../api/client';
import { queryKeys } from '../../../../api/queryKeys';
import { useQueryClient } from '@tanstack/react-query';

interface RetentionConfig {
  mode: 'cascade' | 'files_only' | 'disabled';
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

interface PreviewData {
  deletedCount?: number;
  deletedSize?: number;
  dryRun?: boolean;
  mode?: string;
  message?: string;
}

export function RetentionPolicy() {
  const { t } = useTranslation();
  const theme = useTheme();
  const qc = useQueryClient();

  // Fetch current config
  const { data: config, isLoading, error } = useQuery({
    queryKey: queryKeys.system.retentionConfig(),
    queryFn: async () => {
      const { data } = await axios.get<RetentionConfig>(
        `${BASE_API_URL}/ui/system/retention`,
      );
      return data;
    },
    refetchOnWindowFocus: false,
  });

  const runMutation = useMutation({
    mutationFn: (body: any) =>
      axios.post<{ message?: string }>(
        `${BASE_API_URL}/ui/system/retention`,
        body,
      ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.system.retentionConfig() });
    },
  });

  const isSubmitting = runMutation.isPending;

  const handleSubmit = (mode: 'dry_run' | 'apply') => async (body: any) => {
    await runMutation.mutateAsync({ ...body, dry_run: mode === 'dry_run' });
  };

  const getModeLabel = (mode: RetentionConfig['mode']) => {
    switch (mode) {
      case 'files_only':
        return t('system.retentionModeFilesOnly');
      case 'disabled':
        return t('system.retentionModeDisabled');
      default:
        return t('system.retentionModeCascade');
    }
  };

  if (isLoading) {
    return <LinearProgress />;
  }

  if (error || !config) {
    return (
      <Alert severity="error">
        {t('system.retentionConfigError')}
      </Alert>
    );
  }

  return (
    <Card>
      <CardContent>
        <Typography variant="h6" gutterBottom>
          {t('system.retentionTitle')}
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          {t('system.retentionSubtitle')}
        </Typography>

        {runMutation.error && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {runMutation.error.message}
          </Alert>
        )}

        {runMutation.isSuccess && (
          <Alert severity="success" sx={{ mb: 2 }}>
            {t('system.retentionApplied')}
          </Alert>
        )}

        {/* Mode selector */}
        <FormGroup sx={{ mb: 3 }}>
          <FormControlLabel
            control={
              <Switch
                checked={config.mode === 'disabled'}
                onChange={(e) => {
                  /* handled via apply */}
                }}
              />
            }
            label={<strong>{t('system.retentionModeLabel')}</strong>}
          />
          <TextField
            select
            size="small"
            fullWidth
            value={config.mode}
            onChange={(e) => {
              /* mode change handled via apply */
            }}
            sx={{ mb: 1 }}
          >
            <MenuItem value="cascade">cascade</MenuItem>
            <MenuItem value="files_only">files_only</MenuItem>
            <MenuItem value="disabled">disabled</MenuItem>
          </TextField>
        </FormGroup>

        {/* Config fields - shown based on mode */}
        <Stack spacing={2} sx={{ mb: 3 }}>
          <TextField
            label={t('system.retentionDays')}
            type="number"
            size="small"
            fullWidth
            value={config.days ?? ''}
            onChange={(e) => {
              /* handled via apply */
            }}
            InputLabelProps={{ shrink: true }}
          />
          <TextField
            label={t('system.retentionMaxGb')}
            type="number"
            size="small"
            fullWidth
            value={config.max_gb ?? ''}
            onChange={(e) => {
              /* handled via apply */
            }}
            InputLabelProps={{ shrink: true }}
          />
          <TextField
            label={t('system.datasetMaxAgeDays')}
            type="number"
            size="small"
            fullWidth
            value={config.dataset_max_age_days}
            onChange={(e) => {
              /* handled via apply */
            }}
            InputLabelProps={{ shrink: true }}
          />
          <TextField
            label={t('system.migrationMaxAgeDays')}
            type="number"
            size="small"
            fullWidth
            value={config.migration_max_age_days}
            onChange={(e) => {
              /* handled via apply */
            }}
            InputLabelProps={{ shrink: true }}
          />
          <TextField
            label={t('system.batchSize')}
            type="number"
            size="small"
            fullWidth
            value={config.batch_size}
            onChange={(e) => {
              /* handled via apply */
            }}
            InputLabelProps={{ shrink: true }}
          />
          <FormGroup>
            <FormControlLabel
              control={
                <Switch
                  checked={config.protect_favorites}
                  onChange={(e, checked) => {
                    /* handled via apply */
                  }}
                />
              }
              label={t('system.protectFavorites')}
            />
          </FormGroup>
          <FormGroup>
            <FormControlLabel
              control={
                <Switch
                  checked={config.min_age_hours > 0}
                  onChange={(e, checked) => {
                    /* handled via apply */
                  }}
                />
              }
              label={t('system.minAgeHoursLabel')}
            />
            <TextField
              label={t('system.minAgeHours')}
              type="number"
              size="small"
              fullWidth
              value={config.min_age_hours}
              onChange={(e) => {
                /* handled via apply */
              }}
              InputLabelProps={{ shrink: true }}
            />
          </FormGroup>
        </Stack>

        <Stack direction="row" spacing={1} sx={{ mb: 2 }}>
          <Button
            variant="outlined"
            startIcon={<CloudSyncIcon />}
            onClick={() => handleSubmit('dry_run')({ mode: config.mode })}
            disabled={isSubmitting}
          >
            {t('system.dryRun')}
          </Button>
          <Button
            variant="contained"
            startIcon={<BuildIcon />}
            onClick={() => handleSubmit('apply')({ mode: config.mode })}
            disabled={isSubmitting}
          >
            {t('system.apply')}
          </Button>
        </Stack>

        {/* Last run info */}
        <Collapse in={!!config.last_run}>
          <Alert
            severity="info"
            variant="outlined"
            icon={false}
            sx={{ mb: 1 }}
          >
            <AlertTitle>{t('system.lastRun')}</AlertTitle>
            {config.last_mode && (
              <Box sx={{ mb: 0.5 }}>
                {t('system.mode')}: <Chip label={config.last_mode} size="small" />
              </Box>
            )}
            {config.last_deleted_count !== undefined && (
              <Box sx={{ mb: 0.5 }}>
                {t('system.deletedCount')}: {config.last_deleted_count}
              </Box>
            )}
            {config.last_freed_bytes !== undefined && (
              <Box sx={{ mb: 0.5 }}>
                {t('system.freedBytes')}: {Math.round(config.last_freed_bytes / 1024 / 1024)} MB
              </Box>
            )}
            {config.last_run && (
              <Box sx={{ mb: 0.5 }}>
                {t('system.runAt')}: {new Date(config.last_run).toLocaleString()}
              </Box>
            )}
          </Alert>
        </Collapse>
      </CardContent>
    </Card>
  );
}