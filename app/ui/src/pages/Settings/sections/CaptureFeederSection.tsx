import { useTranslation } from 'react-i18next';
import type { ReactFormExtendedApi } from '@tanstack/react-form';
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Checkbox from '@mui/material/Checkbox';
import FormControl from '@mui/material/FormControl';
import FormControlLabel from '@mui/material/FormControlLabel';
import FormHelperText from '@mui/material/FormHelperText';
import Grid from '@mui/material/Grid2';
import InputLabel from '@mui/material/InputLabel';
import MenuItem from '@mui/material/MenuItem';
import Select from '@mui/material/Select';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';
import Accordion from '@mui/material/Accordion';
import AccordionSummary from '@mui/material/AccordionSummary';
import AccordionDetails from '@mui/material/AccordionDetails';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import { ServiceBlock } from '../shared/ServiceBlock';
import { ScalesIntegrationFields } from '../shared/scalesIntegrationFields';
import { FeederRelayFields } from '../shared/feederRelayFields';
import { FrigateExclusionsFields } from '../shared/FrigateExclusionsFields';
import type { Settings } from '../../../types';

type Props = {
  form: ReactFormExtendedApi<Settings, undefined>;
};

type TriggerTransportSource = NonNullable<
  NonNullable<Settings['triggers']>['motion_sensor']
>['source'];

function splitCsv(value: string): string[] {
  return (value || '')
    .split(',')
    .map((part) => part.trim())
    .filter(Boolean);
}

