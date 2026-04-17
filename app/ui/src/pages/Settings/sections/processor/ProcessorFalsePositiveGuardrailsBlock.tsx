import { useTranslation } from 'react-i18next';
import type { ReactFormExtendedApi } from '@tanstack/react-form';
import Grid from '@mui/material/Grid2';
import Switch from '@mui/material/Switch';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';
import FormControlLabel from '@mui/material/FormControlLabel';
import FormControl from '@mui/material/FormControl';
import FormHelperText from '@mui/material/FormHelperText';
import { ServiceBlock } from '../../shared/ServiceBlock';
import type { Settings } from '../../../../types';

type Props = {
  form: ReactFormExtendedApi<Settings, undefined>;
};

export function ProcessorFalsePositiveGuardrailsBlock({ form }: Props) {
  const { t } = useTranslation();

  return (
    <ServiceBlock title={t('settings.falsePositiveGuardrailsTitle')}>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        {t('settings.falsePositiveGuardrailsDesc')}
      </Typography>
      <Grid container spacing={2}>
        <Grid size={{ xs: 12, sm: 8 }}>
          <form.Field name="processor.detector_scope">
            {(field) => {
              const val = Array.isArray(field.state.value)
                ? field.state.value
                : [];
              const str = val
                .map((item) => String(item).trim())
                .filter(Boolean)
                .join(', ');
              return (
                <TextField
                  fullWidth
                  multiline
                  minRows={2}
                  value={str}
                  onChange={(e) => {
                    const items = e.target.value
                      .split(/[\n,]/)
                      .map((s) => s.trim())
                      .filter(Boolean);
                    field.handleChange(items.length ? items : []);
                  }}
                  label={t('settings.detectorScope')}
                  helperText={t('settings.detectorScopeHint')}
                  placeholder="Bird, Squirrel"
                />
              );
            }}
          </form.Field>
        </Grid>
        <Grid size={{ xs: 12, sm: 4 }}>
          <form.Field name="processor.classifier_fallback_bird">
            {(field) => (
              <FormControl fullWidth>
                <FormControlLabel
                  control={
                    <Switch
                      checked={field.state.value !== false}
                      onChange={(e) => field.handleChange(e.target.checked)}
                    />
                  }
                  label={t('settings.classifierFallbackBird')}
                />
                <FormHelperText>
                  {t('settings.classifierFallbackBirdHint')}
                </FormHelperText>
              </FormControl>
            )}
          </form.Field>
        </Grid>
        <Grid size={{ xs: 12 }}>
          <form.Field name="processor.included_bird_families">
            {(field) => {
              const val = Array.isArray(field.state.value)
                ? field.state.value
                : [];
              const str = val
                .map((item) => String(item).trim())
                .filter(Boolean)
                .join('\n');
              return (
                <TextField
                  fullWidth
                  multiline
                  minRows={3}
                  value={str}
                  onChange={(e) => {
                    const items = e.target.value
                      .split(/[\n,]/)
                      .map((s) => s.trim())
                      .filter(Boolean);
                    field.handleChange(items.length ? items : []);
                  }}
                  label={t('settings.birdFamilies')}
                  helperText={t('settings.includedBirdFamiliesHint')}
                  placeholder="Perching Birds"
                />
              );
            }}
          </form.Field>
        </Grid>
      </Grid>
    </ServiceBlock>
  );
}
