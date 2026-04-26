import { useTranslation } from 'react-i18next';
import type { ReactFormExtendedApi } from '@tanstack/react-form';
import Grid from '@mui/material/Grid2';
import Switch from '@mui/material/Switch';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';
import FormControlLabel from '@mui/material/FormControlLabel';
import FormHelperText from '@mui/material/FormHelperText';
import MenuItem from '@mui/material/MenuItem';
import FormControl from '@mui/material/FormControl';
import InputLabel from '@mui/material/InputLabel';
import Select from '@mui/material/Select';
import { ServiceBlock } from '../../shared/ServiceBlock';
import type { Settings } from '../../../../types';

type Props = {
  form: ReactFormExtendedApi<Settings, undefined>;
};

export function ProcessorBirdnetExtendedBlock({ form }: Props) {
  const { t } = useTranslation();

  return (
    <ServiceBlock title={t('settings.processorBirdnetExtendedTitle')}>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        {t('settings.processorBirdnetExtendedDesc')}
      </Typography>
      <Grid container spacing={2}>
        <Typography variant="subtitle2" sx={{ width: '100%', px: 1, mt: 0.5 }}>
          {t('settings.processorBirdnetPriorHeading')}
        </Typography>
        <Grid size={{ xs: 12, sm: 6 }}>
          <form.Field name="processor.birdnet_mqtt_prior_window_hours">
            {(field) => (
              <TextField
                fullWidth
                type="number"
                inputProps={{ min: 1, max: 168, step: 1 }}
                value={field.state.value ?? 24}
                onChange={(e) =>
                  field.handleChange(Number(e.target.value) || 24)
                }
                label={t('settings.processorBirdnetPriorWindowHours')}
                helperText={t('settings.processorBirdnetPriorWindowHoursHint')}
              />
            )}
          </form.Field>
        </Grid>
        <Grid size={{ xs: 12, sm: 6 }}>
          <form.Field name="processor.birdnet_mqtt_prior_ttl_hours">
            {(field) => (
              <TextField
                fullWidth
                type="number"
                inputProps={{ min: 1, max: 200, step: 1 }}
                value={field.state.value ?? 25}
                onChange={(e) =>
                  field.handleChange(Number(e.target.value) || 25)
                }
                label={t('settings.processorBirdnetPriorTtlHours')}
                helperText={t('settings.processorBirdnetPriorTtlHoursHint')}
              />
            )}
          </form.Field>
        </Grid>
        <Grid size={{ xs: 12, sm: 6 }}>
          <form.Field name="processor.birdnet_mqtt_prior_half_life_hours">
            {(field) => (
              <TextField
                fullWidth
                type="number"
                inputProps={{ min: 0.5, max: 72, step: 0.5 }}
                value={field.state.value ?? 6}
                onChange={(e) =>
                  field.handleChange(Number(e.target.value) || 6)
                }
                label={t('settings.processorBirdnetPriorHalfLifeHours')}
                helperText={t(
                  'settings.processorBirdnetPriorHalfLifeHoursHint',
                )}
              />
            )}
          </form.Field>
        </Grid>
        <Grid size={{ xs: 12, sm: 6 }}>
          <form.Field name="processor.birdnet_mqtt_prior_min_confidence">
            {(field) => (
              <TextField
                fullWidth
                type="number"
                inputProps={{ min: 0, max: 1, step: 0.05 }}
                value={field.state.value ?? 0}
                onChange={(e) =>
                  field.handleChange(Number(e.target.value) || 0)
                }
                label={t('settings.processorBirdnetPriorMinConfidence')}
                helperText={t(
                  'settings.processorBirdnetPriorMinConfidenceHint',
                )}
              />
            )}
          </form.Field>
        </Grid>
        <Grid size={{ xs: 12, sm: 6 }}>
          <form.Field name="processor.birdnet_mqtt_bias_window_seconds">
            {(field) => (
              <TextField
                fullWidth
                type="number"
                inputProps={{ min: 0, max: 86400, step: 1 }}
                value={field.state.value ?? 0}
                onChange={(e) =>
                  field.handleChange(Number(e.target.value) || 0)
                }
                label={t('settings.processorBirdnetBiasWindowSeconds')}
                helperText={t('settings.processorBirdnetBiasWindowSecondsHint')}
              />
            )}
          </form.Field>
        </Grid>
        <Typography variant="subtitle2" sx={{ width: '100%', px: 1, mt: 1 }}>
          {t('settings.processorBirdnetFifoHeading')}
        </Typography>
        <Grid size={{ xs: 12 }}>
          <form.Field name="processor.birdnet_fifo_snapshot_enabled">
            {(field) => (
              <FormControlLabel
                control={
                  <Switch
                    checked={field.state.value !== false}
                    onChange={(e) => field.handleChange(e.target.checked)}
                  />
                }
                label={t('settings.processorBirdnetFifoSnapshotEnabled')}
              />
            )}
          </form.Field>
          <FormHelperText sx={{ ml: 0, mt: 0.5 }}>
            {t('settings.processorBirdnetFifoSnapshotEnabledHint')}
          </FormHelperText>
        </Grid>
        <Grid size={{ xs: 12, sm: 6 }}>
          <form.Field name="processor.birdnet_fifo_snapshot_interval_sec">
            {(field) => (
              <TextField
                fullWidth
                type="number"
                inputProps={{ min: 1, max: 300, step: 1 }}
                value={field.state.value ?? 3}
                onChange={(e) =>
                  field.handleChange(Number(e.target.value) || 3)
                }
                label={t('settings.processorBirdnetFifoSnapshotIntervalSec')}
                helperText={t(
                  'settings.processorBirdnetFifoSnapshotIntervalSecHint',
                )}
              />
            )}
          </form.Field>
        </Grid>
        <Grid size={{ xs: 12, sm: 6 }}>
          <form.Field name="processor.birdnet_fifo_snapshot_recent_limit">
            {(field) => (
              <TextField
                fullWidth
                type="number"
                inputProps={{ min: 10, max: 500, step: 1 }}
                value={field.state.value ?? 80}
                onChange={(e) =>
                  field.handleChange(Number(e.target.value) || 80)
                }
                label={t('settings.processorBirdnetFifoSnapshotRecentLimit')}
                helperText={t(
                  'settings.processorBirdnetFifoSnapshotRecentLimitHint',
                )}
              />
            )}
          </form.Field>
        </Grid>
        <Grid size={{ xs: 12, sm: 6 }}>
          <form.Field name="processor.birdnet_fifo_snapshot_stale_sec">
            {(field) => (
              <TextField
                fullWidth
                type="number"
                inputProps={{ min: 30, max: 3600, step: 1 }}
                value={field.state.value ?? 180}
                onChange={(e) =>
                  field.handleChange(Number(e.target.value) || 180)
                }
                label={t('settings.processorBirdnetFifoSnapshotStaleSec')}
                helperText={t(
                  'settings.processorBirdnetFifoSnapshotStaleSecHint',
                )}
              />
            )}
          </form.Field>
        </Grid>
        <Grid size={{ xs: 12, sm: 6 }}>
          <form.Field name="processor.birdnet_fifo_hearing_active_hours">
            {(field) => (
              <TextField
                fullWidth
                type="number"
                inputProps={{ min: 1, max: 168, step: 1 }}
                value={field.state.value ?? 24}
                onChange={(e) =>
                  field.handleChange(Number(e.target.value) || 24)
                }
                label={t('settings.processorBirdnetFifoHearingActiveHours')}
                helperText={t(
                  'settings.processorBirdnetFifoHearingActiveHoursHint',
                )}
              />
            )}
          </form.Field>
        </Grid>
        <Grid size={{ xs: 12 }}>
          <form.Field name="processor.birdnet_fifo_persist_enabled">
            {(field) => (
              <FormControlLabel
                control={
                  <Switch
                    checked={field.state.value !== false}
                    onChange={(e) => field.handleChange(e.target.checked)}
                  />
                }
                label={t('settings.processorBirdnetFifoPersistEnabled')}
              />
            )}
          </form.Field>
        </Grid>
        <Grid size={{ xs: 12, sm: 6 }}>
          <form.Field name="processor.birdnet_fifo_sqlite_busy_ms">
            {(field) => (
              <TextField
                fullWidth
                type="number"
                inputProps={{ min: 1000, max: 120000, step: 1000 }}
                value={field.state.value ?? 30000}
                onChange={(e) =>
                  field.handleChange(Number(e.target.value) || 30000)
                }
                label={t('settings.processorBirdnetFifoSqliteBusyMs')}
                helperText={t('settings.processorBirdnetFifoSqliteBusyMsHint')}
              />
            )}
          </form.Field>
        </Grid>
        <Typography variant="subtitle2" sx={{ width: '100%', px: 1, mt: 1 }}>
          {t('settings.processorBirdnetObservabilityHeading')}
        </Typography>
        <Grid size={{ xs: 12, sm: 6 }}>
          <form.Field name="processor.birdnet_mqtt_observability_level">
            {(field) => (
              <FormControl fullWidth>
                <InputLabel id="bn-obs-label">
                  {t('settings.processorBirdnetObservabilityLevel')}
                </InputLabel>
                <Select
                  labelId="bn-obs-label"
                  label={t('settings.processorBirdnetObservabilityLevel')}
                  value={field.state.value ?? 'info'}
                  onChange={(e) => field.handleChange(String(e.target.value))}
                >
                  <MenuItem value="off">{t('settings.processorBirdnetObsLevelOff')}</MenuItem>
                  <MenuItem value="info">{t('settings.processorBirdnetObsLevelInfo')}</MenuItem>
                  <MenuItem value="debug">{t('settings.processorBirdnetObsLevelDebug')}</MenuItem>
                </Select>
              </FormControl>
            )}
          </form.Field>
        </Grid>
        <Grid size={{ xs: 12, sm: 6 }}>
          <form.Field name="processor.birdnet_mqtt_observability_debug">
            {(field) => (
              <FormControlLabel
                control={
                  <Switch
                    checked={field.state.value ?? false}
                    onChange={(e) => field.handleChange(e.target.checked)}
                  />
                }
                label={t('settings.processorBirdnetObservabilityDebug')}
              />
            )}
          </form.Field>
          <FormHelperText sx={{ ml: 0, mt: 0.5 }}>
            {t('settings.processorBirdnetObservabilityDebugHint')}
          </FormHelperText>
        </Grid>
      </Grid>
    </ServiceBlock>
  );
}
