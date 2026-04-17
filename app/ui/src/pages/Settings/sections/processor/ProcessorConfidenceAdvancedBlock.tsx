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

export function ProcessorConfidenceAdvancedBlock({ form }: Props) {
  const { t } = useTranslation();

  return (
    <ServiceBlock title={t('settings.confidenceAdvanced')}>
      <Grid container spacing={2}>
        <Grid size={{ xs: 12 }}>
          <form.Field name="processor.species_confidence_overrides">
            {(field) => {
              const val = field.state.value;
              const str =
                val && typeof val === 'object' && !Array.isArray(val)
                  ? Object.entries(val)
                      .map(([k, v]) => `${k}: ${v}`)
                      .join('\n')
                  : '';
              return (
                <TextField
                  fullWidth
                  multiline
                  minRows={2}
                  value={str}
                  onChange={(e) => {
                    const lines = e.target.value.split('\n').filter(Boolean);
                    const obj: Record<string, number> = {};
                    for (const line of lines) {
                      const idx = line.indexOf(':');
                      if (idx > 0) {
                        const k = line.slice(0, idx).trim();
                        const v = parseFloat(line.slice(idx + 1).trim());
                        if (!isNaN(v) && v >= 0 && v <= 1) obj[k] = v;
                      }
                    }
                    field.handleChange(Object.keys(obj).length ? obj : {});
                  }}
                  label={t('settings.speciesConfidenceOverrides')}
                  placeholder="Pileated Woodpecker: 0.05"
                  helperText={t('settings.speciesConfidenceOverridesHint')}
                />
              );
            }}
          </form.Field>
        </Grid>
        <Grid size={{ xs: 12 }}>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
            {t('settings.ebirdRegionalTopConfidenceIntro')}
          </Typography>
        </Grid>
        <Grid size={{ xs: 12 }}>
          <form.Field name="processor.ebird_regional_top_auto_confidence">
            {(field) => (
              <FormControlLabel
                control={
                  <Switch
                    checked={field.state.value ?? true}
                    onChange={(e) => field.handleChange(e.target.checked)}
                  />
                }
                label={t('settings.ebirdRegionalTopAutoConfidence')}
              />
            )}
          </form.Field>
          <FormHelperText sx={{ ml: 0, mt: 0.5 }}>
            {t('settings.ebirdRegionalTopAutoConfidenceHint')}
          </FormHelperText>
        </Grid>
        <Grid size={{ xs: 12, sm: 6 }}>
          <form.Field name="processor.ebird_regional_top_confidence_delta">
            {(field) => (
              <TextField
                fullWidth
                type="number"
                inputProps={{ min: 0, max: 0.5, step: 0.01 }}
                value={field.state.value ?? 0.05}
                onChange={(e) =>
                  field.handleChange(Number(e.target.value) || 0.05)
                }
                label={t('settings.ebirdRegionalTopConfidenceDelta')}
                helperText={t('settings.ebirdRegionalTopConfidenceDeltaHint')}
              />
            )}
          </form.Field>
        </Grid>
        <Grid size={{ xs: 12, sm: 6 }}>
          <form.Field name="processor.ebird_regional_top_confidence_floor">
            {(field) => (
              <TextField
                fullWidth
                type="number"
                inputProps={{ min: 0.01, max: 1, step: 0.01 }}
                value={field.state.value ?? 0.05}
                onChange={(e) =>
                  field.handleChange(Number(e.target.value) || 0.05)
                }
                label={t('settings.ebirdRegionalTopConfidenceFloor')}
                helperText={t('settings.ebirdRegionalTopConfidenceFloorHint')}
              />
            )}
          </form.Field>
        </Grid>
        <Grid size={{ xs: 12, sm: 6 }}>
          <form.Field name="ui.unknown_confidence_threshold">
            {(field) => (
              <TextField
                fullWidth
                type="number"
                inputProps={{ min: 0, max: 1, step: 0.05 }}
                value={field.state.value ?? 0.5}
                onChange={(e) =>
                  field.handleChange(Number(e.target.value) || undefined)
                }
                label={t('settings.unknownConfidenceThreshold')}
                helperText={t('settings.unknownConfidenceThresholdHelp')}
              />
            )}
          </form.Field>
        </Grid>
      </Grid>
    </ServiceBlock>
  );
}
