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

type ScalesUnit = NonNullable<
  NonNullable<Settings['integrations']>['scales']
>['unit'];

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
                        <MenuItem value="homeassistant">
                          {t('settings.scalesSourceHomeAssistant')}
                        </MenuItem>
                      </Select>
                      <FormHelperText>
                        {t('settings.scalesSourceHint')}
                      </FormHelperText>
                    </FormControl>
                  )}
                </form.Field>
              </Grid>
              <Grid size={{ xs: 12, sm: 6 }}>
                <form.Field name="integrations.scales.unit">
                  {(field) => (
                    <FormControl fullWidth>
                      <InputLabel id="settings-scales-unit">
                        {t('settings.scalesUnit')}
                      </InputLabel>
                      <Select
                        labelId="settings-scales-unit"
                        value={(field.state.value ?? 'g') as ScalesUnit}
                        label={t('settings.scalesUnit')}
                        onChange={(e) =>
                          field.handleChange(e.target.value as ScalesUnit)
                        }
                      >
                        <MenuItem value="g">
                          {t('settings.scalesUnitG')}
                        </MenuItem>
                        <MenuItem value="kg">
                          {t('settings.scalesUnitKg')}
                        </MenuItem>
                      </Select>
                      <FormHelperText>
                        {t('settings.scalesUnitHint')}
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
                        <Grid size={{ xs: 12, sm: 6 }}>
                          <form.Field name="integrations.scales.mqtt_tare_payload">
                            {(field) => (
                              <TextField
                                fullWidth
                                value={field.state.value ?? 'TARE'}
                                onChange={(e) =>
                                  field.handleChange(e.target.value)
                                }
                                label={t('settings.scalesMqttTarePayload')}
                                helperText={t(
                                  'settings.scalesMqttTarePayloadHint',
                                )}
                              />
                            )}
                          </form.Field>
                        </Grid>
                      </>
                    ) : (src ?? 'mqtt') === 'homeassistant' ? (
                      <>
                        <Grid size={{ xs: 12 }}>
                          <Alert severity="info">
                            {t('settings.scalesHaAlert')}
                          </Alert>
                        </Grid>
                        <Grid size={{ xs: 12 }}>
                          <form.Field name="integrations.scales.homeassistant_entity_id">
                            {(field) => (
                              <TextField
                                fullWidth
                                value={field.state.value ?? ''}
                                onChange={(e) =>
                                  field.handleChange(e.target.value)
                                }
                                label={t('settings.scalesHaEntity')}
                                placeholder="sensor.bird_feeder_weight"
                                helperText={t('settings.scalesHaEntityHint')}
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
                              <>
                                <Grid size={{ xs: 12 }}>
                                  <form.Field name="integrations.scales.estimate_require_consecutive_spike">
                                    {(field) => (
                                      <>
                                        <FormControlLabel
                                          control={
                                            <Switch
                                              checked={
                                                field.state.value ?? true
                                              }
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
                                <Grid size={{ xs: 12, sm: 6 }}>
                                  <form.Field name="integrations.scales.min_delta_kg_for_estimate">
                                    {(field) => {
                                      const kg = field.state.value ?? 0.008;
                                      const grams = Math.round(kg * 1000);
                                      return (
                                        <TextField
                                          fullWidth
                                          type="number"
                                          inputProps={{
                                            min: 0.1,
                                            max: 5000,
                                            step: 0.1,
                                          }}
                                          value={grams}
                                          onChange={(e) => {
                                            const raw = Number(e.target.value);
                                            const g = Number.isFinite(raw)
                                              ? raw
                                              : 8;
                                            field.handleChange(
                                              Math.max(0.0001, g / 1000),
                                            );
                                          }}
                                          label={t(
                                            'settings.scalesMinDeltaKgEstimate',
                                          )}
                                          helperText={t(
                                            'settings.scalesMinDeltaKgEstimateHint',
                                          )}
                                        />
                                      );
                                    }}
                                  </form.Field>
                                </Grid>
                                <Grid size={{ xs: 12, sm: 6 }}>
                                  <form.Field name="integrations.scales.history_max_lines">
                                    {(field) => (
                                      <TextField
                                        fullWidth
                                        type="number"
                                        inputProps={{
                                          min: 100,
                                          max: 1_000_000,
                                          step: 100,
                                        }}
                                        value={field.state.value ?? 10000}
                                        onChange={(e) =>
                                          field.handleChange(
                                            Number(e.target.value) || 10000,
                                          )
                                        }
                                        label={t(
                                          'settings.scalesHistoryMaxLines',
                                        )}
                                        helperText={t(
                                          'settings.scalesHistoryMaxLinesHint',
                                        )}
                                      />
                                    )}
                                  </form.Field>
                                </Grid>
                              </>
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
