import { useTranslation } from 'react-i18next';
import type { ReactFormExtendedApi } from '@tanstack/react-form';
import Box from '@mui/material/Box';
import Grid from '@mui/material/Grid2';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';
import FormControl from '@mui/material/FormControl';
import InputLabel from '@mui/material/InputLabel';
import MenuItem from '@mui/material/MenuItem';
import Select from '@mui/material/Select';
import FormHelperText from '@mui/material/FormHelperText';
import FormControlLabel from '@mui/material/FormControlLabel';
import Switch from '@mui/material/Switch';
import Alert from '@mui/material/Alert';
import Accordion from '@mui/material/Accordion';
import AccordionSummary from '@mui/material/AccordionSummary';
import AccordionDetails from '@mui/material/AccordionDetails';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import { ServiceBlock } from '../shared/ServiceBlock';
import type { Settings } from '../../../types';

type Props = {
  form: ReactFormExtendedApi<Settings, undefined>;
};

export function VideoSection({ form }: Props) {
  const { t } = useTranslation();

  return (
    <>
      {/* ========== 2. ДЕТЕКЦИЯ ДВИЖЕНИЯ ========== */}
      <Accordion>
        <AccordionSummary expandIcon={<ExpandMoreIcon />}>
          {t('settings.accordionMotion')}
        </AccordionSummary>
        <AccordionDetails>
          <Box component="fieldset" sx={{ border: 'none', p: 0, m: 0, minWidth: 0 }}>
            <Box component="legend" sx={{ clip: 'rect(0,0,0,0)', position: 'absolute', width: 1, height: 1, overflow: 'hidden' }}>
              {t('settings.accordionMotion')}
            </Box>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
              {t('settings.accordionMotionDesc')}
            </Typography>
            <ServiceBlock title={t('settings.serviceTrigger')}>
              <Grid container spacing={2}>
                <Grid size={{ xs: 12 }}>
                  <form.Field name="motion.source">
                    {(field) => (
                      <FormControl fullWidth>
                        <InputLabel id="settings-trigger-label">{t('settings.triggerLabel')}</InputLabel>
                        <Select
                          labelId="settings-trigger-label"
                          value={field.state.value ?? 'opencv'}
                          label={t('settings.triggerLabel')}
                          onChange={(e) =>
                            field.handleChange(
                              e.target.value as NonNullable<Settings['motion']>['source'],
                            )
                          }
                        >
                          <MenuItem value="opencv">{t('settings.triggerOpencv')}</MenuItem>
                          <MenuItem value="frigate">{t('settings.triggerFrigate')}</MenuItem>
                          <MenuItem value="mqtt">{t('settings.triggerMqtt')}</MenuItem>
                          <MenuItem value="esphome">{t('settings.triggerEsp')}</MenuItem>
                        </Select>
                        <FormHelperText>{t('settings.triggerHint')}</FormHelperText>
                      </FormControl>
                    )}
                  </form.Field>
                </Grid>
                <form.Subscribe selector={(state) => state.values.motion?.source}>
                  {(source) => (
                    <>
                      {source === 'mqtt' && (
                        <>
                          <Grid size={{ xs: 12 }}>
                            <Alert severity="info" sx={{ mb: 2 }}>
                              {t('settings.mqttSensorAlert')}
                            </Alert>
                          </Grid>
                          <Grid size={{ xs: 12 }}>
                            <form.Field name="motion.mqtt_topic">
                              {(field) => (
                                <TextField
                                  fullWidth
                                  value={field.state.value ?? ''}
                                  onChange={(e) => field.handleChange(e.target.value)}
                                  label={t('settings.mqttTopic')}
                                  placeholder="stat/bird_pir/STATE"
                                  helperText={t('settings.mqttTopicHint')}
                                />
                              )}
                            </form.Field>
                          </Grid>
                        </>
                      )}
                      {source === 'esphome' && (
                        <>
                          <Grid size={{ xs: 12 }}>
                            <Alert severity="info" sx={{ mb: 2 }}>
                              {t('settings.esphomeAlert')}
                            </Alert>
                          </Grid>
                          <Grid size={{ xs: 12, sm: 6 }}>
                            <form.Field name="motion.esphome_url">
                              {(field) => (
                                <TextField
                                  fullWidth
                                  value={field.state.value ?? ''}
                                  onChange={(e) => field.handleChange(e.target.value)}
                                  label={t('settings.esphomeUrl')}
                                  placeholder="http://192.168.1.50"
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
                                  label={t('settings.sensorId')}
                                  placeholder="bird_pir"
                                  helperText={t('settings.sensorIdHint')}
                                />
                              )}
                            </form.Field>
                          </Grid>
                        </>
                      )}
                      {source === 'frigate' && (
                        <>
                          <Grid size={{ xs: 12 }}>
                            <Alert severity="info" sx={{ mb: 1 }}>
                              {t('settings.frigateMotionIntro')}
                            </Alert>
                          </Grid>
                          <Grid size={{ xs: 12 }}>
                            <ServiceBlock title={t('settings.frigateRoutingTitle')}>
                              <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                                {t('settings.frigateRoutingDesc')}
                              </Typography>
                              <Grid container spacing={2}>
                                <Grid size={{ xs: 12, sm: 6 }}>
                                  <form.Field name="motion.frigate_camera_filter">
                                    {(field) => (
                                      <TextField
                                        fullWidth
                                        value={(field.state.value || []).join(', ')}
                                        onChange={(e) =>
                                          field.handleChange(
                                            (e.target.value || '')
                                              .split(',')
                                              .map((s) => s.trim())
                                              .filter(Boolean),
                                          )
                                        }
                                        label={t('settings.frigateCameraFilter')}
                                        placeholder="BirdCam, Patio"
                                        helperText={t('settings.frigateCameraFilterHint')}
                                      />
                                    )}
                                  </form.Field>
                                </Grid>
                                <Grid size={{ xs: 12, sm: 6 }}>
                                  <form.Field name="motion.frigate_label_filter">
                                    {(field) => (
                                      <TextField
                                        fullWidth
                                        value={(field.state.value || []).join(', ')}
                                        onChange={(e) =>
                                          field.handleChange(
                                            (e.target.value || '')
                                              .split(',')
                                              .map((s) => s.trim())
                                              .filter(Boolean),
                                          )
                                        }
                                        label={t('settings.frigateLabelFilter')}
                                        placeholder="bird, squirrel"
                                        helperText={t('settings.frigateLabelFilterHint')}
                                      />
                                    )}
                                  </form.Field>
                                </Grid>
                                <Grid size={{ xs: 12, sm: 6 }}>
                                  <form.Field name="motion.frigate_label_exclude">
                                    {(field) => (
                                      <TextField
                                        fullWidth
                                        value={(field.state.value || []).join(', ')}
                                        onChange={(e) =>
                                          field.handleChange(
                                            (e.target.value || '')
                                              .split(',')
                                              .map((s) => s.trim())
                                              .filter(Boolean),
                                          )
                                        }
                                        label={t('settings.frigateLabelExclude')}
                                        placeholder="cat, dog"
                                        helperText={t('settings.frigateLabelExcludeHint')}
                                      />
                                    )}
                                  </form.Field>
                                </Grid>
                                <Grid size={{ xs: 12, sm: 6 }}>
                                  <form.Field name="motion.frigate_trigger_on_tracked_object">
                                    {(field) => (
                                      <FormControl fullWidth>
                                        <FormControlLabel
                                          control={
                                            <Switch
                                              checked={field.state.value !== false}
                                              onChange={(e) => field.handleChange(e.target.checked)}
                                            />
                                          }
                                          label={t('settings.frigateTriggerOnGeometry')}
                                        />
                                        <FormHelperText>
                                          {t('settings.frigateTriggerOnGeometryHint')}
                                        </FormHelperText>
                                      </FormControl>
                                    )}
                                  </form.Field>
                                </Grid>
                              </Grid>
                            </ServiceBlock>
                          </Grid>
                        </>
                      )}
                    </>
                  )}
                </form.Subscribe>
                <Grid size={{ xs: 12, sm: 6 }}>
                  <form.Field name="motion.check_every_n_frames">
                    {(field) => (
                      <TextField
                        fullWidth
                        type="number"
                        inputProps={{ min: 1, max: 30, step: 1 }}
                        value={field.state.value ?? 1}
                        onChange={(e) => {
                          const v = parseInt(e.target.value, 10);
                          field.handleChange(isNaN(v) || v < 1 ? 1 : Math.min(30, v));
                        }}
                        label={t('settings.motionCheckEveryNFrames')}
                        helperText={t('settings.motionCheckEveryNFramesHint')}
                      />
                    )}
                  </form.Field>
                </Grid>
              </Grid>
            </ServiceBlock>
          </Box>
        </AccordionDetails>
      </Accordion>

      {/* ========== 3. РЕЛЕ КОРМУШКИ ========== */}
      <Accordion>
        <AccordionSummary expandIcon={<ExpandMoreIcon />}>
          {t('settings.accordionFeed')}
        </AccordionSummary>
        <AccordionDetails>
          <Box component="fieldset" sx={{ border: 'none', p: 0, m: 0, minWidth: 0 }}>
            <Box component="legend" sx={{ clip: 'rect(0,0,0,0)', position: 'absolute', width: 1, height: 1, overflow: 'hidden' }}>
              {t('settings.accordionFeed')}
            </Box>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
              {t('settings.accordionFeedDesc')}
            </Typography>
            <Grid container spacing={2}>
              <Grid size={{ xs: 12 }}>
                <form.Field name="feed.source">
                  {(field) => (
                    <FormControl fullWidth>
                      <InputLabel id="settings-feed-type-label">{t('settings.feedType')}</InputLabel>
                      <Select
                        labelId="settings-feed-type-label"
                        value={field.state.value ?? 'none'}
                        label={t('settings.feedType')}
                        onChange={(e) => field.handleChange(e.target.value)}
                      >
                        <MenuItem value="none">{t('settings.feedNone')}</MenuItem>
                        <MenuItem value="mqtt">{t('settings.feedMqtt')}</MenuItem>
                        <MenuItem value="esphome">{t('settings.feedEsp')}</MenuItem>
                      </Select>
                    </FormControl>
                  )}
                </form.Field>
              </Grid>
              <form.Subscribe selector={(state) => state.values.feed?.source}>
                {(source) => (
                  <>
                    {source === 'mqtt' && (
                      <>
                        <Grid size={{ xs: 12 }}>
                          <Alert severity="info" sx={{ mb: 2 }}>
                            {t('settings.feedMqttHint')}
                          </Alert>
                        </Grid>
                        <Grid size={{ xs: 12, sm: 6 }}>
                          <form.Field name="feed.mqtt_topic">
                            {(field) => (
                              <TextField
                                fullWidth
                                value={field.state.value ?? ''}
                                onChange={(e) => field.handleChange(e.target.value)}
                                label={t('settings.relayTopic')}
                                placeholder="cmnd/bird_feeder/Power"
                                helperText={t('settings.relayTopicHint')}
                              />
                            )}
                          </form.Field>
                        </Grid>
                      </>
                    )}
                    {source === 'esphome' && (
                      <>
                        <Grid size={{ xs: 12 }}>
                          <Alert severity="info" sx={{ mb: 2 }}>
                            {t('settings.esphomeFeedHint')}
                          </Alert>
                        </Grid>
                        <Grid size={{ xs: 12, sm: 6 }}>
                          <form.Field name="feed.esphome_type">
                            {(field) => (
                              <FormControl fullWidth>
                                <InputLabel id="settings-switch-type-label">{t('settings.switchType')}</InputLabel>
                                <Select
                                  labelId="settings-switch-type-label"
                                  value={field.state.value ?? 'switch'}
                                  label={t('settings.switchType')}
                                  onChange={(e) => field.handleChange(e.target.value as 'switch' | 'button')}
                                >
                                  <MenuItem value="switch">{t('settings.switchTypeSwitch')}</MenuItem>
                                  <MenuItem value="button">{t('settings.switchTypeButton')}</MenuItem>
                                </Select>
                              </FormControl>
                            )}
                          </form.Field>
                        </Grid>
                        <Grid size={{ xs: 12, sm: 6 }}>
                          <form.Field name="feed.esphome_url">
                            {(field) => (
                              <TextField
                                fullWidth
                                value={field.state.value ?? ''}
                                onChange={(e) => field.handleChange(e.target.value)}
                                label={t('settings.deviceUrl')}
                                placeholder="http://192.168.1.50"
                              />
                            )}
                          </form.Field>
                        </Grid>
                        <Grid size={{ xs: 12, sm: 6 }}>
                          <form.Field name="feed.esphome_switch_id">
                            {(field) => (
                              <TextField
                                fullWidth
                                value={field.state.value ?? ''}
                                onChange={(e) => field.handleChange(e.target.value)}
                                label={t('settings.switchId')}
                                placeholder="bird_feeder"
                                helperText={t('settings.switchIdHint')}
                              />
                            )}
                          </form.Field>
                        </Grid>
                      </>
                    )}
                    {(source === 'mqtt' || source === 'esphome') && (
                      <Grid size={{ xs: 12, sm: 6 }}>
                        <form.Field name="feed.duration_seconds">
                          {(field) => (
                            <TextField
                              fullWidth
                              type="number"
                              inputProps={{ min: 1, max: 30 }}
                              value={field.state.value ?? 3}
                              onChange={(e) => field.handleChange(Number(e.target.value) || 3)}
                              label={t('settings.relaySeconds')}
                              helperText={t('settings.relaySecondsHint')}
                            />
                          )}
                        </form.Field>
                      </Grid>
                    )}
                  </>
                )}
              </form.Subscribe>
            </Grid>

            <Box sx={{ mt: 3 }}>
            <ServiceBlock title={t('settings.serviceScales')}>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                {t('settings.serviceScalesDesc')}
              </Typography>
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
                                <InputLabel id="settings-scales-src">{t('settings.scalesSource')}</InputLabel>
                                <Select
                                  labelId="settings-scales-src"
                                  value={field.state.value ?? 'mqtt'}
                                  label={t('settings.scalesSource')}
                                  onChange={(e) =>
                                    field.handleChange(e.target.value as 'mqtt' | 'homeassistant')
                                  }
                                >
                                  <MenuItem value="mqtt">{t('settings.scalesSourceMqtt')}</MenuItem>
                                  <MenuItem value="homeassistant">{t('settings.scalesSourceHa')}</MenuItem>
                                </Select>
                                <FormHelperText>{t('settings.scalesSourceHint')}</FormHelperText>
                              </FormControl>
                            )}
                          </form.Field>
                        </Grid>
                        <form.Subscribe selector={(s) => s.values.integrations?.scales?.source}>
                          {(src) => (
                            <>
                              {(src ?? 'mqtt') === 'mqtt' && (
                                <>
                                  <Grid size={{ xs: 12 }}>
                                    <form.Field name="integrations.scales.mqtt_topic">
                                      {(field) => (
                                        <TextField
                                          fullWidth
                                          value={field.state.value ?? ''}
                                          onChange={(e) => field.handleChange(e.target.value)}
                                          label={t('settings.scalesMqttTopic')}
                                          placeholder="homeassistant/sensor/feeder_scale_weight/state"
                                          helperText={t('settings.scalesMqttTopicHint')}
                                        />
                                      )}
                                    </form.Field>
                                  </Grid>
                                  <Grid size={{ xs: 12 }}>
                                    <form.Field name="integrations.scales.mqtt_topic_prefix">
                                      {(field) => (
                                        <TextField
                                          fullWidth
                                          value={field.state.value ?? ''}
                                          onChange={(e) => field.handleChange(e.target.value)}
                                          label={t('settings.scalesMqttPrefix')}
                                          placeholder="birdlense/scale"
                                          helperText={t('settings.scalesMqttPrefixHint')}
                                        />
                                      )}
                                    </form.Field>
                                  </Grid>
                                </>
                              )}
                              {src === 'homeassistant' && (
                                <>
                                  <Grid size={{ xs: 12 }}>
                                    <form.Field name="integrations.scales.homeassistant_entity_id">
                                      {(field) => (
                                        <TextField
                                          fullWidth
                                          value={field.state.value ?? ''}
                                          onChange={(e) => field.handleChange(e.target.value)}
                                          label={t('settings.scalesHaEntity')}
                                          placeholder="sensor.smart_scale_weight"
                                          helperText={t('settings.scalesHaEntityHint')}
                                        />
                                      )}
                                    </form.Field>
                                  </Grid>
                                  <Grid size={{ xs: 12 }}>
                                    <Alert severity="info">{t('settings.scalesHaProcessorHint')}</Alert>
                                  </Grid>
                                </>
                              )}
                            </>
                          )}
                        </form.Subscribe>
                        <Grid size={{ xs: 12, sm: 6 }}>
                          <form.Field name="integrations.scales.unit">
                            {(field) => (
                              <FormControl fullWidth>
                                <InputLabel id="settings-scales-unit">{t('settings.scalesUnit')}</InputLabel>
                                <Select
                                  labelId="settings-scales-unit"
                                  value={field.state.value ?? 'kg'}
                                  label={t('settings.scalesUnit')}
                                  onChange={(e) => field.handleChange(e.target.value as 'kg' | 'g')}
                                >
                                  <MenuItem value="kg">kg</MenuItem>
                                  <MenuItem value="g">g</MenuItem>
                                </Select>
                              </FormControl>
                            )}
                          </form.Field>
                        </Grid>
                        <form.Subscribe selector={(s) => s.values.integrations?.scales?.source}>
                          {(src) =>
                            (src ?? 'mqtt') === 'mqtt' ? (
                              <>
                                <Grid size={{ xs: 12 }}>
                                  <form.Field name="integrations.scales.weight_estimate_enabled">
                                    {(field) => (
                                      <>
                                        <FormControlLabel
                                          control={
                                            <Switch
                                              checked={field.state.value ?? true}
                                              onChange={(e) => field.handleChange(e.target.checked)}
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
                                    s.values.integrations?.scales?.weight_estimate_enabled !== false
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
                                                    checked={field.state.value ?? true}
                                                    onChange={(e) =>
                                                      field.handleChange(e.target.checked)
                                                    }
                                                  />
                                                }
                                                label={t('settings.scalesEstimateRequireSpike')}
                                              />
                                              <Typography
                                                variant="body2"
                                                color="text.secondary"
                                                display="block"
                                              >
                                                {t('settings.scalesEstimateRequireSpikeHint')}
                                              </Typography>
                                            </>
                                          )}
                                        </form.Field>
                                      </Grid>
                                      </>
                                    ) : null
                                  }
                                </form.Subscribe>
                                <Grid size={{ xs: 12 }}>
                                  <form.Field name="integrations.scales.motion_trigger_enabled">
                                    {(field) => (
                                      <>
                                        <FormControlLabel
                                          control={
                                            <Switch
                                              checked={field.state.value ?? false}
                                              onChange={(e) =>
                                                field.handleChange(e.target.checked)
                                              }
                                            />
                                          }
                                          label={t('settings.scalesMotionTrigger')}
                                        />
                                        <Typography
                                          variant="body2"
                                          color="text.secondary"
                                          display="block"
                                        >
                                          {t('settings.scalesMotionTriggerHint')}
                                        </Typography>
                                      </>
                                    )}
                                  </form.Field>
                                </Grid>
                                <form.Subscribe
                                  selector={(s) => s.values.integrations?.scales?.motion_trigger_enabled}
                                >
                                  {(mtOn) =>
                                    mtOn ? (
                                      <>
                                        <Grid size={{ xs: 12, sm: 6 }}>
                                          <form.Field name="integrations.scales.motion_trigger_min_delta_kg">
                                            {(field) => (
                                              <TextField
                                                fullWidth
                                                type="number"
                                                inputProps={{ min: 0.001, step: 0.001 }}
                                                value={field.state.value ?? 0.02}
                                                onChange={(e) => {
                                                  const raw = Number(e.target.value);
                                                  const v =
                                                    Number.isFinite(raw) && raw >= 0.001 ? raw : 0.02;
                                                  field.handleChange(v);
                                                }}
                                                label={t('settings.scalesMotionMinDelta')}
                                                helperText={t('settings.scalesMotionMinDeltaHint')}
                                              />
                                            )}
                                          </form.Field>
                                        </Grid>
                                        <Grid size={{ xs: 12, sm: 6 }}>
                                          <form.Field name="integrations.scales.motion_trigger_debounce_seconds">
                                            {(field) => (
                                              <TextField
                                                fullWidth
                                                type="number"
                                                inputProps={{ min: 0.2, step: 0.1 }}
                                                value={field.state.value ?? 1.5}
                                                onChange={(e) => {
                                                  const raw = Number(e.target.value);
                                                  const v =
                                                    Number.isFinite(raw) && raw >= 0.2 ? raw : 1.5;
                                                  field.handleChange(v);
                                                }}
                                                label={t('settings.scalesMotionDebounce')}
                                              />
                                            )}
                                          </form.Field>
                                        </Grid>
                                      </>
                                    ) : null
                                  }
                                </form.Subscribe>
                              </>
                            ) : null
                          }
                        </form.Subscribe>
                      </>
                    ) : null
                  }
                </form.Subscribe>
              </Grid>
            </ServiceBlock>
            </Box>
          </Box>
        </AccordionDetails>
      </Accordion>
    </>
  );
}
