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

export function ProcessorScoringBlock({ form }: Props) {
  const { t } = useTranslation();

  return (
    <ServiceBlock title={t('settings.processorScoringTitle')}>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        {t('settings.processorScoringDesc')}
      </Typography>
      <Grid container spacing={2}>
        <Grid size={{ xs: 12, sm: 6, md: 4 }}>
          <form.Field name="processor.scoring_default_low_threshold">
            {(field) => (
              <ProcessorNumberField
                defaultKey="scoring_default_low_threshold"
                value={field.state.value}
                onValueChange={(n) => field.handleChange(n)}
                inputProps={{ min: 0.02, max: 0.6, step: 0.01 }}
                label={t('settings.processorScoringDefaultLowThreshold')}
                helperText={t('settings.processorScoringDefaultLowThresholdHint')}
              />
            )}
          </form.Field>
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 4 }}>
          <form.Field name="processor.scoring_default_high_threshold">
            {(field) => (
              <ProcessorNumberField
                defaultKey="scoring_default_high_threshold"
                value={field.state.value}
                onValueChange={(n) => field.handleChange(n)}
                inputProps={{ min: 0.1, max: 0.95, step: 0.01 }}
                label={t('settings.processorScoringDefaultHighThreshold')}
                helperText={t('settings.processorScoringDefaultHighThresholdHint')}
              />
            )}
          </form.Field>
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 4 }}>
          <form.Field name="processor.scoring_relaxed_min_confidence">
            {(field) => (
              <ProcessorNumberField
                defaultKey="scoring_relaxed_min_confidence"
                value={field.state.value}
                onValueChange={(n) => field.handleChange(n)}
                inputProps={{ min: 0.01, max: 0.3, step: 0.01 }}
                label={t('settings.processorScoringRelaxedMinConfidence')}
                helperText={t('settings.processorScoringRelaxedMinConfidenceHint')}
              />
            )}
          </form.Field>
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 4 }}>
          <form.Field name="processor.scoring_frigate_prior_boost">
            {(field) => (
              <ProcessorNumberField
                defaultKey="scoring_frigate_prior_boost"
                value={field.state.value}
                onValueChange={(n) => field.handleChange(n)}
                inputProps={{ min: 0, max: 0.5, step: 0.01 }}
                label={t('settings.processorScoringFrigatePriorBoost')}
                helperText={t('settings.processorScoringFrigatePriorBoostHint')}
              />
            )}
          </form.Field>
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 4 }}>
          <form.Field name="processor.scoring_moving_roi_min_motion_score">
            {(field) => (
              <ProcessorNumberField
                defaultKey="scoring_moving_roi_min_motion_score"
                value={field.state.value}
                onValueChange={(n) => field.handleChange(n)}
                inputProps={{ min: 0.05, max: 0.6, step: 0.01 }}
                label={t('settings.processorScoringMovingRoiMinMotionScore')}
                helperText={t('settings.processorScoringMovingRoiMinMotionScoreHint')}
              />
            )}
          </form.Field>
        </Grid>
      </Grid>
    </ServiceBlock>
  );
}
