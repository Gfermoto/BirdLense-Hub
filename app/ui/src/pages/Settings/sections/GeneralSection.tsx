import { useTranslation } from 'react-i18next';
import type { ReactFormExtendedApi } from '@tanstack/react-form';
import Box from '@mui/material/Box';
import Grid from '@mui/material/Grid2';
import Switch from '@mui/material/Switch';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';
import FormControlLabel from '@mui/material/FormControlLabel';
import FormHelperText from '@mui/material/FormHelperText';
import MenuItem from '@mui/material/MenuItem';
import Select from '@mui/material/Select';
import InputLabel from '@mui/material/InputLabel';
import FormControl from '@mui/material/FormControl';
import Accordion from '@mui/material/Accordion';
import AccordionSummary from '@mui/material/AccordionSummary';
import AccordionDetails from '@mui/material/AccordionDetails';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import { PasswordField } from '../../../components/PasswordField';
import { ServiceBlock } from '../shared/ServiceBlock';
import { CamerasListField } from '../shared/CamerasListField';
import type { Settings } from '../../../types';

type Props = {
  form: ReactFormExtendedApi<Settings, undefined>;
};

export function GeneralSection({ form }: Props) {
  const { t } = useTranslation();

  return (
    <>
      {/* ========== 1. ПОДКЛЮЧЕНИЕ ========== */}
      <Accordion>
        <AccordionSummary expandIcon={<ExpandMoreIcon />}>
          {t('settings.accordionConnection')}
        </AccordionSummary>
        <AccordionDetails>
          <Box component="fieldset" sx={{ border: 'none', p: 0, m: 0, minWidth: 0 }}>
            <Box component="legend" sx={{ clip: 'rect(0,0,0,0)', position: 'absolute', width: 1, height: 1, overflow: 'hidden' }}>
              {t('settings.accordionConnection')}
            </Box>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
              {t('settings.accordionConnectionDesc')}
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
                        onChange={(e) => field.handleChange(Number(e.target.value) || 1883)}
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
                  <form.Field name="mqtt.frigate_topic">
                    {(field) => (
                      <TextField
                        fullWidth
                        value={field.state.value ?? 'frigate/events'}
                        onChange={(e) => field.handleChange(e.target.value)}
                        label={t('settings.frigateTopic')}
                        placeholder="frigate/events"
                        helperText={t('settings.frigateTopicHint')}
                      />
                    )}
                  </form.Field>
                </Grid>
                <Grid size={{ xs: 12, sm: 6 }}>
                  <form.Field name="mqtt.birdnet_topic">
                    {(field) => (
                      <TextField
                        fullWidth
                        value={field.state.value ?? 'birdnet'}
                        onChange={(e) => field.handleChange(e.target.value)}
                        label={t('settings.birdnetTopic')}
                        placeholder="birdnet"
                        helperText={t('settings.birdnetTopicHint')}
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
                        onChange={(e) => field.handleChange(Number(e.target.value) || 5)}
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
                        onChange={(e) => field.handleChange(Number(e.target.value) || 300)}
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
                              onChange={(e) => field.handleChange(e.target.checked)}
                            />
                          }
                          label={t('settings.mqttHaDiscovery')}
                        />
                        <FormHelperText>{t('settings.mqttHaDiscoveryHint')}</FormHelperText>
                      </>
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

            <ServiceBlock title={t('settings.serviceVideo')}>
              <Grid container spacing={2}>
                <Grid size={{ xs: 12, sm: 6 }}>
                  <form.Field name="video.encoding">
                    {(field) => (
                      <FormControl fullWidth>
                        <InputLabel id="settings-encoding-label">{t('settings.encodingLabel')}</InputLabel>
                        <Select
                          labelId="settings-encoding-label"
                          value={(field.state.value ?? 'cpu').toLowerCase()}
                          label={t('settings.encodingLabel')}
                          onChange={(e) => field.handleChange(e.target.value)}
                        >
                          <MenuItem value="cpu">{t('settings.encodingCpu')}</MenuItem>
                          <MenuItem value="intel">{t('settings.encodingIntel')}</MenuItem>
                        </Select>
                        <FormHelperText>{t('settings.encodingHint')}</FormHelperText>
                      </FormControl>
                    )}
                  </form.Field>
                </Grid>
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

            <ServiceBlock title={t('settings.serviceGeneral')}>
              <Grid container spacing={2}>
                <Grid size={{ xs: 12 }}>
                  <form.Field name="general.birdnet_url">
                    {(field) => (
                      <TextField
                        fullWidth
                        value={field.state.value ?? ''}
                        onChange={(e) => field.handleChange(e.target.value)}
                        label={t('settings.birdnetUrl')}
                        placeholder="http://birdnet.local"
                        helperText={t('settings.birdnetUrlHint')}
                      />
                    )}
                  </form.Field>
                </Grid>
                <Grid size={{ xs: 12 }}>
                  <form.Field name="general.heimdall_url">
                    {(field) => (
                      <TextField
                        fullWidth
                        value={field.state.value ?? ''}
                        onChange={(e) => field.handleChange(e.target.value)}
                        label={t('settings.heimdallUrl')}
                        placeholder="http://heimdall.local"
                        helperText={t('settings.heimdallUrlHint')}
                      />
                    )}
                  </form.Field>
                </Grid>
                <Grid size={{ xs: 12 }}>
                  <form.Field name="general.donate_url">
                    {(field) => (
                      <TextField
                        fullWidth
                        value={field.state.value ?? ''}
                        onChange={(e) => field.handleChange(e.target.value)}
                        label={t('settings.donateUrl')}
                        placeholder="https://ko-fi.com/..."
                        helperText={t('settings.donateUrlHint')}
                      />
                    )}
                  </form.Field>
                </Grid>
              </Grid>
            </ServiceBlock>
          </Box>
        </AccordionDetails>
      </Accordion>

      {/* ========== Производительность / Redis ========== */}
      <Accordion>
        <AccordionSummary expandIcon={<ExpandMoreIcon />}>
          {t('settings.accordionPerformance')}
        </AccordionSummary>
        <AccordionDetails>
          <Box component="fieldset" sx={{ border: 'none', p: 0, m: 0, minWidth: 0 }}>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
              {t('settings.accordionPerformanceDesc')}
            </Typography>
            <Grid container spacing={2}>
              <Grid size={{ xs: 12 }}>
                <form.Field name="performance.cache_redis_enabled">
                  {(field) => (
                    <FormControlLabel
                      control={
                        <Switch
                          checked={field.state.value !== false}
                          onChange={(e) => field.handleChange(e.target.checked)}
                        />
                      }
                      label={t('settings.performanceRedisEnabled')}
                    />
                  )}
                </form.Field>
                <FormHelperText sx={{ ml: 0, mt: 0.5 }}>
                  {t('settings.performanceRedisEnabledHint')}
                </FormHelperText>
              </Grid>
              <Grid size={{ xs: 12 }}>
                <form.Subscribe
                  selector={(s) => s.values.performance?.redis_url_effective_masked ?? ''}
                >
                  {(effectiveMasked) => (
                    <form.Field name="performance.redis_url">
                      {(field) => {
                        const raw = (field.state.value ?? '').trim();
                        const placeholder =
                          !raw && effectiveMasked
                            ? effectiveMasked
                            : 'redis://redis:6379/0';
                        return (
                          <TextField
                            fullWidth
                            value={field.state.value ?? ''}
                            onChange={(e) => field.handleChange(e.target.value)}
                            label={t('settings.performanceRedisUrl')}
                            placeholder={placeholder}
                            helperText={
                              <>
                                <Box component="span" display="block">
                                  {t('settings.performanceRedisUrlHint')}
                                </Box>
                                {effectiveMasked ? (
                                  <Box component="span" display="block" sx={{ mt: 0.5 }}>
                                    {t('settings.performanceRedisEffectiveNow', {
                                      url: effectiveMasked,
                                    })}
                                  </Box>
                                ) : null}
                              </>
                            }
                          />
                        );
                      }}
                    </form.Field>
                  )}
                </form.Subscribe>
              </Grid>
            </Grid>
          </Box>
        </AccordionDetails>
      </Accordion>

      {/* ========== 6. БЕЗОПАСНОСТЬ ========== */}
      <Accordion>
        <AccordionSummary expandIcon={<ExpandMoreIcon />}>
          {t('settings.accordionSecurity')}
        </AccordionSummary>
        <AccordionDetails>
          <Box component="fieldset" sx={{ border: 'none', p: 0, m: 0, minWidth: 0 }}>
            <Box component="legend" sx={{ clip: 'rect(0,0,0,0)', position: 'absolute', width: 1, height: 1, overflow: 'hidden' }}>
              {t('settings.accordionSecurity')}
            </Box>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
              {t('settings.accordionSecurityDesc')}
            </Typography>
            <Grid container spacing={2}>
              <Grid size={{ xs: 12, sm: 6 }}>
                <form.Field name="general.settings_password">
                  {(field) => (
                    <PasswordField
                      value={field.state.value ?? ''}
                      onChange={(v) => field.handleChange(v)}
                      label={t('settings.settingsPassword')}
                      placeholder={t('settings.settingsPasswordPlaceholder')}
                      helperText={t('settings.settingsPasswordHint')}
                    />
                  )}
                </form.Field>
              </Grid>
              <Grid size={{ xs: 12, sm: 6 }}>
                <form.Field name="general.contributor_password">
                  {(field) => (
                    <PasswordField
                      value={field.state.value ?? ''}
                      onChange={(v) => field.handleChange(v)}
                      label={t('settings.contributorPassword')}
                      placeholder={t('settings.contributorPasswordPlaceholder')}
                      helperText={t('settings.contributorPasswordHint')}
                    />
                  )}
                </form.Field>
              </Grid>
            </Grid>
          </Box>
        </AccordionDetails>
      </Accordion>
    </>
  );
}
