import { useTranslation } from 'react-i18next';
import type { ReactFormExtendedApi } from '@tanstack/react-form';
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
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
import Accordion from '@mui/material/Accordion';
import AccordionSummary from '@mui/material/AccordionSummary';
import AccordionDetails from '@mui/material/AccordionDetails';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import { Link as RouterLink } from 'react-router-dom';
import { PasswordField } from '../../../components/PasswordField';
import { ServiceBlock } from '../shared/ServiceBlock';
import { CamerasListField } from '../shared/CamerasListField';
import type { Settings } from '../../../types';

type Props = {
  form: ReactFormExtendedApi<Settings, undefined>;
};

export function ConnectionsSection({ form }: Props) {
  const { t } = useTranslation();

  return (
    <Accordion>
      <AccordionSummary expandIcon={<ExpandMoreIcon />}>
        {t('settings.accordionConnections')}
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
            {t('settings.accordionConnections')}
          </Box>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            {t('settings.accordionConnectionsDesc')}
          </Typography>

          <ServiceBlock title={t('settings.serviceMqtt')}>
            <Grid container spacing={2}>
              <Grid size={{ xs: 12, sm: 6 }}>
                <form.Field name="mqtt.broker">
                  {(field) => (
                    <TextField
                      fullWidth
                      id={field.name}
                      value={field.state.value ?? ''}
                      onChange={(e) => field.handleChange(e.target.value)}
                      label={t('settings.mqttBroker')}
                      placeholder="192.168.1.10"
                      helperText={t('settings.mqttBrokerHint')}
                    />
                  )}
                </form.Field>
              </Grid>
              <Grid size={{ xs: 12, sm: 6 }}>
                <form.Field name="mqtt.port">
                  {(field) => (
                    <TextField
                      fullWidth
                      type="number"
                      value={field.state.value ?? 1883}
                      onChange={(e) =>
                        field.handleChange(Number(e.target.value) || 1883)
                      }
                      label={t('settings.mqttPort')}
                    />
                  )}
                </form.Field>
              </Grid>
              <Grid size={{ xs: 12, sm: 6 }}>
                <form.Field name="mqtt.username">
                  {(field) => (
                    <TextField
                      fullWidth
                      value={field.state.value ?? ''}
                      onChange={(e) => field.handleChange(e.target.value)}
                      label={t('settings.mqttUser')}
                    />
                  )}
                </form.Field>
              </Grid>
              <Grid size={{ xs: 12, sm: 6 }}>
                <form.Field name="mqtt.password">
                  {(field) => (
                    <PasswordField
                      value={field.state.value ?? ''}
                      onChange={(v) => field.handleChange(v)}
                      label={t('settings.mqttPassword')}
                    />
                  )}
                </form.Field>
              </Grid>
              <Grid size={{ xs: 12, sm: 6 }}>
                <form.Field name="mqtt.publish_topic">
                  {(field) => (
                    <TextField
                      fullWidth
                      value={field.state.value ?? 'birdlense/detections'}
                      onChange={(e) => field.handleChange(e.target.value)}
                      label={t('settings.mqttPublishTopic')}
                      placeholder="birdlense/detections"
                      helperText={t('settings.mqttPublishTopicHint')}
                    />
                  )}
                </form.Field>
              </Grid>
              <Grid size={{ xs: 12, sm: 6 }}>
                <form.Field name="mqtt.reconnect_min_delay">
                  {(field) => (
                    <TextField
                      fullWidth
                      type="number"
                      inputProps={{ min: 1, max: 3600, step: 1 }}
                      value={field.state.value ?? 5}
                      onChange={(e) =>
                        field.handleChange(Number(e.target.value) || 5)
                      }
                      label={t('settings.mqttReconnectMinDelay')}
                      helperText={t('settings.mqttReconnectMinDelayHint')}
                    />
                  )}
                </form.Field>
              </Grid>
              <Grid size={{ xs: 12, sm: 6 }}>
                <form.Field name="mqtt.reconnect_max_delay">
                  {(field) => (
                    <TextField
                      fullWidth
                      type="number"
                      inputProps={{ min: 1, max: 3600, step: 1 }}
                      value={field.state.value ?? 300}
                      onChange={(e) =>
                        field.handleChange(Number(e.target.value) || 300)
                      }
                      label={t('settings.mqttReconnectMaxDelay')}
                      helperText={t('settings.mqttReconnectMaxDelayHint')}
                    />
                  )}
                </form.Field>
              </Grid>
              <Grid size={{ xs: 12, sm: 6 }}>
                <form.Field name="mqtt.ha_discovery">
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
                        label={t('settings.mqttHaDiscovery')}
                      />
                      <FormHelperText>
                        {t('settings.mqttHaDiscoveryHint')}
                      </FormHelperText>
                    </>
                  )}
                </form.Field>
              </Grid>
              <Grid size={{ xs: 12 }}>
                <form.Field name="triggers.frigate.topic">
                  {(field) => (
                    <TextField
                      fullWidth
                      value={field.state.value ?? 'frigate/events'}
                      onChange={(e) => field.handleChange(e.target.value)}
                      label={t('settings.frigateTopic')}
                      placeholder="frigate/events"
                      helperText={t('settings.frigateTopicConnectionsHint')}
                    />
                  )}
                </form.Field>
              </Grid>
            </Grid>
          </ServiceBlock>

          <ServiceBlock title={t('settings.accordionHomeAssistant')}>
            <Alert severity="info" variant="outlined" sx={{ mb: 2 }}>
              {t('settings.haEnvOverrideHint')}
            </Alert>
            <Grid container spacing={2}>
              <Grid size={{ xs: 12 }}>
                <form.Field name="homeassistant.url">
                  {(field) => (
                    <TextField
                      fullWidth
                      value={field.state.value ?? ''}
                      onChange={(e) => field.handleChange(e.target.value)}
                      label={t('settings.haUrl')}
                      placeholder="http://homeassistant:8123"
                      helperText={t('settings.haUrlHint')}
                    />
                  )}
                </form.Field>
              </Grid>
              <Grid size={{ xs: 12 }}>
                <form.Field name="homeassistant.token">
                  {(field) => (
                    <PasswordField
                      value={field.state.value ?? ''}
                      onChange={(v) => field.handleChange(v)}
                      label={t('settings.haToken')}
                      placeholder={t('settings.haTokenPlaceholder')}
                      helperText={t('settings.haTokenHint')}
                    />
                  )}
                </form.Field>
              </Grid>
            </Grid>
          </ServiceBlock>

          <ServiceBlock title={t('settings.serviceGo2rtc')}>
            <Grid container spacing={2}>
              <Grid size={{ xs: 12 }}>
                <form.Field name="video.go2rtc_url">
                  {(field) => (
                    <TextField
                      fullWidth
                      value={field.state.value ?? ''}
                      onChange={(e) => field.handleChange(e.target.value)}
                      label={t('settings.go2rtcUrlLabel')}
                      placeholder="http://192.168.1.10:1984"
                      helperText={t('settings.go2rtcUrlHint')}
                    />
                  )}
                </form.Field>
              </Grid>
              <Grid size={{ xs: 12, sm: 6 }}>
                <form.Field name="video.go2rtc_username">
                  {(field) => (
                    <TextField
                      fullWidth
                      value={field.state.value ?? ''}
                      onChange={(e) => field.handleChange(e.target.value)}
                      label={t('settings.go2rtcUser')}
                    />
                  )}
                </form.Field>
              </Grid>
              <Grid size={{ xs: 12, sm: 6 }}>
                <form.Field name="video.go2rtc_password">
                  {(field) => (
                    <PasswordField
                      value={field.state.value ?? ''}
                      onChange={(v) => field.handleChange(v)}
                      label={t('settings.go2rtcPassword')}
                    />
                  )}
                </form.Field>
              </Grid>
            </Grid>
          </ServiceBlock>

          <ServiceBlock title={t('settings.videoFileReplayTitle')}>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
              {t('settings.videoFileReplayDesc')}
            </Typography>
            <Grid container spacing={2}>
              <Grid size={{ xs: 12 }}>
                <form.Field name="video.file_realtime_simulation">
                  {(field) => (
                    <>
                      <FormControlLabel
                        control={
                          <Switch
                            checked={Boolean(field.state.value)}
                            onChange={(e) =>
                              field.handleChange(e.target.checked)
                            }
                          />
                        }
                        label={t('settings.videoFileRealtimeSimulation')}
                      />
                      <FormHelperText sx={{ ml: 0, mt: 0.5 }}>
                        {t('settings.videoFileRealtimeSimulationHint')}
                      </FormHelperText>
                    </>
                  )}
                </form.Field>
              </Grid>
              <Grid size={{ xs: 12 }}>
                <Alert severity="info" variant="outlined">
                  {t('settings.videoFileReplayLibraryHint')}{' '}
                  <RouterLink to="/library#file-replay">
                    {t('settings.videoFileModeLibraryLink')}
                  </RouterLink>
                </Alert>
              </Grid>
            </Grid>
          </ServiceBlock>

          <ServiceBlock title={t('settings.serviceCameras')}>
            <Grid container spacing={2}>
              <form.Subscribe selector={(state) => state.values.video?.source}>
                {(videoSource) =>
                  (videoSource ?? 'go2rtc').toLowerCase() === 'file' ? (
                    <Grid size={{ xs: 12 }}>
                      <Alert severity="info" variant="outlined" sx={{ mb: 1 }}>
                        {t('settings.videoFileModeActiveHint')}{' '}
                        <RouterLink to="/library#file-replay">
                          {t('settings.videoFileModeLibraryLink')}
                        </RouterLink>
                      </Alert>
                    </Grid>
                  ) : null
                }
              </form.Subscribe>
              <Grid size={{ xs: 12 }}>
                <form.Field name="video.cameras">
                  {(field) => (
                    <CamerasListField
                      value={field.state.value}
                      onChange={field.handleChange}
                    />
                  )}
                </form.Field>
              </Grid>
            </Grid>
          </ServiceBlock>

          <ServiceBlock title={t('settings.serviceRecordingTransport')}>
            <Grid container spacing={2}>
              <Grid size={{ xs: 12, sm: 6 }}>
                <form.Field name="video.encoding">
                  {(field) => (
                    <FormControl fullWidth>
                      <InputLabel id="settings-encoding-label">
                        {t('settings.encodingLabel')}
                      </InputLabel>
                      <Select
                        labelId="settings-encoding-label"
                        value={(field.state.value ?? 'cpu').toLowerCase()}
                        label={t('settings.encodingLabel')}
                        onChange={(e) => field.handleChange(e.target.value)}
                      >
                        <MenuItem value="cpu">
                          {t('settings.encodingCpu')}
                        </MenuItem>
                        <MenuItem value="intel">
                          {t('settings.encodingIntel')}
                        </MenuItem>
                      </Select>
                      <FormHelperText>
                        {t('settings.encodingHint')}
                      </FormHelperText>
                    </FormControl>
                  )}
                </form.Field>
              </Grid>
              <Grid size={{ xs: 12, sm: 6 }}>
                <form.Field name="video.record_stream_codec">
                  {(field) => (
                    <FormControl fullWidth>
                      <InputLabel id="settings-record-codec-label">
                        {t('settings.recordStreamCodecLabel')}
                      </InputLabel>
                      <Select
                        labelId="settings-record-codec-label"
                        value={(field.state.value ?? 'h264').toLowerCase()}
                        label={t('settings.recordStreamCodecLabel')}
                        onChange={(e) =>
                          field.handleChange(e.target.value as 'h264' | 'copy')
                        }
                      >
                        <MenuItem value="h264">
                          {t('settings.recordStreamCodecH264')}
                        </MenuItem>
                        <MenuItem value="copy">
                          {t('settings.recordStreamCodecCopy')}
                        </MenuItem>
                      </Select>
                      <FormHelperText>
                        {t('settings.recordStreamCodecHint')}
                      </FormHelperText>
                    </FormControl>
                  )}
                </form.Field>
              </Grid>
              <Grid size={{ xs: 12, sm: 6 }}>
                <form.Field name="video.capture_backend">
                  {(field) => (
                    <FormControl fullWidth>
                      <InputLabel id="settings-capture-backend-label">
                        {t('settings.captureBackendLabel')}
                      </InputLabel>
                      <Select
                        labelId="settings-capture-backend-label"
                        value={(field.state.value ?? 'auto').toLowerCase()}
                        label={t('settings.captureBackendLabel')}
                        onChange={(e) => field.handleChange(e.target.value)}
                      >
                        <MenuItem value="auto">
                          {t('settings.captureBackendAuto')}
                        </MenuItem>
                        <MenuItem value="opencv">
                          {t('settings.captureBackendOpenCv')}
                        </MenuItem>
                        <MenuItem value="ffmpeg_vaapi">
                          {t('settings.captureBackendFfmpegVaapi')}
                        </MenuItem>
                      </Select>
                      <FormHelperText>
                        {t('settings.captureBackendHint')}
                      </FormHelperText>
                    </FormControl>
                  )}
                </form.Field>
              </Grid>
              <Grid size={{ xs: 12, sm: 6 }}>
                <form.Field name="video.pre_record_seconds">
                  {(field) => (
                    <TextField
                      fullWidth
                      type="number"
                      inputProps={{ min: 0, max: 30, step: 1 }}
                      value={field.state.value ?? 0}
                      onChange={(e) =>
                        field.handleChange(Number(e.target.value) || 0)
                      }
                      label={t('settings.videoPreRecordSeconds')}
                      helperText={t('settings.videoPreRecordSecondsHint')}
                    />
                  )}
                </form.Field>
              </Grid>
              <Grid size={{ xs: 12, sm: 6 }}>
                <form.Field name="video.auto_reconnect">
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
                        label={t('settings.videoAutoReconnect')}
                      />
                      <FormHelperText>
                        {t('settings.videoAutoReconnectHint')}
                      </FormHelperText>
                    </>
                  )}
                </form.Field>
              </Grid>
            </Grid>
          </ServiceBlock>
        </Box>
      </AccordionDetails>
    </Accordion>
  );
}
