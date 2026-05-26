import { useTranslation } from 'react-i18next';
import type { ReactFormExtendedApi } from '@tanstack/react-form';
import Grid from '@mui/material/Grid2';
import Switch from '@mui/material/Switch';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';
import FormControlLabel from '@mui/material/FormControlLabel';
import FormHelperText from '@mui/material/FormHelperText';
import { ServiceBlock } from '../../shared/ServiceBlock';
import { ProcessorNumberField } from '../../shared/ProcessorNumberField';
import {
  INFERENCE_LORES_WH_DEFAULT,
  whPairOrDefault,
} from '../../shared/processorFieldDefaults';
import type { Settings } from '../../../../types';

type Props = {
  form: ReactFormExtendedApi<Settings, undefined>;
};

export function ProcessorStreamGeometryBlock({ form }: Props) {
  const { t } = useTranslation();

  return (
    <ServiceBlock title={t('settings.processorStreamGeometryTitle')}>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        {t('settings.processorStreamGeometryDesc')}
      </Typography>
      <Grid container spacing={2}>
        <Grid size={{ xs: 12 }}>
          <form.Field name="processor.detect_use_native_resolution">
            {(field) => (
              <FormControlLabel
                control={
                  <Switch
                    checked={field.state.value ?? false}
                    onChange={(e) => field.handleChange(e.target.checked)}
                  />
                }
                label={t('settings.processorDetectUseNativeResolution')}
              />
            )}
          </form.Field>
          <FormHelperText sx={{ ml: 0, mt: 0.5 }}>
            {t('settings.processorDetectUseNativeResolutionHint')}
          </FormHelperText>
        </Grid>
        <Grid size={{ xs: 12, sm: 6 }}>
          <form.Field name="processor.inference_lores_wh">
            {(field) => {
              const [w, h] = whPairOrDefault(
                field.state.value,
                INFERENCE_LORES_WH_DEFAULT,
              );
              return (
                <TextField
                  fullWidth
                  type="number"
                  inputProps={{ min: 320, max: 1920, step: 1 }}
                  label={t('settings.processorInferenceLoresWidth')}
                  value={w}
                  onChange={(e) => {
                    const nw = Number(e.target.value) || w;
                    field.handleChange([nw, h]);
                  }}
                  helperText={t('settings.processorInferenceLoresWhHint')}
                />
              );
            }}
          </form.Field>
        </Grid>
        <Grid size={{ xs: 12, sm: 6 }}>
          <form.Field name="processor.inference_lores_wh">
            {(field) => {
              const [w, h] = whPairOrDefault(
                field.state.value,
                INFERENCE_LORES_WH_DEFAULT,
              );
              return (
                <TextField
                  fullWidth
                  type="number"
                  inputProps={{ min: 240, max: 1080, step: 1 }}
                  label={t('settings.processorInferenceLoresHeight')}
                  value={h}
                  onChange={(e) => {
                    const nh = Number(e.target.value) || h;
                    field.handleChange([w, nh]);
                  }}
                />
              );
            }}
          </form.Field>
        </Grid>
        <Grid size={{ xs: 12, sm: 6 }}>
          <form.Field name="processor.detection_quality_assumed_fps">
            {(field) => (
              <ProcessorNumberField
                defaultKey="detection_quality_assumed_fps"
                value={field.state.value}
                onValueChange={(n) => field.handleChange(n)}
                inputProps={{ min: 1, max: 60, step: 0.5 }}
                label={t('settings.processorDetectionQualityAssumedFps')}
                helperText={t('settings.processorDetectionQualityAssumedFpsHint')}
              />
            )}
          </form.Field>
        </Grid>
      </Grid>
    </ServiceBlock>
  );
}
