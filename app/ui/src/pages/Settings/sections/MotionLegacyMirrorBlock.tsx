import { useTranslation } from 'react-i18next';
import type { ReactFormExtendedApi } from '@tanstack/react-form';
import FormControl from '@mui/material/FormControl';
import FormControlLabel from '@mui/material/FormControlLabel';
import FormHelperText from '@mui/material/FormHelperText';
import Grid from '@mui/material/Grid2';
import InputLabel from '@mui/material/InputLabel';
import MenuItem from '@mui/material/MenuItem';
import Select from '@mui/material/Select';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';
import { ServiceBlock } from '../shared/ServiceBlock';
import type { Settings } from '../../../types';

type Props = {
  form: ReactFormExtendedApi<Settings, undefined>;
};

type MotionSource = NonNullable<NonNullable<Settings['motion']>['source']>;

/** Ключи motion.* в YAML — fallback рядом с triggers.* (см. default_config). */
export function MotionLegacyMirrorBlock({ form }: Props) {
  const { t } = useTranslation();

  return (
    <ServiceBlock title={t('settings.motionLegacyTitle')}>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        {t('settings.motionLegacyDesc')}
      </Typography>
      <Grid container spacing={2}>
        <Grid size={{ xs: 12, sm: 6 }}>
          <form.Field name="motion.source">
            {(field) => (
              <FormControl fullWidth>
                <InputLabel id="motion-legacy-src">
                  {t('settings.motionLegacySource')}
                </InputLabel>
                <Select
                  labelId="motion-legacy-src"
                  value={(field.state.value ?? 'opencv') as MotionSource}
                  label={t('settings.motionLegacySource')}
                  onChange={(e) =>
                    field.handleChange(e.target.value as MotionSource)
                  }
                >
                  <MenuItem value="opencv">opencv</MenuItem>
                  <MenuItem value="frigate">frigate</MenuItem>
                  <MenuItem value="mqtt">mqtt</MenuItem>
                  <MenuItem value="esphome">esphome</MenuItem>
                </Select>
                <FormHelperText>
                  {t('settings.motionLegacySourceHint')}
                </FormHelperText>
              </FormControl>
            )}
          </form.Field>
        </Grid>
        <Grid size={{ xs: 12, sm: 6 }}>
          <form.Field name="motion.check_every_n_frames">
            {(field) => (
              <TextField
                fullWidth
                type="number"
                inputProps={{ min: 1, max: 30, step: 1 }}
                value={field.state.value ?? 1}
                onChange={(e) =>
                  field.handleChange(Number(e.target.value) || 1)
                }
                label={t('settings.motionLegacyCheckEveryN')}
                helperText={t('settings.motionLegacyCheckEveryNHint')}
              />
            )}
          </form.Field>
        </Grid>
        <Grid size={{ xs: 12, sm: 6 }}>
          <form.Field name="motion.opencv_diff_threshold">
            {(field) => (
              <TextField
                fullWidth
                type="number"
                inputProps={{ min: 1, max: 255, step: 1 }}
                value={field.state.value ?? 18}
                onChange={(e) =>
                  field.handleChange(Number(e.target.value) || 18)
                }
                label={t('settings.motionLegacyOpencvDiff')}
                helperText={t('settings.motionLegacyOpencvDiffHint')}
              />
            )}
          </form.Field>
        </Grid>
        <Grid size={{ xs: 12, sm: 6 }}>
          <form.Field name="motion.opencv_min_contour_area">
            {(field) => (
              <TextField
                fullWidth
                type="number"
                inputProps={{ min: 1, max: 20000, step: 1 }}
                value={field.state.value ?? 240}
                onChange={(e) =>
                  field.handleChange(Number(e.target.value) || 240)
                }
                label={t('settings.motionLegacyOpencvMinArea')}
                helperText={t('settings.motionLegacyOpencvMinAreaHint')}
              />
            )}
          </form.Field>
        </Grid>
        <Grid size={{ xs: 12, sm: 6 }}>
          <form.Field name="motion.frigate_min_trigger_score">
            {(field) => (
              <TextField
                fullWidth
                type="number"
                inputProps={{ min: 0, max: 1, step: 0.05 }}
                value={field.state.value ?? 0.5}
                onChange={(e) =>
                  field.handleChange(Number(e.target.value) || 0)
                }
                label={t('settings.motionLegacyFrigateMinScore')}
                helperText={t('settings.motionLegacyFrigateMinScoreHint')}
              />
            )}
          </form.Field>
        </Grid>
        <Grid size={{ xs: 12, sm: 6 }}>
          <form.Field name="motion.mqtt_topic">
            {(field) => (
              <TextField
                fullWidth
                value={field.state.value ?? ''}
                onChange={(e) => field.handleChange(e.target.value)}
                label={t('settings.motionLegacyMqttTopic')}
                helperText={t('settings.motionLegacyMqttTopicHint')}
              />
            )}
          </form.Field>
        </Grid>
        <Grid size={{ xs: 12, sm: 6 }}>
          <form.Field name="motion.esphome_url">
            {(field) => (
              <TextField
                fullWidth
                value={field.state.value ?? ''}
                onChange={(e) => field.handleChange(e.target.value)}
                label={t('settings.motionLegacyEsphomeUrl')}
              />
            )}
          </form.Field>
        </Grid>
        <Grid size={{ xs: 12, sm: 6 }}>
          <form.Field name="motion.esphome_sensor_id">
            {(field) => (
              <TextField
                fullWidth
                value={field.state.value ?? ''}
                onChange={(e) => field.handleChange(e.target.value)}
                label={t('settings.motionLegacyEsphomeSensor')}
                helperText={t('settings.motionLegacyEsphomeSensorHint')}
              />
            )}
          </form.Field>
        </Grid>
      </Grid>
    </ServiceBlock>
  );
}
