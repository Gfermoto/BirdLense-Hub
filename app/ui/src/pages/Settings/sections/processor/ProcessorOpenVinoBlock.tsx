import { useTranslation } from 'react-i18next';
import type { ReactFormExtendedApi } from '@tanstack/react-form';
import Grid from '@mui/material/Grid2';
import Typography from '@mui/material/Typography';
import { ServiceBlock } from '../../shared/ServiceBlock';
import { ProcessorNumberField } from '../../shared/ProcessorNumberField';
import type { Settings } from '../../../../types';

type Props = {
  form: ReactFormExtendedApi<Settings, undefined>;
};

export function ProcessorOpenVinoBlock({ form }: Props) {
  const { t } = useTranslation();

  return (
    <ServiceBlock title={t('settings.processorOpenVinoTitle')}>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        {t('settings.processorOpenVinoDesc')}
      </Typography>
      <Grid container spacing={2}>
        <Grid size={{ xs: 12, sm: 4 }}>
          <form.Field name="processor.openvino_binary_track_ultralytics_conf">
            {(field) => (
              <ProcessorNumberField
                defaultKey="openvino_binary_track_ultralytics_conf"
                value={field.state.value ?? undefined}
                onValueChange={(n) => field.handleChange(n)}
                inputProps={{ min: 0.05, max: 0.95, step: 0.01 }}
                label={t('settings.processorOpenvinoTrackConf')}
                helperText={t('settings.processorOpenvinoTrackConfHint')}
              />
            )}
          </form.Field>
        </Grid>
        <Grid size={{ xs: 12, sm: 4 }}>
          <form.Field name="processor.openvino_binary_bird_score_scale">
            {(field) => (
              <ProcessorNumberField
                defaultKey="openvino_binary_bird_score_scale"
                value={field.state.value ?? undefined}
                onValueChange={(n) => field.handleChange(n)}
                inputProps={{ min: 0.5, max: 12, step: 0.1 }}
                label={t('settings.processorOpenvinoBirdScoreScale')}
                helperText={t('settings.processorOpenvinoBirdScoreScaleHint')}
              />
            )}
          </form.Field>
        </Grid>
        <Grid size={{ xs: 12, sm: 4 }}>
          <form.Field name="processor.openvino_min_confidence_binary_bird">
            {(field) => (
              <ProcessorNumberField
                defaultKey="openvino_min_confidence_binary_bird"
                value={field.state.value ?? undefined}
                onValueChange={(n) => field.handleChange(n)}
                inputProps={{ min: 0.05, max: 0.95, step: 0.01 }}
                label={t('settings.processorOpenvinoMinConfBird')}
                helperText={t('settings.processorOpenvinoMinConfBirdHint')}
              />
            )}
          </form.Field>
        </Grid>
      </Grid>
    </ServiceBlock>
  );
}
