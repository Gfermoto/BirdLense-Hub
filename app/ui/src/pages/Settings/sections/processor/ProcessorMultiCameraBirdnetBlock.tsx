import { useTranslation } from 'react-i18next';
import type { ReactFormExtendedApi } from '@tanstack/react-form';
import Grid from '@mui/material/Grid2';
import Switch from '@mui/material/Switch';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';
import FormControlLabel from '@mui/material/FormControlLabel';
import FormHelperText from '@mui/material/FormHelperText';
import { ServiceBlock } from '../../shared/ServiceBlock';
import type { Settings } from '../../../../types';

type Props = {
  form: ReactFormExtendedApi<Settings, undefined>;
};

export function ProcessorMultiCameraBirdnetBlock({ form }: Props) {
  const { t } = useTranslation();

  return (
    <ServiceBlock title={t('settings.processorMultiCameraBirdnetTitle')}>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        {t('settings.processorMultiCameraBirdnetDesc')}
      </Typography>
      <Grid container spacing={2}>
        <Grid size={{ xs: 12 }}>
          <form.Field name="processor.multi_camera_groups">
            {(field) => {
              const val = field.state.value;
              const str = Array.isArray(val)
                ? (val as string[][])
                    .map((g) =>
                      Array.isArray(g)
                        ? g
                            .map((s) => String(s).trim())
                            .filter(Boolean)
                            .join(', ')
                        : '',
                    )
                    .filter(Boolean)
                    .join('\n')
                : '';
              return (
                <TextField
                  fullWidth
                  multiline
                  minRows={3}
                  value={str}
                  onChange={(e) => {
                    const lines = e.target.value.split('\n');
                    const groups: string[][] = [];
                    for (const line of lines) {
                      const ids = line
                        .split(',')
                        .map((s) => s.trim())
                        .filter(Boolean);
                      if (ids.length) groups.push(ids);
                    }
                    field.handleChange(groups.length ? groups : []);
                  }}
                  label={t('settings.multiCameraGroups')}
                  placeholder={t('settings.multiCameraGroupsPlaceholder')}
                  helperText={t('settings.multiCameraGroupsHint')}
                />
              );
            }}
          </form.Field>
        </Grid>
        <Grid size={{ xs: 12, sm: 6 }}>
          <form.Field name="processor.multi_camera_confidence_boost">
            {(field) => (
              <TextField
                fullWidth
                type="number"
                inputProps={{ min: 0, max: 0.5, step: 0.01 }}
                value={field.state.value ?? 0.05}
                onChange={(e) =>
                  field.handleChange(Number(e.target.value) || 0.05)
                }
                label={t('settings.multiCameraConfidenceBoost')}
                helperText={t('settings.multiCameraConfidenceBoostHint')}
              />
            )}
          </form.Field>
        </Grid>
        <Grid size={{ xs: 12 }}>
          <form.Field name="processor.birdnet_mqtt_auto_confidence">
            {(field) => (
              <FormControlLabel
                control={
                  <Switch
                    checked={field.state.value ?? false}
                    onChange={(e) => field.handleChange(e.target.checked)}
                  />
                }
                label={t('settings.birdnetMqttAutoConfidence')}
              />
            )}
          </form.Field>
          <FormHelperText sx={{ ml: 0, mt: 0.5 }}>
            {t('settings.birdnetMqttAutoConfidenceHint')}
          </FormHelperText>
        </Grid>
        <form.Subscribe
          selector={(state) =>
            state.values.processor?.birdnet_mqtt_auto_confidence
          }
        >
          {(birdnetBias) =>
            birdnetBias ? (
              <>
                <Grid size={{ xs: 12, sm: 6 }}>
                  <form.Field name="processor.birdnet_mqtt_bias_delta">
                    {(field) => (
                      <TextField
                        fullWidth
                        type="number"
                        inputProps={{ min: 0, max: 0.5, step: 0.01 }}
                        value={field.state.value ?? 0.05}
                        onChange={(e) =>
                          field.handleChange(Number(e.target.value) || 0.05)
                        }
                        label={t('settings.birdnetMqttBiasDelta')}
                        helperText={t('settings.birdnetMqttBiasDeltaHint')}
                      />
                    )}
                  </form.Field>
                </Grid>
                <Grid size={{ xs: 12, sm: 6 }}>
                  <form.Field name="processor.birdnet_mqtt_bias_floor">
                    {(field) => (
                      <TextField
                        fullWidth
                        type="number"
                        inputProps={{ min: 0.01, max: 1, step: 0.01 }}
                        value={field.state.value ?? 0.05}
                        onChange={(e) =>
                          field.handleChange(Number(e.target.value) || 0.05)
                        }
                        label={t('settings.birdnetMqttBiasFloor')}
                        helperText={t('settings.birdnetMqttBiasFloorHint')}
                      />
                    )}
                  </form.Field>
                </Grid>
              </>
            ) : null
          }
        </form.Subscribe>
      </Grid>
    </ServiceBlock>
  );
}
