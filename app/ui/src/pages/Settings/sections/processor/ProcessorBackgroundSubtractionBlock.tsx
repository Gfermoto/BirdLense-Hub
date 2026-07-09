import { useTranslation } from 'react-i18next';
import type { ReactFormExtendedApi } from '@tanstack/react-form';
import Grid from '@mui/material/Grid2';
import Switch from '@mui/material/Switch';
import Typography from '@mui/material/Typography';
import FormControlLabel from '@mui/material/FormControlLabel';
import FormHelperText from '@mui/material/FormHelperText';
import { ServiceBlock } from '../../shared/ServiceBlock';
import { ProcessorNumberField } from '../../shared/ProcessorNumberField';
import type { Settings } from '../../../../types';

type Props = {
  form: ReactFormExtendedApi<Settings, undefined>;
};

export function ProcessorBackgroundSubtractionBlock({ form }: Props) {
  const { t } = useTranslation();

  return (
    <ServiceBlock title={t('settings.processorMog2Title')}>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        {t('settings.processorMog2Desc')}
      </Typography>
      <Grid container spacing={2}>
        <Grid size={{ xs: 12 }}>
          <form.Field name="processor.background_subtraction_enabled">
            {(field) => (
              <FormControlLabel
                control={
                  <Switch
                    checked={field.state.value !== false}
                    onChange={(e) => field.handleChange(e.target.checked)}
                  />
                }
                label={t('settings.processorMog2Enabled')}
              />
            )}
          </form.Field>
          <FormHelperText sx={{ ml: 0, mt: 0.5 }}>
            {t('settings.processorMog2EnabledHint')}
          </FormHelperText>
        </Grid>
        <Grid size={{ xs: 12, sm: 6 }}>
          <form.Field name="processor.background_subtraction_history">
            {(field) => (
              <ProcessorNumberField
                defaultKey="background_subtraction_history"
                value={field.state.value}
                onValueChange={(n) => field.handleChange(n)}
                inputProps={{ min: 50, max: 2000, step: 10 }}
                label={t('settings.processorMog2History')}
                helperText={t('settings.processorMog2HistoryHint')}
              />
            )}
          </form.Field>
        </Grid>
        <Grid size={{ xs: 12, sm: 6 }}>
          <form.Field name="processor.background_subtraction_var_threshold">
            {(field) => (
              <ProcessorNumberField
                defaultKey="background_subtraction_var_threshold"
                value={field.state.value}
                onValueChange={(n) => field.handleChange(n)}
                inputProps={{ min: 4, max: 64, step: 1 }}
                label={t('settings.processorMog2VarThreshold')}
                helperText={t('settings.processorMog2VarThresholdHint')}
              />
            )}
          </form.Field>
        </Grid>
        <Grid size={{ xs: 12, sm: 6 }}>
          <form.Field name="processor.background_subtraction_min_fg_ratio">
            {(field) => (
              <ProcessorNumberField
                defaultKey="background_subtraction_min_fg_ratio"
                value={field.state.value}
                onValueChange={(n) => field.handleChange(n)}
                inputProps={{ min: 0.01, max: 0.5, step: 0.01 }}
                label={t('settings.processorMog2MinFgRatio')}
                helperText={t('settings.processorMog2MinFgRatioHint')}
              />
            )}
          </form.Field>
        </Grid>
        <Grid size={{ xs: 12, sm: 6 }}>
          <form.Field name="processor.background_subtraction_warmup_frames">
            {(field) => (
              <ProcessorNumberField
                defaultKey="background_subtraction_warmup_frames"
                value={field.state.value}
                onValueChange={(n) => field.handleChange(n)}
                inputProps={{ min: 5, max: 300, step: 1 }}
                label={t('settings.processorMog2WarmupFrames')}
                helperText={t('settings.processorMog2WarmupFramesHint')}
              />
            )}
          </form.Field>
        </Grid>
        <Grid size={{ xs: 12 }}>
          <form.Field name="processor.background_subtraction_detect_shadows">
            {(field) => (
              <FormControlLabel
                control={
                  <Switch
                    checked={field.state.value !== false}
                    onChange={(e) => field.handleChange(e.target.checked)}
                  />
                }
                label={t('settings.processorMog2DetectShadows')}
              />
            )}
          </form.Field>
        </Grid>
      </Grid>
    </ServiceBlock>
  );
}
