import { useTranslation } from 'react-i18next';
import type { ReactFormExtendedApi } from '@tanstack/react-form';
import Alert from '@mui/material/Alert';
import FormControl from '@mui/material/FormControl';
import FormControlLabel from '@mui/material/FormControlLabel';
import FormHelperText from '@mui/material/FormHelperText';
import Grid from '@mui/material/Grid2';
import InputLabel from '@mui/material/InputLabel';
import MenuItem from '@mui/material/MenuItem';
import Select from '@mui/material/Select';
import Switch from '@mui/material/Switch';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';
import type { Settings } from '../../../types';

export type ScalesSource = NonNullable<
  NonNullable<Settings['integrations']>['scales']
>['source'];

type Props = {
  form: ReactFormExtendedApi<Settings, undefined>;
};

/** integrations.scales.* — вес в UI и карточке визита (не триггер). */
export function ScalesIntegrationFields({ form }: Props) {
  const { t } = useTranslation();

  return (
    <Grid container spacing={2}>
      <Grid size={{ xs: 12 }}>
        <form.Field name="integrations.scales.enabled">
          {(field) => (
            <FormControlLabel
              control={
                <Switch
                  checked={field.state.value ?? false}
                  onChange={(e) => field.handleChange(e.target.checked)}
                />
              }
              label={t('settings.scalesEnabled')}
            />
          )}
        </form.Field>
      </Grid>
      <form.Subscribe selector={(s) => s.values.integrations?.scales?.enabled}>
        {(scalesOn) =>
          scalesOn ? (
            <>
              <Grid size={{ xs: 12 }}>
                <form.Field name="integrations.scales.source">
                  {(field) => (
                    <FormControl fullWidth>
                      <InputLabel id="settings-scales-src">
                        {t('settings.scalesSource')}
                      </InputLabel>
                      <Select
                        labelId="settings-scales-src"
                        value={field.state.value ?? 'mqtt'}
                        label={t('settings.scalesSource')}
                        onChange={(e) =>
                          field.handleChange(e.target.value as ScalesSource)
                        }
                      >
                        <MenuItem value="mqtt">
                          {t('settings.scalesSourceMqtt')}
                        </MenuItem>
                        <MenuItem value="esphome">
                          {t('settings.scalesSourceEsp')}
                        </MenuItem>
                      </Select>
                      <FormHelperText>
                        {t('settings.scalesSourceHint')}
                      </FormHelperText>
                    </FormControl>
                  )}
                </form.Field>
              </Grid>
              <form.Subscribe
                selector={(s) => s.values.integrations?.scales?.source}
              >
                {(src) => (
                  <>
                    {(src ?? 'mqtt') === 'mqtt' ? (
                      <>
                        <Grid size={{ xs: 12 }}>
                          <Alert severity="info">
                            {t('settings.scalesMqttAlert')}
                          </Alert>
                        </Grid>
                        <Grid size={{ xs: 12 }}>
                          <form.Field name="integrations.scales.mqtt_topic_prefix">
                            {(field) => (
                              <TextField
                                fullWidth
                                value={field.state.value ?? ''}
                                onChange={(e) =>
                                  field.handleChange(e.target.value)
                                }
                                label={t('settings.scalesMqttPrefix')}
                                placeholder="birdlense/scale"
                                helperText={t('settings.scalesMqttPrefixHint')}
                              />
                            )}
                          </form.Field>
                        </Grid>
                        <Grid size={{ xs: 12 }}>
                          <form.Field name="integrations.scales.mqtt_topic">
                            {(field) => (
                              <TextField
                                fullWidth
                                value={field.state.value ?? ''}
                                onChange={(e) =>
                                  field.handleChange(e.target.value)
                                }
                                label={t('settings.scalesMqttTopic')}
                                placeholder="birdlense/scale/weight"
                                helperText={t('settings.scalesMqttTopicHint')}
                              />
                            )}
                          </form.Field>
                        </Grid>
                        <Grid size={{ xs: 12 }}>
                          <form.Field name="integrations.scales.mqtt_bird_present_topic">
                            {(field) => (
                              <TextField
                                fullWidth
                                value={field.state.value ?? ''}
                                onChange={(e) =>
                                  field.handleChange(e.target.value)
                                }
                                label={t('settings.scalesMqttBirdPresentTopic')}
                                placeholder="birdlense/scale/bird_present"
                                helperText={t(
                                  'settings.scalesMqttBirdPresentTopicHint',
                                )}
                              />
                            )}
                          </form.Field>
                        </Grid>
                        <Grid size={{ xs: 12 }}>
                          <form.Field name="integrations.scales.mqtt_command_topic">
                            {(field) => (
                              <TextField
                                fullWidth
                                value={field.state.value ?? ''}
                                onChange={(e) =>
                                  field.handleChange(e.target.value)
                                }
                                label={t('settings.scalesMqttCommandTopic')}
                                placeholder="birdlense/scale/command"
                                helperText={t(
                                  'settings.scalesMqttCommandTopicHint',
                                )}
                              />
                            )}
                          </form.Field>
                        </Grid>
                      </>
                    ) : (
                      <>
                        <Grid size={{ xs: 12 }}>
                          <Alert severity="info">
                            {t('settings.scalesEspAlert')}
                          </Alert>
                        </Grid>
                        <Grid size={{ xs: 12, sm: 6 }}>
                          <form.Field name="integrations.scales.esphome_url">
                            {(field) => (
                              <TextField
                                fullWidth
                                value={field.state.value ?? ''}
                                onChange={(e) =>
                                  field.handleChange(e.target.value)
                                }
                                label={t('settings.esphomeUrl')}
                                placeholder="http://192.168.1.50"
                              />
                            )}
                          </form.Field>
                        </Grid>
                        <Grid size={{ xs: 12, sm: 6 }}>
                          <form.Field name="integrations.scales.esphome_weight_sensor_id">
                            {(field) => (
                              <TextField
                                fullWidth
                                value={field.state.value ?? ''}
                                onChange={(e) =>
                                  field.handleChange(e.target.value)
                                }
                                label={t('settings.scalesEspWeightSensorId')}
                                placeholder="weight_live_internal"
                                helperText={t(
                                  'settings.scalesEspWeightSensorIdHint',
                                )}
                              />
                            )}
                          </form.Field>
                        </Grid>
                        <Grid size={{ xs: 12, sm: 6 }}>
                          <form.Field name="integrations.scales.esphome_bird_present_sensor_id">
                            {(field) => (
                              <TextField
                                fullWidth
                                value={field.state.value ?? ''}
                                onChange={(e) =>
                                  field.handleChange(e.target.value)
                                }
                                label={t('settings.scalesEspBirdSensorId')}
                                placeholder="bird_present"
                                helperText={t(
                                  'settings.scalesEspBirdSensorIdHint',
                                )}
                              />
                            )}
                          </form.Field>
                        </Grid>
                        <Grid size={{ xs: 12, sm: 6 }}>
                          <form.Field name="integrations.scales.esphome_tare_button_id">
                            {(field) => (
                              <TextField
                                fullWidth
                                value={field.state.value ?? ''}
                                onChange={(e) =>
                                  field.handleChange(e.target.value)
                                }
                                label={t('settings.scalesEspTareButtonId')}
                                placeholder="manual_tare"
                                helperText={t(
                                  'settings.scalesEspTareButtonIdHint',
                                )}
                              />
                            )}
                          </form.Field>
                        </Grid>
                      </>
                    )}
                    {(src ?? 'mqtt') === 'mqtt' ? (
                      <>
                        <Grid size={{ xs: 12 }}>
                          <form.Field name="integrations.scales.weight_estimate_enabled">
                            {(field) => (
                              <>
                                <FormControlLabel
                                  control={
                                    <Switch
                                      checked={field.state.value ?? true}
                                      onChange={(e) =>
                                        field.handleChange(e.target.checked)
                                      }
                                    />
                                  }
                                  label={t('settings.scalesWeightEstimate')}
                                />
                                <Typography
                                  variant="body2"
                                  color="text.secondary"
                                  display="block"
                                >
                                  {t('settings.scalesWeightEstimateHint')}
                                </Typography>
                              </>
                            )}
                          </form.Field>
                        </Grid>
                        <form.Subscribe
                          selector={(s) =>
                            s.values.integrations?.scales
                              ?.weight_estimate_enabled !== false
                          }
                        >
                          {(weOn) =>
                            weOn ? (
                              <Grid size={{ xs: 12 }}>
                                <form.Field name="integrations.scales.estimate_require_consecutive_spike">
                                  {(field) => (
                                    <>
                                      <FormControlLabel
                                        control={
                                          <Switch
                                            checked={field.state.value ?? true}
                                            onChange={(e) =>
                                              field.handleChange(
                                                e.target.checked,
                                              )
                                            }
                                          />
                                        }
                                        label={t(
                                          'settings.scalesEstimateRequireSpike',
                                        )}
                                      />
                                      <Typography
                                        variant="body2"
                                        color="text.secondary"
                                        display="block"
                                      >
                                        {t(
                                          'settings.scalesEstimateRequireSpikeHint',
                                        )}
                                      </Typography>
                                    </>
                                  )}
                                </form.Field>
                              </Grid>
                            ) : null
                          }
                        </form.Subscribe>
                      </>
                    ) : null}
                  </>
                )}
              </form.Subscribe>
            </>
          ) : null
        }
      </form.Subscribe>
    </Grid>
  );
}
