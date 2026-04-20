import { useTranslation } from 'react-i18next';
import type { ReactFormExtendedApi } from '@tanstack/react-form';
import Grid from '@mui/material/Grid2';
import Switch from '@mui/material/Switch';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';
import FormControlLabel from '@mui/material/FormControlLabel';
import FormHelperText from '@mui/material/FormHelperText';
import Divider from '@mui/material/Divider';
import { ServiceBlock } from '../../shared/ServiceBlock';
import type { Settings } from '../../../../types';

type Props = {
  form: ReactFormExtendedApi<Settings, undefined>;
};

export function ProcessorAdaptiveProfilesBlock({ form }: Props) {
  const { t } = useTranslation();

  return (
    <ServiceBlock title={t('settings.processorAdaptiveProfilesTitle')}>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        {t('settings.processorAdaptiveProfilesDesc')}
      </Typography>
      <Grid container spacing={2}>
        <Grid size={{ xs: 12 }}>
          <form.Field name="processor.adaptive_profiles.enabled">
            {(field) => (
              <FormControlLabel
                control={
                  <Switch
                    checked={field.state.value ?? false}
                    onChange={(e) => field.handleChange(e.target.checked)}
                  />
                }
                label={t('settings.processorAdaptiveProfilesEnabled')}
              />
            )}
          </form.Field>
          <FormHelperText sx={{ ml: 0, mt: 0.5 }}>
            {t('settings.processorAdaptiveProfilesEnabledHint')}
          </FormHelperText>
        </Grid>
        <Grid size={{ xs: 12 }}>
          <Divider sx={{ my: 1 }} />
          <Typography variant="subtitle2" sx={{ mb: 1 }}>
            {t('settings.processorNightThresholdsHeading')}
          </Typography>
        </Grid>
        <Grid size={{ xs: 12, sm: 6 }}>
          <form.Field name="processor.adaptive_profiles.night.max_brightness">
            {(field) => (
              <TextField
                fullWidth
                type="number"
                inputProps={{ min: 0, max: 255, step: 0.5 }}
                value={field.state.value ?? 18}
                onChange={(e) =>
                  field.handleChange(Number(e.target.value) || 0)
                }
                label={t('settings.processorNightMaxBrightness')}
                helperText={t('settings.processorNightMaxBrightnessHint')}
              />
            )}
          </form.Field>
        </Grid>
        <Grid size={{ xs: 12, sm: 6 }}>
          <form.Field name="processor.adaptive_profiles.night.max_contrast">
            {(field) => (
              <TextField
                fullWidth
                type="number"
                inputProps={{ min: 0, max: 255, step: 0.5 }}
                value={field.state.value ?? 12}
                onChange={(e) =>
                  field.handleChange(Number(e.target.value) || 0)
                }
                label={t('settings.processorNightMaxContrast')}
                helperText={t('settings.processorNightMaxContrastHint')}
              />
            )}
          </form.Field>
        </Grid>
        <Grid size={{ xs: 12 }}>
          <Divider sx={{ my: 1 }} />
          <Typography variant="subtitle2" sx={{ mb: 1 }}>
            {t('settings.processorNightOverridesHeading')}
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
            {t('settings.processorNightOverridesIntro')}
          </Typography>
        </Grid>
        <Grid size={{ xs: 12, sm: 6 }}>
          <form.Field name="processor.adaptive_profiles.night.overrides.light_gate_min_brightness">
            {(field) => (
              <TextField
                fullWidth
                type="number"
                inputProps={{ min: 0, max: 255, step: 0.5 }}
                value={field.state.value ?? 8}
                onChange={(e) =>
                  field.handleChange(Number(e.target.value) || 8)
                }
                label={t('settings.processorOverrideLightGateBrightness')}
                helperText={t(
                  'settings.processorOverrideLightGateBrightnessHint',
                )}
              />
            )}
          </form.Field>
        </Grid>
        <Grid size={{ xs: 12, sm: 6 }}>
          <form.Field name="processor.adaptive_profiles.night.overrides.light_gate_min_contrast">
            {(field) => (
              <TextField
                fullWidth
                type="number"
                inputProps={{ min: 0, max: 255, step: 0.5 }}
                value={field.state.value ?? 6}
                onChange={(e) =>
                  field.handleChange(Number(e.target.value) || 6)
                }
                label={t('settings.processorOverrideLightGateContrast')}
                helperText={t(
                  'settings.processorOverrideLightGateContrastHint',
                )}
              />
            )}
          </form.Field>
        </Grid>
        <Grid size={{ xs: 12, sm: 6 }}>
          <form.Field name="processor.adaptive_profiles.night.overrides.min_confidence_binary">
            {(field) => (
              <TextField
                fullWidth
                type="number"
                inputProps={{ min: 0.05, max: 0.9, step: 0.02 }}
                value={field.state.value ?? 0.24}
                onChange={(e) =>
                  field.handleChange(Number(e.target.value) || 0.24)
                }
                label={t('settings.processorOverrideMinConfidenceBinary')}
                helperText={t(
                  'settings.processorOverrideMinConfidenceBinaryHint',
                )}
              />
            )}
          </form.Field>
        </Grid>
        <Grid size={{ xs: 12, sm: 6 }}>
          <form.Field name="processor.adaptive_profiles.night.overrides.min_confidence_binary_bird">
            {(field) => (
              <TextField
                fullWidth
                type="number"
                inputProps={{ min: 0.05, max: 0.9, step: 0.02 }}
                value={field.state.value ?? 0.34}
                onChange={(e) =>
                  field.handleChange(Number(e.target.value) || 0.34)
                }
                label={t('settings.processorOverrideMinConfidenceBinaryBird')}
                helperText={t(
                  'settings.processorOverrideMinConfidenceBinaryBirdHint',
                )}
              />
            )}
          </form.Field>
        </Grid>
        <Grid size={{ xs: 12, sm: 6 }}>
          <form.Field name="processor.adaptive_profiles.night.overrides.min_track_duration">
            {(field) => (
              <TextField
                fullWidth
                type="number"
                inputProps={{ min: 0.1, max: 10, step: 0.1 }}
                value={field.state.value ?? 0.7}
                onChange={(e) =>
                  field.handleChange(Number(e.target.value) || 0.7)
                }
                label={t('settings.processorOverrideMinTrackDuration')}
                helperText={t('settings.processorOverrideMinTrackDurationHint')}
              />
            )}
          </form.Field>
        </Grid>
        <Grid size={{ xs: 12, sm: 6 }}>
          <form.Field name="processor.adaptive_profiles.night.overrides.min_confidence_to_process">
            {(field) => (
              <TextField
                fullWidth
                type="number"
                inputProps={{ min: 0.05, max: 1, step: 0.02 }}
                value={field.state.value ?? 0.34}
                onChange={(e) =>
                  field.handleChange(Number(e.target.value) || 0.34)
                }
                label={t('settings.processorOverrideMinConfidenceToProcess')}
                helperText={t(
                  'settings.processorOverrideMinConfidenceToProcessHint',
                )}
              />
            )}
          </form.Field>
        </Grid>
        <Grid size={{ xs: 12, sm: 6 }}>
          <form.Field name="processor.adaptive_profiles.night.overrides.min_box_size_px">
            {(field) => (
              <TextField
                fullWidth
                type="number"
                inputProps={{ min: 8, max: 256, step: 1 }}
                value={field.state.value ?? 40}
                onChange={(e) =>
                  field.handleChange(Number(e.target.value) || 40)
                }
                label={t('settings.processorOverrideMinBoxSizePx')}
                helperText={t('settings.processorOverrideMinBoxSizePxHint')}
              />
            )}
          </form.Field>
        </Grid>
        <Grid size={{ xs: 12, sm: 6 }}>
          <form.Field name="processor.adaptive_profiles.night.overrides.min_center_dist">
            {(field) => (
              <TextField
                fullWidth
                type="number"
                inputProps={{ min: 0.01, max: 0.25, step: 0.005 }}
                value={field.state.value ?? 0.03}
                onChange={(e) =>
                  field.handleChange(Number(e.target.value) || 0.03)
                }
                label={t('settings.processorOverrideMinCenterDist')}
                helperText={t('settings.processorOverrideMinCenterDistHint')}
              />
            )}
          </form.Field>
        </Grid>
        <Grid size={{ xs: 12, sm: 6 }}>
          <form.Field name="processor.adaptive_profiles.night.overrides.max_classifications_per_frame">
            {(field) => (
              <TextField
                fullWidth
                type="number"
                inputProps={{ min: 1, max: 16, step: 1 }}
                value={field.state.value ?? 4}
                onChange={(e) =>
                  field.handleChange(Number(e.target.value) || 4)
                }
                label={t(
                  'settings.processorOverrideMaxClassificationsPerFrame',
                )}
                helperText={t(
                  'settings.processorOverrideMaxClassificationsPerFrameHint',
                )}
              />
            )}
          </form.Field>
        </Grid>
      </Grid>
    </ServiceBlock>
  );
}
