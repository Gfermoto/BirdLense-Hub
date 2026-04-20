import { useTranslation } from 'react-i18next';
import type { ReactFormExtendedApi } from '@tanstack/react-form';
import Grid from '@mui/material/Grid2';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';
import MenuItem from '@mui/material/MenuItem';
import FormControl from '@mui/material/FormControl';
import InputLabel from '@mui/material/InputLabel';
import Select from '@mui/material/Select';
import { ServiceBlock } from '../../shared/ServiceBlock';
import type { Settings } from '../../../../types';

type Props = {
  form: ReactFormExtendedApi<Settings, undefined>;
};

export function ProcessorDetectorPipelineBlock({ form }: Props) {
  const { t } = useTranslation();

  return (
    <ServiceBlock title={t('settings.processorDetectorPipelineTitle')}>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        {t('settings.processorDetectorPipelineDesc')}
      </Typography>
      <Grid container spacing={2}>
        <Grid size={{ xs: 12, sm: 6 }}>
          <form.Field name="processor.binary_imgsz">
            {(field) => (
              <TextField
                fullWidth
                type="number"
                inputProps={{ min: 320, max: 1280, step: 32 }}
                value={field.state.value ?? 640}
                onChange={(e) =>
                  field.handleChange(Number(e.target.value) || 640)
                }
                label={t('settings.processorBinaryImgsz')}
                helperText={t('settings.processorBinaryImgszHint')}
              />
            )}
          </form.Field>
        </Grid>
        <Grid size={{ xs: 12, sm: 6 }}>
          <form.Field name="processor.inference_lores_px">
            {(field) => (
              <TextField
                fullWidth
                type="number"
                inputProps={{ min: 320, max: 1280, step: 32 }}
                value={field.state.value ?? 640}
                onChange={(e) =>
                  field.handleChange(Number(e.target.value) || 640)
                }
                label={t('settings.processorInferenceLoresPx')}
                helperText={t('settings.processorInferenceLoresPxHint')}
              />
            )}
          </form.Field>
        </Grid>
        <Grid size={{ xs: 12, sm: 6 }}>
          <form.Field name="processor.frame_processing_warn_ms">
            {(field) => (
              <TextField
                fullWidth
                type="number"
                inputProps={{ min: 50, max: 5000, step: 50 }}
                value={field.state.value ?? 450}
                onChange={(e) =>
                  field.handleChange(Number(e.target.value) || 450)
                }
                label={t('settings.processorFrameProcessingWarnMs')}
                helperText={t('settings.processorFrameProcessingWarnMsHint')}
              />
            )}
          </form.Field>
        </Grid>
        <Grid size={{ xs: 12, sm: 6 }}>
          <form.Field name="processor.classification_scheduler">
            {(field) => (
              <FormControl fullWidth>
                <InputLabel id="proc-class-sched-label">
                  {t('settings.processorClassificationScheduler')}
                </InputLabel>
                <Select
                  labelId="proc-class-sched-label"
                  label={t('settings.processorClassificationScheduler')}
                  value={field.state.value ?? 'priority'}
                  onChange={(e) =>
                    field.handleChange(String(e.target.value))
                  }
                >
                  <MenuItem value="priority">
                    {t('settings.processorClassificationSchedulerPriority')}
                  </MenuItem>
                  <MenuItem value="round_robin">
                    {t('settings.processorClassificationSchedulerRoundRobin')}
                  </MenuItem>
                </Select>
              </FormControl>
            )}
          </form.Field>
        </Grid>
        <Grid size={{ xs: 12, sm: 6 }}>
          <form.Field name="processor.max_classifications_per_frame">
            {(field) => (
              <TextField
                fullWidth
                type="number"
                inputProps={{ min: 1, max: 16, step: 1 }}
                value={field.state.value ?? 3}
                onChange={(e) =>
                  field.handleChange(Number(e.target.value) || 1)
                }
                label={t('settings.processorMaxClassificationsPerFrame')}
                helperText={t('settings.processorMaxClassificationsPerFrameHint')}
              />
            )}
          </form.Field>
        </Grid>
        <Grid size={{ xs: 12, sm: 6 }}>
          <form.Field name="processor.max_blur_checks">
            {(field) => (
              <TextField
                fullWidth
                type="number"
                inputProps={{ min: 1, max: 20, step: 1 }}
                value={field.state.value ?? 3}
                onChange={(e) =>
                  field.handleChange(Number(e.target.value) || 1)
                }
                label={t('settings.processorMaxBlurChecks')}
                helperText={t('settings.processorMaxBlurChecksHint')}
              />
            )}
          </form.Field>
        </Grid>
        <Grid size={{ xs: 12, sm: 6 }}>
          <form.Field name="processor.blur_threshold">
            {(field) => (
              <TextField
                fullWidth
                type="number"
                inputProps={{ min: 1, max: 500, step: 1 }}
                value={field.state.value ?? 100}
                onChange={(e) =>
                  field.handleChange(Number(e.target.value) || 100)
                }
                label={t('settings.processorBlurThreshold')}
                helperText={t('settings.processorBlurThresholdHint')}
              />
            )}
          </form.Field>
        </Grid>
        <Grid size={{ xs: 12, sm: 6 }}>
          <form.Field name="processor.min_center_dist">
            {(field) => (
              <TextField
                fullWidth
                type="number"
                inputProps={{ min: 0.01, max: 0.25, step: 0.005 }}
                value={field.state.value ?? 0.035}
                onChange={(e) =>
                  field.handleChange(Number(e.target.value) || 0.035)
                }
                label={t('settings.processorMinCenterDist')}
                helperText={t('settings.processorMinCenterDistHint')}
              />
            )}
          </form.Field>
        </Grid>
      </Grid>
    </ServiceBlock>
  );
}
