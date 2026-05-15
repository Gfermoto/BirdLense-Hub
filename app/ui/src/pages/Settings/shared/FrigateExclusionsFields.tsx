import { useTranslation } from 'react-i18next';
import type { ReactFormExtendedApi } from '@tanstack/react-form';
import FormControl from '@mui/material/FormControl';
import FormControlLabel from '@mui/material/FormControlLabel';
import FormHelperText from '@mui/material/FormHelperText';
import Grid from '@mui/material/Grid2';
import Switch from '@mui/material/Switch';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';
import type { Settings } from '../../../types';

function splitCsv(value: string): string[] {
  return (value || '')
    .split(',')
    .map((part) => part.trim())
    .filter(Boolean);
}

type Props = {
  form: ReactFormExtendedApi<Settings, undefined>;
  showGeometryToggles?: boolean;
};

/** Shared MQTT label exclusion fields (triggers.frigate.* + detection.frigate_standalone_skip_labels). */
export function FrigateExclusionsFields({
  form,
  showGeometryToggles = true,
}: Props) {
  const { t } = useTranslation();

  return (
    <Grid container spacing={2} id="settings-frigate-exclusions">
      <Grid size={{ xs: 12 }}>
        <Typography variant="body2" color="text.secondary">
          {t('settings.frigateExclusionsIntro')}
        </Typography>
      </Grid>
      <Grid size={{ xs: 12, sm: 6 }}>
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
      </Grid>
      <Grid size={{ xs: 12, sm: 6 }}>
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
      </Grid>
      <Grid size={{ xs: 12, sm: 6 }}>
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
      </Grid>
      {showGeometryToggles ? (
        <>
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
        </>
      ) : null}
    </Grid>
  );
}
