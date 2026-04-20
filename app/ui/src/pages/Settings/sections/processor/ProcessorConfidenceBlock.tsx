import { useTranslation } from 'react-i18next';
import type { ReactFormExtendedApi } from '@tanstack/react-form';
import Grid from '@mui/material/Grid2';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';
import { ServiceBlock } from '../../shared/ServiceBlock';
import type { Settings } from '../../../../types';

type Props = {
  form: ReactFormExtendedApi<Settings, undefined>;
};

export function ProcessorConfidenceBlock({ form }: Props) {
  const { t } = useTranslation();

  return (
    <ServiceBlock title={t('settings.confidenceThresholdsTitle')}>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        {t('settings.confidenceThresholdsDesc')}
      </Typography>
      <Grid container spacing={2}>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <form.Field name="processor.min_confidence_binary">
            {(field) => (
              <TextField
                fullWidth
                type="number"
                inputProps={{ min: 0.05, max: 0.9, step: 0.05 }}
                value={field.state.value ?? 0.22}
                onChange={(e) =>
                  field.handleChange(Number(e.target.value) || undefined)
                }
                label={t('settings.confidenceDetector')}
                helperText={t('settings.confidenceDetectorHelp')}
              />
            )}
          </form.Field>
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <form.Field name="processor.min_confidence_to_process">
            {(field) => (
              <TextField
                fullWidth
                type="number"
                inputProps={{ min: 0, max: 1, step: 0.05 }}
                value={field.state.value ?? 0.3}
                onChange={(e) =>
                  field.handleChange(Number(e.target.value) || undefined)
                }
                label={t('settings.confidenceClassifier')}
                helperText={t('settings.confidenceClassifierHelp')}
              />
            )}
          </form.Field>
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <form.Field name="processor.min_confidence_to_notify">
            {(field) => (
              <TextField
                fullWidth
                type="number"
                inputProps={{ min: 0, max: 1, step: 0.05 }}
                value={field.state.value ?? 0.44}
                onChange={(e) =>
                  field.handleChange(Number(e.target.value) || undefined)
                }
                label={t('settings.confidenceTelegram')}
                helperText={t('settings.confidenceTelegramHelp')}
              />
            )}
          </form.Field>
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <form.Field name="processor.dataset_min_confidence">
            {(field) => (
              <TextField
                fullWidth
                type="number"
                inputProps={{ min: 0, max: 1, step: 0.05 }}
                value={field.state.value ?? 0.5}
                onChange={(e) =>
                  field.handleChange(Number(e.target.value) || undefined)
                }
                label={t('settings.confidenceDataset')}
                helperText={t('settings.confidenceDatasetHelp')}
              />
            )}
          </form.Field>
        </Grid>
        <Grid size={{ xs: 12 }}>
          <Typography variant="subtitle2" sx={{ mt: 1, mb: 0.5 }}>
            {t('settings.yoloSplitThresholdsTitle')}
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
            {t('settings.yoloSplitThresholdsDesc')}
          </Typography>
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 4 }}>
          <form.Field name="processor.min_confidence_binary_bird">
            {(field) => (
              <TextField
                fullWidth
                type="number"
                inputProps={{ min: 0.05, max: 0.95, step: 0.01 }}
                value={
                  field.state.value === undefined || field.state.value === null
                    ? ''
                    : field.state.value
                }
                onChange={(e) => {
                  const raw = e.target.value.trim();
                  if (raw === '') {
                    field.handleChange(null);
                    return;
                  }
                  const n = Number(raw);
                  if (Number.isFinite(n)) {
                    field.handleChange(n);
                  }
                }}
                label={t('settings.confidenceBinaryBird')}
                helperText={t('settings.confidenceBinaryBirdHelp')}
              />
            )}
          </form.Field>
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 4 }}>
          <form.Field name="processor.min_confidence_binary_rodent">
            {(field) => (
              <TextField
                fullWidth
                type="number"
                inputProps={{ min: 0.05, max: 0.95, step: 0.01 }}
                value={
                  field.state.value === undefined || field.state.value === null
                    ? ''
                    : field.state.value
                }
                onChange={(e) => {
                  const raw = e.target.value.trim();
                  if (raw === '') {
                    field.handleChange(null);
                    return;
                  }
                  const n = Number(raw);
                  if (Number.isFinite(n)) {
                    field.handleChange(n);
                  }
                }}
                label={t('settings.confidenceBinaryRodent')}
                helperText={t('settings.confidenceBinaryRodentHelp')}
              />
            )}
          </form.Field>
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 4 }}>
          <form.Field name="processor.bird_skip_classifier_max_area_frac">
            {(field) => (
              <TextField
                fullWidth
                type="number"
                inputProps={{ min: 0, max: 0.5, step: 0.001 }}
                value={
                  field.state.value === undefined || field.state.value === null
                    ? ''
                    : field.state.value
                }
                onChange={(e) => {
                  const raw = e.target.value.trim();
                  if (raw === '') {
                    field.handleChange(null);
                    return;
                  }
                  const n = Number(raw);
                  if (Number.isFinite(n)) {
                    field.handleChange(n);
                  }
                }}
                label={t('settings.birdSkipClassifierArea')}
                helperText={t('settings.birdSkipClassifierAreaHelp')}
              />
            )}
          </form.Field>
        </Grid>
      </Grid>
    </ServiceBlock>
  );
}