export function CaptureFeederSection({ form }: Props) {
  const { t } = useTranslation();
  const resolutions = [
    { label: t('settings.resolutionFullHD'), width: 1920, height: 1080 },
    { label: t('settings.resolutionHD'), width: 1280, height: 720 },
    { label: t('settings.resolutionVGA'), width: 640, height: 480 },
  ];

  return (
    <Accordion>
      <AccordionSummary expandIcon={<ExpandMoreIcon />}>
        {t('settings.accordionCaptureFeeder')}
      </AccordionSummary>
      <AccordionDetails>
        <Box
          component="fieldset"
          sx={{ border: 'none', p: 0, m: 0, minWidth: 0 }}
        >
          <Box
            component="legend"
            sx={{
              clip: 'rect(0,0,0,0)',
              position: 'absolute',
              width: 1,
              height: 1,
              overflow: 'hidden',
            }}
          >
            {t('settings.accordionCaptureFeeder')}
          </Box>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            {t('settings.accordionCaptureFeederDesc')}
          </Typography>

          <ServiceBlock title={t('settings.accordionMotion')}>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
              {t('settings.accordionMotionDesc')}
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
              {t('settings.triggerGroupedHint')}
            </Typography>
            <Grid container spacing={2}>
              <Grid size={{ xs: 12 }}>
                <ServiceBlock title={t('settings.triggerOpencvBlock')}>
                  <form.Field name="triggers.opencv.enabled">
                    {(field) => (
                      <FormControlLabel
                        control={
                          <Checkbox
                            checked={field.state.value ?? true}
                            onChange={(e) =>
                              field.handleChange(e.target.checked)
                            }
                          />
                        }
                        label={t('settings.triggerOpencv')}
                      />
                    )}
                  </form.Field>
                  <form.Subscribe
                    selector={(state) =>
                      state.values.triggers?.opencv?.enabled !== false
                    }
                  >
                    {(enabled) =>
                      enabled ? (
                        <Grid container spacing={2}>
                          <Grid size={{ xs: 12, sm: 4 }}>
                            <form.Field name="triggers.opencv.check_every_n_frames">
                              {(field) => (
                                <TextField
                                  fullWidth
                                  type="number"
                                  inputProps={{ min: 1, max: 30, step: 1 }}
                                  value={field.state.value ?? 1}
                                  onChange={(e) => {
                                    const v = parseInt(e.target.value, 10);
                                    field.handleChange(
                                      Number.isNaN(v) || v < 1
                                        ? 1
                                        : Math.min(30, v),
                                    );
                                  }}
                                  label={t('settings.motionCheckEveryNFrames')}
                                  helperText={t(
                                    'settings.motionCheckEveryNFramesHint',
                                  )}
                                />
                              )}
                            </form.Field>
                          </Grid>
                          <Grid size={{ xs: 12, sm: 4 }}>
                            <form.Field name="triggers.opencv.diff_threshold">
                              {(field) => (
                                <TextField
                                  fullWidth
                                  type="number"
                                  inputProps={{ min: 5, max: 80, step: 1 }}
                                  value={field.state.value ?? 18}
                                  onChange={(e) =>
                                    field.handleChange(
                                      Number(e.target.value) || 18,
                                    )
                                  }
                                  label={t('settings.opencvDiffThreshold')}
                                />
                              )}
                            </form.Field>
                          </Grid>
                          <Grid size={{ xs: 12, sm: 4 }}>
                            <form.Field name="triggers.opencv.min_contour_area">
                              {(field) => (
                                <TextField
                                  fullWidth
                                  type="number"
                                  inputProps={{ min: 50, max: 20000, step: 10 }}
                                  value={field.state.value ?? 240}
                                  onChange={(e) =>
                                    field.handleChange(
                                      Number(e.target.value) || 240,
                                    )
                                  }
                                  label={t('settings.opencvMinContourArea')}
                                />
                              )}
                            </form.Field>
                          </Grid>
                        </Grid>
                      ) : null
                    }
                  </form.Subscribe>
                </ServiceBlock>
              </Grid>

              <Grid size={{ xs: 12 }}>
                <ServiceBlock title={t('settings.triggerFrigateBlock')}>
                  <form.Field name="triggers.frigate.enabled">
                    {(field) => (
                      <FormControlLabel
                        control={
                          <Checkbox
                            checked={field.state.value !== false}
                            onChange={(e) =>
                              field.handleChange(e.target.checked)
                            }
                          />
                        }
                        label={t('settings.triggerFrigate')}
                      />
                    )}
                  </form.Field>
                  <form.Subscribe
                    selector={(state) =>
                      state.values.triggers?.frigate?.enabled !== false
                    }
                  >
                    {(enabled) =>
                      enabled ? (
                        <>
                          <Alert
                            severity="info"
                            variant="outlined"
                            sx={{ mb: 2 }}
                          >
                            {t('settings.frigateMotionIntro')}
                          </Alert>
                          <Grid container spacing={2}>
                            <Grid size={{ xs: 12, sm: 6 }}>
                              <form.Field name="triggers.frigate.min_trigger_score">
                                {(field) => (
                                  <TextField
                                    fullWidth
                                    type="number"
                                    inputProps={{ min: 0, max: 1, step: 0.05 }}
                                    value={
                                      field.state.value === undefined ||
                                      field.state.value === null
                                        ? 0.5
                                        : field.state.value
                                    }
                                    onChange={(e) => {
                                      const v = e.target.value;
                                      if (v === '') {
                                        field.handleChange(undefined);
                                        return;
                                      }
                                      field.handleChange(Number(v));
                                    }}
                                    label={t('settings.frigateMinTriggerScore')}
                                    helperText={t(
                                      'settings.frigateMinTriggerScoreHint',
                                    )}
                                  />
                                )}
                              </form.Field>
                            </Grid>
                            <Grid size={{ xs: 12 }}>
                              <form.Field name="triggers.frigate.topic">
                                {(field) => (
                                  <TextField
                                    fullWidth
                                    value={
                                      field.state.value ?? 'frigate/events'
                                    }
                                    onChange={(e) =>
                                      field.handleChange(e.target.value)
                                    }
                                    label={t('settings.frigateTopic')}
                                    placeholder="frigate/events"
                                    helperText={t('settings.frigateTopicHint')}
                                  />
                                )}
                              </form.Field>
                            </Grid>
                            <Grid size={{ xs: 12 }}>
                              <Typography variant="subtitle2" sx={{ mt: 1, mb: 0.5 }}>
                                {t('settings.frigateRoutingTitle')}
                              </Typography>
                              <Typography
                                variant="body2"
                                color="text.secondary"
                                sx={{ mb: 1 }}
                              >
                                {t('settings.frigateRoutingDesc')}
                              </Typography>
                            </Grid>
                            <Grid size={{ xs: 12, sm: 6 }}>
                              <form.Field name="triggers.frigate.camera_filter">
                                {(field) => (
                                  <TextField
                                    fullWidth
                                    value={(field.state.value || []).join(', ')}
                                    onChange={(e) =>
                                      field.handleChange(
                                        splitCsv(e.target.value),
                                      )
                                    }
                                    label={t('settings.frigateCameraFilter')}
                                    placeholder={t(
                                      'settings.frigateCameraFilterPlaceholder',
                                    )}
                                    helperText={t(
                                      'settings.frigateCameraFilterHint',
                                    )}
                                  />
                                )}
                              </form.Field>
                            </Grid>
                            <Grid size={{ xs: 12, sm: 6 }}>
                              <form.Field name="triggers.frigate.label_filter">
                                {(field) => (
                                  <TextField
                                    fullWidth
                                    value={(field.state.value || []).join(', ')}
                                    onChange={(e) =>
                                      field.handleChange(
                                        splitCsv(e.target.value),
                                      )
                                    }
                                    label={t('settings.frigateLabelFilter')}
                                    placeholder={t(
                                      'settings.frigateLabelFilterPlaceholder',
                                    )}
                                    helperText={t(
                                      'settings.frigateLabelFilterHint',
                                    )}
                                  />
                                )}
                              </form.Field>
                            </Grid>
                            <Grid size={{ xs: 12 }}>
                              <Typography variant="subtitle2" sx={{ mt: 1, mb: 0.5 }}>
                                {t('settings.frigateExclusionsHeading')}
                              </Typography>
                            </Grid>
                            <FrigateExclusionsFields form={form} />
                          </Grid>
                        </>
                      ) : null
                    }
                  </form.Subscribe>
                </ServiceBlock>
              </Grid>

              <Grid size={{ xs: 12 }}>
                <ServiceBlock title={t('settings.triggerMotionSensorBlock')}>
                  <form.Field name="triggers.motion_sensor.enabled">
                    {(field) => (
                      <FormControlLabel
                        control={
                          <Checkbox
                            checked={field.state.value ?? false}
                            onChange={(e) =>
                              field.handleChange(e.target.checked)
                            }
                          />
                        }
                        label={t('settings.triggerMotionSensor')}
                      />
                    )}
                  </form.Field>
                  <form.Subscribe
                    selector={(state) => ({
                      enabled:
                        state.values.triggers?.motion_sensor?.enabled === true,
                      source: (state.values.triggers?.motion_sensor?.source ??
                        'mqtt') as TriggerTransportSource,
                    })}
                  >
                    {({ enabled, source }) =>
                      enabled ? (
                        <Grid container spacing={2}>
                          <Grid size={{ xs: 12 }}>
                            <form.Field name="triggers.motion_sensor.source">
                              {(field) => (
                                <FormControl fullWidth>
                                  <InputLabel id="settings-motion-sensor-source">
                                    {t('settings.triggerSource')}
                                  </InputLabel>
                                  <Select
                                    labelId="settings-motion-sensor-source"
                                    value={field.state.value ?? 'mqtt'}
                                    label={t('settings.triggerSource')}
                                    onChange={(e) =>
                                      field.handleChange(
                                        e.target
                                          .value as TriggerTransportSource,
                                      )
                                    }
                                  >
                                    <MenuItem value="mqtt">
                                      {t('settings.triggerMqtt')}
                                    </MenuItem>
                                    <MenuItem value="esphome">
                                      {t('settings.triggerEsp')}
                                    </MenuItem>
                                  </Select>
                                </FormControl>
                              )}
                            </form.Field>
                          </Grid>
                          {source === 'mqtt' ? (
                            <>
                              <Grid size={{ xs: 12 }}>
                                <Alert severity="info" variant="outlined">
                                  {t('settings.mqttSensorAlert')}
                                </Alert>
                              </Grid>
                              <Grid size={{ xs: 12 }}>
                                <form.Field name="triggers.motion_sensor.mqtt_topic">
                                  {(field) => (
                                    <TextField
                                      fullWidth
                                      value={field.state.value ?? ''}
                                      onChange={(e) =>
                                        field.handleChange(e.target.value)
                                      }
                                      label={t('settings.mqttTopic')}
                                      placeholder="stat/bird_pir/STATE"
                                      helperText={t('settings.mqttTopicHint')}
                                    />
                                  )}
                                </form.Field>
                              </Grid>
                            </>
                          ) : (
                            <>
                              <Grid size={{ xs: 12 }}>
                                <Alert severity="info" variant="outlined">
                                  {t('settings.esphomeAlert')}
                                </Alert>
                              </Grid>
                              <Grid size={{ xs: 12, sm: 6 }}>
                                <form.Field name="triggers.motion_sensor.esphome_url">
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
                                <form.Field name="triggers.motion_sensor.esphome_sensor_id">
                                  {(field) => (
                                    <TextField
                                      fullWidth
                                      value={field.state.value ?? ''}
                                      onChange={(e) =>
                                        field.handleChange(e.target.value)
                                      }
                                      label={t('settings.sensorId')}
                                      placeholder="bird_pir"
                                      helperText={t('settings.sensorIdHint')}
                                    />
                                  )}
                                </form.Field>
                              </Grid>
                            </>
                          )}
                        </Grid>
                      ) : null
                    }
                  </form.Subscribe>
                </ServiceBlock>
              </Grid>

              <Grid size={{ xs: 12 }}>
                <ServiceBlock title={t('settings.serviceScales')}>
                  <Typography
                    variant="body2"
                    color="text.secondary"
                    sx={{ mb: 2 }}
                  >
                    {t('settings.serviceScalesDesc')}
                  </Typography>
                  <ScalesIntegrationFields form={form} />
                </ServiceBlock>
              </Grid>

              <Grid size={{ xs: 12 }}>
                <ServiceBlock title={t('settings.triggerScalesBlock')}>
                  <form.Field name="triggers.scales.enabled">
                    {(field) => (
                      <FormControlLabel
                        control={
                          <Checkbox
                            checked={field.state.value ?? false}
                            onChange={(e) =>
                              field.handleChange(e.target.checked)
                            }
                          />
                        }
                        label={t('settings.triggerScales')}
                      />
                    )}
                  </form.Field>
                  <Typography
                    variant="body2"
                    color="text.secondary"
                    sx={{ mb: 2 }}
                  >
                    {t('settings.triggerScalesHint')}
                  </Typography>
                  <form.Subscribe
                    selector={(state) =>
                      state.values.triggers?.scales?.enabled === true
                    }
                  >
                    {(triggerOn) =>
                      triggerOn ? (
                        <Grid container spacing={2}>
                          <Grid size={{ xs: 12 }}>
                            <Alert severity="info" variant="outlined">
                              {t('settings.triggerScalesPipelineHint')}
                            </Alert>
                          </Grid>
                          <Grid size={{ xs: 12, sm: 6 }}>
                            <form.Field name="triggers.scales.motion_trigger_min_delta_kg">
                              {(field) => {
                                const kg = field.state.value ?? 0.02;
                                const grams = Math.round(kg * 1000);
                                return (
                                  <TextField
                                    fullWidth
                                    type="number"
                                    inputProps={{
                                      min: 1,
                                      max: 500000,
                                      step: 1,
                                    }}
                                    value={grams}
                                    onChange={(e) => {
                                      const raw = Number(e.target.value);
                                      const g = Number.isFinite(raw) ? raw : 20;
                                      field.handleChange(
                                        Math.max(0.001, g / 1000),
                                      );
                                    }}
                                    label={t('settings.scalesMotionMinDelta')}
                                    helperText={t(
                                      'settings.scalesMotionMinDeltaHint',
                                    )}
                                  />
                                );
                              }}
                            </form.Field>
                          </Grid>
                          <Grid size={{ xs: 12, sm: 6 }}>
                            <form.Field name="triggers.scales.motion_trigger_debounce_seconds">
                              {(field) => (
                                <TextField
                                  fullWidth
                                  type="number"
                                  inputProps={{ min: 0.2, step: 0.1 }}
                                  value={field.state.value ?? 1.5}
                                  onChange={(e) =>
                                    field.handleChange(
                                      Number(e.target.value) || 1.5,
                                    )
                                  }
                                  label={t('settings.scalesMotionDebounce')}
                                />
                              )}
                            </form.Field>
                          </Grid>
                        </Grid>
                      ) : null
                    }
                  </form.Subscribe>
                </ServiceBlock>
              </Grid>
            </Grid>
          </ServiceBlock>

          <ServiceBlock title={t('settings.serviceRecording')}>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
              {t('settings.serviceRecordingDesc')}
            </Typography>
            <Grid container spacing={2}>
              <Grid size={{ xs: 12 }}>
                <form.Field name="video.video_width">
                  {(widthField) => (
                    <form.Field name="video.video_height">
                      {(heightField) => {
                        const w = widthField.state.value;
                        const h = heightField.state.value;
                        const sel = resolutions.find(
                          (r) => r.width === w && r.height === h,
                        );

                        return (
                          <FormControl fullWidth>
                            <InputLabel id="settings-resolution-label">
                              {t('settings.resolution')}
                            </InputLabel>
                            <Select
                              labelId="settings-resolution-label"
                              value={sel ? `${sel.width}x${sel.height}` : ''}
                              label={t('settings.resolution')}
                              onChange={(e) => {
                                const [a, b] = (e.target.value as string)
                                  .split('x')
                                  .map(Number);
                                widthField.handleChange(a);
                                heightField.handleChange(b);
                              }}
                            >
                              {resolutions.map((r) => (
                                <MenuItem
                                  key={r.label}
                                  value={`${r.width}x${r.height}`}
                                >
                                  {r.label}
                                </MenuItem>
                              ))}
                            </Select>
                            <FormHelperText>
                              {t('settings.resolutionHint')}
                            </FormHelperText>
                          </FormControl>
                        );
                      }}
                    </form.Field>
                  )}
                </form.Field>
              </Grid>
            </Grid>
          </ServiceBlock>

          <FeederRelayFields form={form} />
        </Box>
      </AccordionDetails>
    </Accordion>
  );
}
