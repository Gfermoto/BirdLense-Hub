import { useTranslation } from 'react-i18next';
import type { ReactFormExtendedApi } from '@tanstack/react-form';
import Grid from '@mui/material/Grid2';
import Switch from '@mui/material/Switch';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';
import FormControlLabel from '@mui/material/FormControlLabel';
import FormHelperText from '@mui/material/FormHelperText';
import { ServiceBlock } from '../../shared/ServiceBlock';
import type { Settings } from '../../../../types';

type Props = {
  form: ReactFormExtendedApi<Settings, undefined>;
};

export function ProcessorTrackRegenBlock({ form }: Props) {
  const { t } = useTranslation();

  return (
    <ServiceBlock title={t('settings.processorTrackRegenTitle')}>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        {t('settings.processorTrackRegenDesc')}
      </Typography>
      <Grid container spacing={2}>
        <Grid size={{ xs: 12, sm: 6 }}>
          <form.Field name="processor.track_regen_frame_step">
            {(field) => (
              <TextField
                fullWidth
                type="number"
                inputProps={{ min: 1, max: 30, step: 1 }}
                value={field.state.value ?? 6}
                onChange={(e) =>
                  field.handleChange(Number(e.target.value) || 1)
                }
                label={t('settings.processorTrackRegenFrameStep')}
                helperText={t('settings.processorTrackRegenFrameStepHint')}
              />
            )}
          </form.Field>
        </Grid>
        <Grid size={{ xs: 12, sm: 6 }}>
          <form.Field name="processor.track_regen_detection_strategy">
            {(field) => (
              <TextField
                fullWidth
                value={field.state.value ?? 'two_stage'}
                onChange={(e) => field.handleChange(e.target.value)}
                label={t('settings.processorTrackRegenDetectionStrategy')}
                helperText={t(
                  'settings.processorTrackRegenDetectionStrategyHint',
                )}
              />
            )}
          </form.Field>
        </Grid>
        <Grid size={{ xs: 12, sm: 6 }}>
          <form.Field name="processor.track_regen_lores_px">
            {(field) => (
              <TextField
                fullWidth
                type="number"
                inputProps={{ min: 320, max: 1280, step: 32 }}
                value={field.state.value ?? 640}
                onChange={(e) =>
                  field.handleChange(Number(e.target.value) || 640)
                }
                label={t('settings.processorTrackRegenLoresPx')}
                helperText={t('settings.processorTrackRegenLoresPxHint')}
              />
            )}
          </form.Field>
        </Grid>
        <Grid size={{ xs: 12, sm: 6 }}>
          <form.Field name="processor.track_regen_video_timeout_sec">
            {(field) => (
              <TextField
                fullWidth
                type="number"
                inputProps={{ min: 30, max: 7200, step: 10 }}
                value={field.state.value ?? 300}
                onChange={(e) =>
                  field.handleChange(Number(e.target.value) || 300)
                }
                label={t('settings.processorTrackRegenVideoTimeoutSec')}
                helperText={t(
                  'settings.processorTrackRegenVideoTimeoutSecHint',
                )}
              />
            )}
          </form.Field>
        </Grid>
        <Grid size={{ xs: 12, sm: 6 }}>
          <form.Field name="processor.track_regen_precise_timeout_sec">
            {(field) => (
              <TextField
                fullWidth
                type="number"
                inputProps={{ min: 60, max: 7200, step: 10 }}
                value={field.state.value ?? 420}
                onChange={(e) =>
                  field.handleChange(Number(e.target.value) || 420)
                }
                label={t('settings.processorTrackRegenPreciseTimeoutSec')}
                helperText={t(
                  'settings.processorTrackRegenPreciseTimeoutSecHint',
                )}
              />
            )}
          </form.Field>
        </Grid>
        <Grid size={{ xs: 12, sm: 6 }}>
          <form.Field name="processor.track_regen_precise_detection_strategy">
            {(field) => (
              <TextField
                fullWidth
                value={field.state.value ?? 'two_stage'}
                onChange={(e) => field.handleChange(e.target.value)}
                label={t('settings.processorTrackRegenPreciseDetectionStrategy')}
                helperText={t(
                  'settings.processorTrackRegenPreciseDetectionStrategyHint',
                )}
              />
            )}
          </form.Field>
        </Grid>
        <Grid size={{ xs: 12, sm: 6 }}>
          <form.Field name="processor.track_regen_precise_min_center_dist">
            {(field) => (
              <TextField
                fullWidth
                type="number"
                inputProps={{ min: 0.01, max: 0.2, step: 0.005 }}
                value={field.state.value ?? 0.02}
                onChange={(e) =>
                  field.handleChange(Number(e.target.value) || 0.02)
                }
                label={t('settings.processorTrackRegenPreciseMinCenterDist')}
                helperText={t(
                  'settings.processorTrackRegenPreciseMinCenterDistHint',
                )}
              />
            )}
          </form.Field>
        </Grid>
        <Grid size={{ xs: 12 }}>
          <form.Field name="processor.track_regen_ignore_regional_species">
            {(field) => (
              <FormControlLabel
                control={
                  <Switch
                    checked={field.state.value !== false}
                    onChange={(e) => field.handleChange(e.target.checked)}
                  />
                }
                label={t('settings.processorTrackRegenIgnoreRegionalSpecies')}
              />
            )}
          </form.Field>
          <FormHelperText sx={{ ml: 0, mt: 0.5 }}>
            {t('settings.processorTrackRegenIgnoreRegionalSpeciesHint')}
          </FormHelperText>
        </Grid>
        <Grid size={{ xs: 12 }}>
          <form.Field name="processor.track_regen_match_live_pipeline">
            {(field) => (
              <FormControlLabel
                control={
                  <Switch
                    checked={field.state.value ?? false}
                    onChange={(e) => field.handleChange(e.target.checked)}
                  />
                }
                label={t('settings.processorTrackRegenMatchLivePipeline')}
              />
            )}
          </form.Field>
          <FormHelperText sx={{ ml: 0, mt: 0.5 }}>
            {t('settings.processorTrackRegenMatchLivePipelineHint')}
          </FormHelperText>
        </Grid>
        <Grid size={{ xs: 12 }}>
          <form.Field name="processor.track_regen_parallel_auto_with_manual">
            {(field) => (
              <FormControlLabel
                control={
                  <Switch
                    checked={field.state.value ?? false}
                    onChange={(e) => field.handleChange(e.target.checked)}
                  />
                }
                label={t('settings.processorTrackRegenParallelAutoWithManual')}
              />
            )}
          </form.Field>
          <FormHelperText sx={{ ml: 0, mt: 0.5 }}>
            {t('settings.processorTrackRegenParallelAutoWithManualHint')}
          </FormHelperText>
        </Grid>
      </Grid>
    </ServiceBlock>
  );
}
