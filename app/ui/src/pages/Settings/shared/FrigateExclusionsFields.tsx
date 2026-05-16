import { useTranslation } from 'react-i18next';
import type { ReactFormExtendedApi } from '@tanstack/react-form';
import Chip from '@mui/material/Chip';
import FormControl from '@mui/material/FormControl';
import FormControlLabel from '@mui/material/FormControlLabel';
import FormHelperText from '@mui/material/FormHelperText';
import Grid from '@mui/material/Grid2';
import Paper from '@mui/material/Paper';
import Stack from '@mui/material/Stack';
import Switch from '@mui/material/Switch';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';
import type { ReactNode } from 'react';
import type { Settings } from '../../../types';

function splitCsv(value: string): string[] {
  return (value || '')
    .split(',')
    .map((part) => part.trim())
    .filter(Boolean);
}

type TierProps = {
  step: number;
  title: string;
  description: string;
  children: ReactNode;
};

function ExclusionTier({ step, title, description, children }: TierProps) {
  return (
    <Paper
      variant="outlined"
      sx={{
        p: 2,
        borderLeftWidth: 3,
        borderLeftStyle: 'solid',
        borderLeftColor: 'primary.main',
      }}
    >
      <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 0.75 }}>
        <Chip label={step} size="small" color="primary" sx={{ minWidth: 28 }} />
        <Typography variant="subtitle2" component="h4">
          {title}
        </Typography>
      </Stack>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
        {description}
      </Typography>
      {children}
    </Paper>
  );
}

type Props = {
  form: ReactFormExtendedApi<Settings, undefined>;
  showGeometryToggles?: boolean;
};

/** MQTT label allow/block policy for triggers.frigate.* and detection.frigate_standalone_skip_labels. */
export function FrigateExclusionsFields({
  form,
  showGeometryToggles = true,
}: Props) {
  const { t } = useTranslation();

  return (
    <Grid container spacing={2} id="settings-frigate-exclusions">
      <Grid size={{ xs: 12 }}>
        <Typography variant="subtitle2" component="h3" sx={{ mb: 0.5 }}>
          {t('settings.frigateExclusionsHeading')}
        </Typography>
        <Typography variant="body2" color="text.secondary">
          {t('settings.frigateExclusionsIntro')}
        </Typography>
      </Grid>

      <Grid size={{ xs: 12 }}>
        <ExclusionTier
          step={1}
          title={t('settings.frigateExclusionTier1Title')}
          description={t('settings.frigateExclusionTier1Desc')}
        >
          <form.Field name="triggers.frigate.label_exclude">
            {(field) => (
              <TextField
                fullWidth
                value={(field.state.value || []).join(', ')}
                onChange={(e) => field.handleChange(splitCsv(e.target.value))}
                label={t('settings.frigateLabelExclude')}
                placeholder={t('settings.frigateLabelExcludePlaceholder')}
                helperText={t('settings.frigateLabelExcludeHint')}
              />
            )}
          </form.Field>
        </ExclusionTier>
      </Grid>

      <Grid size={{ xs: 12 }}>
        <ExclusionTier
          step={2}
          title={t('settings.frigateExclusionTier2Title')}
          description={t('settings.frigateExclusionTier2Desc')}
        >
          <form.Field name="triggers.frigate.geometry_fallback_label_exclude">
            {(field) => (
              <TextField
                fullWidth
                value={(field.state.value || []).join(', ')}
                onChange={(e) => field.handleChange(splitCsv(e.target.value))}
                label={t('settings.frigateGeometryFallbackExclude')}
                placeholder={t(
                  'settings.frigateGeometryFallbackExcludePlaceholder',
                )}
                helperText={t('settings.frigateGeometryFallbackExcludeHint')}
              />
            )}
          </form.Field>
        </ExclusionTier>
      </Grid>

      <Grid size={{ xs: 12 }}>
        <ExclusionTier
          step={3}
          title={t('settings.frigateExclusionTier3Title')}
          description={t('settings.frigateExclusionTier3Desc')}
        >
          <form.Field name="detection.frigate_standalone_skip_labels">
            {(field) => (
              <TextField
                fullWidth
                value={(field.state.value || []).join(', ')}
                onChange={(e) => field.handleChange(splitCsv(e.target.value))}
                label={t('settings.frigateStandaloneSkipLabels')}
                placeholder={t('settings.frigateStandaloneSkipLabelsPlaceholder')}
                helperText={t('settings.frigateStandaloneSkipLabelsHint')}
              />
            )}
          </form.Field>
        </ExclusionTier>
      </Grid>

      {showGeometryToggles ? (
        <Grid size={{ xs: 12 }}>
          <Paper variant="outlined" sx={{ p: 2 }}>
            <Typography variant="subtitle2" component="h4" sx={{ mb: 0.5 }}>
              {t('settings.frigateGeometryHeading')}
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
              {t('settings.frigateGeometryDesc')}
            </Typography>
            <Grid container spacing={2}>
              <Grid size={{ xs: 12, sm: 6 }}>
                <form.Field name="triggers.frigate.trigger_on_tracked_object">
                  {(field) => (
                    <FormControl fullWidth>
                      <FormControlLabel
                        control={
                          <Switch
                            checked={field.state.value !== false}
                            onChange={(e) => field.handleChange(e.target.checked)}
                          />
                        }
                        label={t('settings.frigateTriggerOnGeometry')}
                      />
                      <FormHelperText>
                        {t('settings.frigateTriggerOnGeometryHint')}
                      </FormHelperText>
                    </FormControl>
                  )}
                </form.Field>
              </Grid>
              <Grid size={{ xs: 12, sm: 6 }}>
                <form.Field name="triggers.frigate.geometry_fallback_enabled">
                  {(field) => (
                    <FormControl fullWidth>
                      <FormControlLabel
                        control={
                          <Switch
                            checked={field.state.value !== false}
                            onChange={(e) => field.handleChange(e.target.checked)}
                          />
                        }
                        label={t('settings.frigateGeometryFallbackEnabled')}
                      />
                      <FormHelperText>
                        {t('settings.frigateGeometryFallbackEnabledHint')}
                      </FormHelperText>
                    </FormControl>
                  )}
                </form.Field>
              </Grid>
            </Grid>
          </Paper>
        </Grid>
      ) : null}
    </Grid>
  );
}
