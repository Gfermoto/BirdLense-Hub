import { useTranslation } from 'react-i18next';
import type { ReactFormExtendedApi } from '@tanstack/react-form';
import Grid from '@mui/material/Grid2';
import Switch from '@mui/material/Switch';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';
import FormControlLabel from '@mui/material/FormControlLabel';
import FormHelperText from '@mui/material/FormHelperText';
import Alert from '@mui/material/Alert';
import Button from '@mui/material/Button';
import Stack from '@mui/material/Stack';
import Chip from '@mui/material/Chip';
import { ServiceBlock } from '../../shared/ServiceBlock';
import type { Settings } from '../../../../types';

type Props = {
  form: ReactFormExtendedApi<Settings, undefined>;
};

export function ProcessorModelsScopeBlock({ form }: Props) {
  const { t } = useTranslation();

  return (
    <ServiceBlock title={t('settings.processorModelsScopeTitle')}>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        {t('settings.processorModelsScopeDesc')}
      </Typography>
      <Grid container spacing={2}>
        <Grid size={{ xs: 12 }}>
          <form.Field name="processor.detection_strategy">
            {(field) => {
              const v = String(field.state.value ?? 'two_stage').trim() || 'two_stage';
              const isTwo = v === 'two_stage';
              return (
                <Stack spacing={1.5} sx={{ minWidth: 0 }}>
                  {!isTwo ? (
                    <Alert
                      severity="warning"
                      action={
                        <Button
                          color="inherit"
                          size="small"
                          onClick={() => field.handleChange('two_stage')}
                        >
                          {t('settings.processorCoerceTwoStage')}
                        </Button>
                      }
                    >
                      {t('settings.processorSingleStageWarning')}
                    </Alert>
                  ) : null}
                  <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap>
                    <Typography variant="body2" color="text.secondary" component="span">
                      {t('settings.processorDetectionStrategy')}:
                    </Typography>
                    <Chip
                      size="small"
                      color={isTwo ? 'success' : 'warning'}
                      label={v}
                      variant="outlined"
                    />
                    {!isTwo ? (
                      <Button
                        variant="outlined"
                        size="small"
                        onClick={() => field.handleChange('two_stage')}
                      >
                        {t('settings.processorCoerceTwoStage')}
                      </Button>
                    ) : null}
                  </Stack>
                  <Typography variant="body2" color="text.secondary">
                    {t('settings.processorDetectionStrategyTwoStageDesc')}
                  </Typography>
                </Stack>
              );
            }}
          </form.Field>
        </Grid>
        <Grid size={{ xs: 12 }}>
          <form.Field name="processor.models.binary">
            {(field) => (
              <TextField
                fullWidth
                value={field.state.value ?? ''}
                onChange={(e) => field.handleChange(e.target.value)}
                label={t('settings.processorModelBinaryPath')}
                helperText={t('settings.processorModelBinaryPathHint')}
              />
            )}
          </form.Field>
        </Grid>
        <Grid size={{ xs: 12 }}>
          <form.Field name="processor.models.classifier">
            {(field) => (
              <TextField
                fullWidth
                value={field.state.value ?? ''}
                onChange={(e) => field.handleChange(e.target.value)}
                label={t('settings.processorModelClassifierPath')}
                helperText={t('settings.processorModelClassifierPathHint')}
              />
            )}
          </form.Field>
        </Grid>
        <Grid size={{ xs: 12 }}>
          <form.Field name="processor.regional_species">
            {(field) => {
              const val = field.state.value;
              const str = Array.isArray(val)
                ? (val as string[]).map((s) => String(s).trim()).filter(Boolean).join('\n')
                : '';
              return (
                <TextField
                  fullWidth
                  multiline
                  minRows={3}
                  value={str}
                  onChange={(e) => {
                    const lines = e.target.value
                      .split('\n')
                      .map((s) => s.trim())
                      .filter(Boolean);
                    field.handleChange(lines);
                  }}
                  label={t('settings.processorRegionalSpecies')}
                  helperText={t('settings.processorRegionalSpeciesHint')}
                />
              );
            }}
          </form.Field>
        </Grid>
        <Grid size={{ xs: 12 }}>
          <form.Field name="processor.save_images">
            {(field) => (
              <FormControlLabel
                control={
                  <Switch
                    checked={field.state.value ?? false}
                    onChange={(e) => field.handleChange(e.target.checked)}
                  />
                }
                label={t('settings.processorSaveImages')}
              />
            )}
          </form.Field>
          <FormHelperText sx={{ ml: 0, mt: 0.5 }}>
            {t('settings.processorSaveImagesHint')}
          </FormHelperText>
        </Grid>
        <Typography variant="subtitle2" sx={{ width: '100%', px: 1, mt: 1 }}>
          {t('settings.processorGenericBirdHeading')}
        </Typography>
        <Grid size={{ xs: 12, sm: 6 }}>
          <form.Field name="processor.generic_bird_min_detector_conf">
            {(field) => (
              <TextField
                fullWidth
                type="number"
                inputProps={{ min: 0, max: 1, step: 0.02 }}
                value={field.state.value ?? 0.42}
                onChange={(e) =>
                  field.handleChange(Number(e.target.value) || 0.42)
                }
                label={t('settings.processorGenericBirdMinDetectorConf')}
                helperText={t(
                  'settings.processorGenericBirdMinDetectorConfHint',
                )}
              />
            )}
          </form.Field>
        </Grid>
        <Grid size={{ xs: 12, sm: 6 }}>
          <form.Field name="processor.generic_bird_min_frames">
            {(field) => (
              <TextField
                fullWidth
                type="number"
                inputProps={{ min: 1, max: 20, step: 1 }}
                value={field.state.value ?? 2}
                onChange={(e) =>
                  field.handleChange(Number(e.target.value) || 2)
                }
                label={t('settings.processorGenericBirdMinFrames')}
                helperText={t('settings.processorGenericBirdMinFramesHint')}
              />
            )}
          </form.Field>
        </Grid>
        <Grid size={{ xs: 12, sm: 6 }}>
          <form.Field name="processor.generic_bird_min_area_frac">
            {(field) => (
              <TextField
                fullWidth
                type="number"
                inputProps={{ min: 0.001, max: 0.2, step: 0.001 }}
                value={field.state.value ?? 0.008}
                onChange={(e) =>
                  field.handleChange(Number(e.target.value) || 0.008)
                }
                label={t('settings.processorGenericBirdMinAreaFrac')}
                helperText={t('settings.processorGenericBirdMinAreaFracHint')}
              />
            )}
          </form.Field>
        </Grid>
        <Grid size={{ xs: 12, sm: 6 }}>
          <form.Field name="processor.generic_bird_min_best_frame_score">
            {(field) => (
              <TextField
                fullWidth
                type="number"
                inputProps={{ min: 0, max: 50, step: 0.5 }}
                value={field.state.value ?? 6}
                onChange={(e) =>
                  field.handleChange(Number(e.target.value) || 6)
                }
                label={t('settings.processorGenericBirdMinBestFrameScore')}
                helperText={t(
                  'settings.processorGenericBirdMinBestFrameScoreHint',
                )}
              />
            )}
          </form.Field>
        </Grid>
        <Grid size={{ xs: 12, sm: 6 }}>
          <form.Field name="processor.key_frame_limit">
            {(field) => (
              <TextField
                fullWidth
                type="number"
                inputProps={{ min: 1, max: 20, step: 1 }}
                value={field.state.value ?? 3}
                onChange={(e) =>
                  field.handleChange(Number(e.target.value) || 3)
                }
                label={t('settings.processorKeyFrameLimit')}
                helperText={t('settings.processorKeyFrameLimitHint')}
              />
            )}
          </form.Field>
        </Grid>
        <Grid size={{ xs: 12 }}>
          <form.Field name="processor.keep_recording_when_no_detections">
            {(field) => (
              <FormControlLabel
                control={
                  <Switch
                    checked={field.state.value ?? false}
                    onChange={(e) => field.handleChange(e.target.checked)}
                  />
                }
                label={t('settings.processorKeepRecordingWhenNoDetections')}
              />
            )}
          </form.Field>
          <FormHelperText sx={{ ml: 0, mt: 0.5 }}>
            {t('settings.processorKeepRecordingWhenNoDetectionsHint')}
          </FormHelperText>
        </Grid>
      </Grid>
    </ServiceBlock>
  );
}
