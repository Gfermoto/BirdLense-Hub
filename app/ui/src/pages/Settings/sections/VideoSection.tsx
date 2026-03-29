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
                          value={(field.state.value === 'frigate' ? 'auto' : field.state.value) ?? 'auto'}
                          label={t('settings.triggerLabel')}
                          onChange={(e) => field.handleChange(e.target.value === 'auto' ? 'frigate' : e.target.value as Settings['motion']['source'])}
                        >
                          <MenuItem value="auto">{t('settings.triggerFrigate')}</MenuItem>
                          <MenuItem value="opencv">{t('settings.triggerOpencv')}</MenuItem>
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
          </Box>
        </AccordionDetails>
      </Accordion>
    </>
  );
}
