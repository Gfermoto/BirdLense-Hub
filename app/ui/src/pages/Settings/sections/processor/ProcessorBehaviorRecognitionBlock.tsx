import { useTranslation } from 'react-i18next';
import type { ReactFormExtendedApi } from '@tanstack/react-form';
import Grid from '@mui/material/Grid2';
import MenuItem from '@mui/material/MenuItem';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';
import Switch from '@mui/material/Switch';
import FormControlLabel from '@mui/material/FormControlLabel';
import FormHelperText from '@mui/material/FormHelperText';
import Alert from '@mui/material/Alert';
import Link from '@mui/material/Link';
import { Link as RouterLink } from 'react-router-dom';
import { ServiceBlock } from '../../shared/ServiceBlock';
import type { Settings } from '../../../../types';

const BEHAVIOR_README_RU =
  'https://github.com/Gfermoto/BirdLense-Hub/blob/dev/README.ru.md';

type Props = {
  form: ReactFormExtendedApi<Settings, undefined>;
};

export function ProcessorBehaviorRecognitionBlock({ form }: Props) {
  const { t } = useTranslation();

  return (
    <ServiceBlock title={t('settings.processorBehaviorTitle')}>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        {t('settings.processorBehaviorDesc')}
      </Typography>
      <Alert severity="info" variant="outlined" sx={{ mb: 2 }}>
        {t('settings.processorBehaviorBundledWeights')}
      </Alert>
      <Alert severity="warning" variant="outlined" sx={{ mb: 2 }}>
        {t('settings.processorBehaviorNoDatasetUi')}{' '}
        <Link component={RouterLink} to="/system#behavior-baseline-retrain">
          {t('settings.processorBehaviorSystemRetrainLink')}
        </Link>
        {' · '}
        <Link href={BEHAVIOR_README_RU} target="_blank" rel="noopener noreferrer">
          {t('settings.processorBehaviorReadmeLink')}
        </Link>
      </Alert>
      <Grid container spacing={2}>
        <Grid size={{ xs: 12 }}>
          <form.Field name="processor.behavior_recognition.enabled">
            {(field) => (
              <FormControlLabel
                control={
                  <Switch
                    checked={Boolean(field.state.value)}
                    onChange={(e) => field.handleChange(e.target.checked)}
                  />
                }
                label={t('settings.processorBehaviorEnabled')}
              />
            )}
          </form.Field>
          <FormHelperText sx={{ ml: 0, mt: 0.5 }}>
            {t('settings.processorBehaviorEnabledHint')}
          </FormHelperText>
        </Grid>
        <Grid size={{ xs: 12 }}>
          <form.Field name="processor.behavior_recognition.weights_path">
            {(field) => (
              <TextField
                fullWidth
                value={field.state.value ?? ''}
                onChange={(e) => field.handleChange(e.target.value)}
                label={t('settings.processorBehaviorWeightsPath')}
                helperText={t('settings.processorBehaviorWeightsPathHint')}
              />
            )}
          </form.Field>
        </Grid>
        <Grid size={{ xs: 12 }}>
          <form.Field name="processor.behavior_recognition.inference_backend">
            {(field) => (
              <TextField
                select
                fullWidth
                value={field.state.value ?? 'auto'}
                onChange={(e) => field.handleChange(e.target.value)}
                label={t('settings.processorBehaviorInferenceBackend')}
                helperText={t('settings.processorBehaviorInferenceBackendHint')}
              >
                <MenuItem value="auto">{t('settings.processorBehaviorInferenceAuto')}</MenuItem>
                <MenuItem value="logistic_json">{t('settings.processorBehaviorInferenceLogisticJson')}</MenuItem>
                <MenuItem value="openvino">{t('settings.processorBehaviorInferenceOpenvino')}</MenuItem>
              </TextField>
            )}
          </form.Field>
        </Grid>
        <Grid size={{ xs: 12 }}>
          <form.Field name="processor.behavior_recognition.openvino_fallback_logistic">
            {(field) => (
              <FormControlLabel
                control={
                  <Switch
                    checked={Boolean(field.state.value ?? true)}
                    onChange={(e) => field.handleChange(e.target.checked)}
                  />
                }
                label={t('settings.processorBehaviorOpenvinoFallback')}
              />
            )}
          </form.Field>
          <FormHelperText sx={{ ml: 0, mt: 0.5 }}>
            {t('settings.processorBehaviorOpenvinoFallbackHint')}
          </FormHelperText>
        </Grid>
        <Grid size={{ xs: 12, sm: 6 }}>
          <form.Field name="processor.behavior_recognition.max_runtime_detections">
            {(field) => (
              <TextField
                fullWidth
                type="number"
                inputProps={{ min: 1, max: 500, step: 1 }}
                value={field.state.value ?? 50}
                onChange={(e) => {
                  const v = Number(e.target.value);
                  field.handleChange(Number.isFinite(v) ? Math.round(v) : 50);
                }}
                label={t('settings.processorBehaviorMaxRuntimeDets')}
                helperText={t('settings.processorBehaviorMaxRuntimeDetsHint')}
              />
            )}
          </form.Field>
        </Grid>
        <Grid size={{ xs: 12, sm: 6 }}>
          <form.Field name="processor.behavior_recognition.confidence_store_min">
            {(field) => (
              <TextField
                fullWidth
                type="number"
                inputProps={{ min: 0, max: 1, step: 0.05 }}
                value={field.state.value ?? 0.2}
                onChange={(e) => {
                  const v = Number(e.target.value);
                  field.handleChange(Number.isFinite(v) ? v : 0.2);
                }}
                label={t('settings.processorBehaviorStoreMin')}
                helperText={t('settings.processorBehaviorStoreMinHint')}
              />
            )}
          </form.Field>
        </Grid>
        <Grid size={{ xs: 12, sm: 6 }}>
          <form.Field name="processor.behavior_recognition.confidence_review_threshold">
            {(field) => (
              <TextField
                fullWidth
                type="number"
                inputProps={{ min: 0, max: 1, step: 0.05 }}
                value={field.state.value ?? 0.45}
                onChange={(e) => {
                  const v = Number(e.target.value);
                  field.handleChange(Number.isFinite(v) ? v : 0.45);
                }}
                label={t('settings.processorBehaviorReviewThreshold')}
                helperText={t('settings.processorBehaviorReviewThresholdHint')}
              />
            )}
          </form.Field>
        </Grid>
      </Grid>
    </ServiceBlock>
  );
}
