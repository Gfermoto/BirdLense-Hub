import { useTranslation } from 'react-i18next';
import type { ReactFormExtendedApi } from '@tanstack/react-form';
import Grid from '@mui/material/Grid2';
import TextField from '@mui/material/TextField';
import Checkbox from '@mui/material/Checkbox';
import FormControlLabel from '@mui/material/FormControlLabel';
import FormControl from '@mui/material/FormControl';
import FormHelperText from '@mui/material/FormHelperText';
import { ServiceBlock } from '../../shared/ServiceBlock';
import type { Settings } from '../../../../types';

type Props = {
  form: ReactFormExtendedApi<Settings, undefined>;
};

export function ProcessorSpectrogramDatasetBlock({ form }: Props) {
  const { t } = useTranslation();

  return (
    <ServiceBlock title={t('settings.serviceProcessor')}>
      <Grid container spacing={2}>
        <Grid size={{ xs: 12, sm: 6 }}>
          <form.Field name="processor.spectrogram_px_per_sec">
            {(field) => (
              <TextField
                fullWidth
                type="number"
                value={field.state.value ?? 200}
                onChange={(e) => field.handleChange(Number(e.target.value))}
                label={t('settings.spectrogramDetail')}
                helperText={t('settings.spectrogramDetailHelp')}
              />
            )}
          </form.Field>
        </Grid>
        <Grid size={{ xs: 12 }}>
          <form.Field name="processor.generate_spectrogram_always">
            {(field) => (
              <FormControl fullWidth>
                <FormControlLabel
                  control={
                    <Checkbox
                      checked={field.state.value !== false}
                      onChange={(e) => field.handleChange(e.target.checked)}
                    />
                  }
                  label={t('settings.generateSpectrogramAlways')}
                />
                <FormHelperText>
                  {t('settings.generateSpectrogramAlwaysHelp')}
                </FormHelperText>
              </FormControl>
            )}
          </form.Field>
        </Grid>
        <Grid size={{ xs: 12, sm: 6 }}>
          <form.Field name="processor.tracker">
            {(field) => (
              <TextField
                fullWidth
                value={field.state.value ?? ''}
                onChange={(e) => field.handleChange(e.target.value)}
                label={t('settings.objectTracker')}
              />
            )}
          </form.Field>
        </Grid>
        <Grid size={{ xs: 12, sm: 6 }}>
          <form.Field name="processor.save_dataset_crops">
            {(field) => (
              <FormControl fullWidth>
                <FormControlLabel
                  control={
                    <Checkbox
                      checked={!!field.state.value}
                      onChange={(e) => field.handleChange(e.target.checked)}
                    />
                  }
                  label={t('settings.saveDatasetCrops')}
                />
                <FormHelperText>
                  {t('settings.saveDatasetCropsHelp')}
                </FormHelperText>
              </FormControl>
            )}
          </form.Field>
        </Grid>
      </Grid>
    </ServiceBlock>
  );
}
