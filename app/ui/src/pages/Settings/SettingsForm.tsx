import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { useForm } from '@tanstack/react-form';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Grid from '@mui/material/Grid2';
import Switch from '@mui/material/Switch';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';
import Checkbox from '@mui/material/Checkbox';
import { Settings } from '../../types';
import { fetchCoordinatesByZip, fetchVapidPublicKey, subscribePush, updateSettings, sendTestNotification } from '../../api/api';
import FormControlLabel from '@mui/material/FormControlLabel';
import FormControl from '@mui/material/FormControl';
import InputLabel from '@mui/material/InputLabel';
import ListItemText from '@mui/material/ListItemText';
import MenuItem from '@mui/material/MenuItem';
import Select from '@mui/material/Select';
import FormHelperText from '@mui/material/FormHelperText';
import Alert from '@mui/material/Alert';
import Accordion from '@mui/material/Accordion';
import AccordionSummary from '@mui/material/AccordionSummary';
import AccordionDetails from '@mui/material/AccordionDetails';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import Paper from '@mui/material/Paper';
import { PasswordField } from '../../components/PasswordField';

/** Блок настроек одного сервиса — подсветка и заголовок */
function ServiceBlock({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <Paper
      variant="outlined"
      sx={{
        p: 2,
        mb: 2,
        bgcolor: 'action.hover',
        '&:last-of-type': { mb: 0 },
      }}
    >
      <Typography variant="subtitle2" color="primary" sx={{ mb: 1.5, fontWeight: 600 }}>
        {title}
      </Typography>
      {children}
    </Paper>
  );
}

type CameraRow = { stream_name?: string; name?: string };

function urlBase64ToUint8Array(base64: string): Uint8Array {
  const padding = '='.repeat((4 - (base64.length % 4)) % 4);
  const b64 = (base64 + padding).replace(/-/g, '+').replace(/_/g, '/');
  const raw = atob(b64);
  const arr = new Uint8Array(raw.length);
  for (let i = 0; i < raw.length; i++) arr[i] = raw.charCodeAt(i);
  return arr;
}

function WebPushSubscribeButton({ notificationsEnabled }: { notificationsEnabled: boolean }) {
  const { t } = useTranslation();
  const [status, setStatus] = useState<'idle' | 'loading' | 'subscribed' | 'error'>('idle');
  const [errorMsg, setErrorMsg] = useState<string>('');

  const handleSubscribe = async () => {
    if (!notificationsEnabled) return;
    if (!('Notification' in window) || !('PushManager' in window) || !('serviceWorker' in navigator)) {
      setErrorMsg(t('settings.webPushUnsupported'));
      setStatus('error');
      return;
    }
    if (typeof window !== 'undefined' && !window.isSecureContext && !window.location.hostname.includes('localhost')) {
      setErrorMsg(t('settings.webPushUnsupported'));
      setStatus('error');
      return;
    }
    setStatus('loading');
    setErrorMsg('');
    try {
      const perm = await Notification.requestPermission();
      if (perm !== 'granted') {
        setErrorMsg('Permission denied');
        setStatus('error');
        return;
      }
      // Сохраняем enable_notifications на сервере до запроса ключа,
      // иначе vapid-public/subscribe могут вернуть «not available» / «Notifications disabled»
      await updateSettings({ general: { enable_notifications: true } });
      const reg = await navigator.serviceWorker.ready;
      const vapidKey = await fetchVapidPublicKey();
      const sub = await reg.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: urlBase64ToUint8Array(vapidKey),
      });
      await subscribePush(sub);
      setStatus('subscribed');
    } catch (e) {
      const err = e as { message?: string; response?: { data?: { error?: string } } };
      const msg = err.response?.data?.error || (err instanceof Error ? err.message : 'Failed');
      setErrorMsg(msg);
      setStatus('error');
    }
  };

  const supported = typeof window !== 'undefined' && 'Notification' in window && 'PushManager' in window && 'serviceWorker' in navigator;
  const isSecure = typeof window !== 'undefined' && (window.isSecureContext || window.location.hostname === 'localhost');

  if (!supported || !isSecure) {
    return (
      <Typography variant="body2" color="text.secondary">
        {t('settings.webPushUnsupported')}
      </Typography>
    );
  }

  return (
    <Box>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
        {t('settings.webPushDesc')}
      </Typography>
      <Button
        variant="outlined"
        onClick={handleSubscribe}
        disabled={!notificationsEnabled || status === 'loading'}
      >
        {status === 'loading' ? '...' : status === 'subscribed' ? t('settings.webPushSubscribed') : t('settings.webPushSubscribe')}
      </Button>
      {errorMsg && (
        <Typography variant="body2" color="error" sx={{ mt: 1 }}>
          {errorMsg}
        </Typography>
      )}
    </Box>
  );
}

function TestTelegramButton({ notificationsEnabled }: { notificationsEnabled: boolean }) {
  const { t } = useTranslation();
  const [status, setStatus] = useState<'idle' | 'loading' | 'success' | 'error'>('idle');
  const [msg, setMsg] = useState<string>('');

  const handleTest = async () => {
    if (!notificationsEnabled) return;
    setStatus('loading');
    setMsg('');
    const result = await sendTestNotification();
    setStatus(result.success ? 'success' : 'error');
    setMsg(result.message || '');
  };

  return (
    <Box>
      <Button
        variant="outlined"
        size="small"
        onClick={handleTest}
        disabled={!notificationsEnabled || status === 'loading'}
      >
        {status === 'loading' ? '...' : t('settings.testTelegram')}
      </Button>
      {msg && (
        <Typography variant="body2" color={status === 'success' ? 'text.secondary' : 'error'} sx={{ mt: 0.5, ml: 1, display: 'inline' }}>
          {msg}
        </Typography>
      )}
    </Box>
  );
}

function CamerasListField({
  value,
  onChange,
}: {
  value: Array<{ id?: string; stream_name?: string; name?: string }> | undefined;
  onChange: (v: Array<{ id?: string; stream_name?: string; name?: string }>) => void;
}) {
  const rows: CameraRow[] = Array.isArray(value) && value.length > 0
    ? value.map((c) => ({
        stream_name: c.stream_name ?? c.id ?? '',
        name: c.name ?? c.id ?? c.stream_name ?? '',
      }))
    : [{ stream_name: '', name: '' }];

  const sync = (newRows: CameraRow[]) => {
    const arr = newRows.map((r) => ({
      id: (r.stream_name ?? '').trim() || undefined,
      stream_name: (r.stream_name ?? '').trim(),
      name: (r.name ?? '').trim() || (r.stream_name ?? '').trim(),
    }));
    onChange(arr);
  };

  const updateRow = (i: number, field: keyof CameraRow, val: string) => {
    const next = [...rows];
    if (!next[i]) next[i] = { stream_name: '', name: '' };
    next[i] = { ...next[i], [field]: val };
    sync(next);
  };

  const addRow = () => {
    sync([...rows, { stream_name: '', name: '' }]);
  };

  const removeRow = (i: number) => {
    const next = rows.filter((_, idx) => idx !== i);
    sync(next.length ? next : [{ stream_name: '', name: '' }]);
  };

  const { t } = useTranslation();
  return (
    <Box>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
        {t('settings.streamNameHint')}
      </Typography>
      {rows.map((row, i) => (
        <Grid container key={i} spacing={1} sx={{ mb: 1 }} alignItems="center">
          <Grid size={{ xs: 12, sm: 6 }}>
            <TextField
              fullWidth
              size="small"
              value={row.stream_name ?? ''}
              onChange={(e) => updateRow(i, 'stream_name', e.target.value)}
              label={t('settings.streamName')}
              placeholder="BirdBox"
            />
          </Grid>
          <Grid size={{ xs: 12, sm: 5 }}>
            <TextField
              fullWidth
              size="small"
              value={row.name ?? ''}
              onChange={(e) => updateRow(i, 'name', e.target.value)}
              label={t('settings.cameraName')}
              placeholder={t('settings.cameraPlaceholder')}
            />
          </Grid>
          <Grid size={{ xs: 12, sm: 1 }}>
            <Button
              size="small"
              color="error"
              onClick={() => removeRow(i)}
              disabled={rows.length <= 1}
            >
              −
            </Button>
          </Grid>
        </Grid>
      ))}
      <Button size="small" onClick={addRow} sx={{ mt: 0.5 }}>
        {t('settings.addCamera')}
      </Button>
    </Box>
  );
}

export const SettingsForm = ({
  currentSettings,
  observedSpecies,
  onSubmit,
}: {
  currentSettings: Settings;
  observedSpecies: Array<{ id: number; name: string; count: number }>;
  onSubmit: (settings: Settings) => void;
}) => {
  const { t } = useTranslation();
  const form = useForm<Settings>({
    defaultValues: currentSettings,
    onSubmit: ({ value }) => onSubmit(value),
  });

  const handleZipLookup = async () => {
    const zip = form.getFieldValue('secrets.zip');
    if (!zip) return;
    try {
      const { lat, lon } = await fetchCoordinatesByZip(zip);
      form.setFieldValue('secrets.latitude', lat);
      form.setFieldValue('secrets.longitude', lon);
    } catch (error) {
      console.log(error);
      alert(t('settings.zipFetchFailed'));
    }
  };

  const resolutions = [
    { label: t('settings.resolutionFullHD'), width: 1920, height: 1080 },
    { label: t('settings.resolutionHD'), width: 1280, height: 720 },
    { label: t('settings.resolutionVGA'), width: 640, height: 480 },
  ];

  return (
    <Box
      component="form"
      noValidate
      autoComplete="off"
      onSubmit={(e) => {
        e.preventDefault();
        e.stopPropagation();
        form.handleSubmit();
      }}
    >
      {/* ========== 1. ПОДКЛЮЧЕНИЕ ========== */}
      <Accordion defaultExpanded>
        <AccordionSummary expandIcon={<ExpandMoreIcon />}>
          {t('settings.accordionConnection')}
        </AccordionSummary>
        <AccordionDetails>
          <Box
            component="fieldset"
            sx={{ border: 'none', p: 0, m: 0, minWidth: 0 }}
          >
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
              <TextField fullWidth value={field.state.value ?? ''} onChange={(e) => field.handleChange(e.target.value)} label={t('settings.go2rtcUser')} />
            )}
          </form.Field>
        </Grid>
        <Grid size={{ xs: 12, sm: 6 }}>
          <form.Field name="video.go2rtc_password">
            {(field) => (
              <PasswordField value={field.state.value ?? ''} onChange={(v) => field.handleChange(v)} label={t('settings.go2rtcPassword')} />
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
        <Grid size={{ xs: 12, sm: 6 }}>
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
        <Grid size={{ xs: 12, sm: 6 }}>
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

      {/* ========== 2. ДЕТЕКЦИЯ ДВИЖЕНИЯ ========== */}
      <Accordion>
        <AccordionSummary expandIcon={<ExpandMoreIcon />}>
          {t('settings.accordionMotion')}
        </AccordionSummary>
        <AccordionDetails>
          <Box
            component="fieldset"
            sx={{ border: 'none', p: 0, m: 0, minWidth: 0 }}
          >
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
                  onChange={(e) => field.handleChange(e.target.value === 'auto' ? 'frigate' : e.target.value)}
                >
                  <MenuItem value="auto">{t('settings.triggerFrigate')}</MenuItem>
                  <MenuItem value="opencv">{t('settings.triggerOpencv')}</MenuItem>
                  <MenuItem value="mqtt">{t('settings.triggerMqtt')}</MenuItem>
                  <MenuItem value="esphome">{t('settings.triggerEsp')}</MenuItem>
                </Select>
                <FormHelperText>
                  {t('settings.triggerHint')}
                </FormHelperText>
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
          <Box
            component="fieldset"
            sx={{ border: 'none', p: 0, m: 0, minWidth: 0 }}
          >
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
                            onChange={(e) => field.handleChange(e.target.value)}
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

      {/* ========== 4. УВЕДОМЛЕНИЯ ========== */}
      <Accordion>
        <AccordionSummary expandIcon={<ExpandMoreIcon />}>
          {t('settings.accordionNotifications')}
        </AccordionSummary>
        <AccordionDetails>
          <Box
            component="fieldset"
            sx={{ border: 'none', p: 0, m: 0, minWidth: 0 }}
          >
            <Box component="legend" sx={{ clip: 'rect(0,0,0,0)', position: 'absolute', width: 1, height: 1, overflow: 'hidden' }}>
              {t('settings.accordionNotifications')}
            </Box>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
              {t('settings.accordionNotificationsDesc')}
            </Typography>
          <ServiceBlock title={t('settings.serviceTelegram')}>
      <Grid container spacing={2}>
        <Grid size={{ xs: 12 }}>
          <form.Field name="general.enable_notifications">
            {(field) => (
              <FormControlLabel
                control={
                  <Switch
                    checked={field.state.value}
                    onChange={(e) => field.handleChange(e.target.checked)}
                  />
                }
                label={t('settings.notifications')}
              />
            )}
          </form.Field>
        </Grid>
        <form.Subscribe selector={(state) => [state.values.general?.enable_notifications]}>
          {([notificationsEnabled]) => (
            <>
              <Grid size={{ xs: 12 }}>
                <form.Field name="notifications.telegram_bot_token">
                  {(field) => (
                    <PasswordField
                      value={field.state.value ?? ''}
                      onChange={(v) => field.handleChange(v)}
                      label={t('settings.telegramBotToken')}
                      helperText={t('settings.telegramBotTokenHint')}
                      disabled={!notificationsEnabled}
                    />
                  )}
                </form.Field>
              </Grid>
              <Grid size={{ xs: 12 }}>
                <form.Field name="notifications.telegram_chat_id">
                  {(field) => (
                    <TextField
                      fullWidth
                      value={field.state.value ?? ''}
                      onChange={(e) => field.handleChange(e.target.value)}
                      label={t('settings.telegramChatId')}
                      helperText={t('settings.telegramChatIdHint')}
                      disabled={!notificationsEnabled}
                    />
                  )}
                </form.Field>
              </Grid>
              <Grid size={{ xs: 12 }}>
                <TestTelegramButton notificationsEnabled={!!notificationsEnabled} />
              </Grid>
              <Grid size={{ xs: 12 }}>
                <form.Field name="notifications.base_url">
                  {(field) => (
                    <TextField
                      fullWidth
                      value={field.state.value ?? ''}
                      onChange={(e) => field.handleChange(e.target.value)}
                      label={t('settings.notificationsBaseUrl')}
                      helperText={t('settings.notificationsBaseUrlHint')}
                      disabled={!notificationsEnabled}
                    />
                  )}
                </form.Field>
              </Grid>
              <Grid size={{ xs: 12, sm: 6 }}>
                <form.Field name="notifications.message_thread_id">
                  {(field) => (
                    <TextField
                      fullWidth
                      value={field.state.value ?? ''}
                      onChange={(e) => field.handleChange(e.target.value)}
                      label={t('settings.telegramThreadId')}
                      helperText={t('settings.telegramThreadIdHint')}
                      disabled={!notificationsEnabled}
                    />
                  )}
                </form.Field>
              </Grid>
              <Grid size={{ xs: 12, sm: 6 }}>
                <form.Field name="notifications.disable_notification">
                  {(field) => (
                    <FormControlLabel
                      control={
                        <Switch
                          checked={field.state.value ?? false}
                          onChange={(e) => field.handleChange(e.target.checked)}
                          disabled={!notificationsEnabled}
                        />
                      }
                      label={t('settings.telegramSilent')}
                    />
                  )}
                </form.Field>
              </Grid>
              <Grid size={{ xs: 12, sm: 6 }}>
                <form.Field name="notifications.protect_content">
                  {(field) => (
                    <FormControlLabel
                      control={
                        <Switch
                          checked={field.state.value ?? false}
                          onChange={(e) => field.handleChange(e.target.checked)}
                          disabled={!notificationsEnabled}
                        />
                      }
                      label={t('settings.telegramProtect')}
                    />
                  )}
                </form.Field>
              </Grid>
              <Grid size={{ xs: 12, sm: 6 }}>
                <form.Field name="notifications.link_preview_large">
                  {(field) => (
                    <FormControlLabel
                      control={
                        <Switch
                          checked={field.state.value ?? false}
                          onChange={(e) => field.handleChange(e.target.checked)}
                          disabled={!notificationsEnabled}
                        />
                      }
                      label={t('settings.telegramLinkPreviewLarge')}
                    />
                  )}
                </form.Field>
              </Grid>
              <Grid size={{ xs: 12, sm: 6 }}>
                <form.Field name="notifications.send_photo">
                  {(field) => (
                    <FormControlLabel
                      control={
                        <Switch
                          checked={field.state.value ?? true}
                          onChange={(e) => field.handleChange(e.target.checked)}
                          disabled={!notificationsEnabled}
                        />
                      }
                      label={t('settings.telegramSendPhoto')}
                    />
                  )}
                </form.Field>
              </Grid>
              <Grid size={{ xs: 12, sm: 6 }}>
                <form.Field name="notifications.use_custom_emoji">
                  {(field) => (
                    <FormControlLabel
                      control={
                        <Switch
                          checked={field.state.value ?? false}
                          onChange={(e) => field.handleChange(e.target.checked)}
                          disabled={!notificationsEnabled}
                        />
                      }
                      label={t('settings.telegramUseCustomEmoji')}
                    />
                  )}
                </form.Field>
              </Grid>
              <form.Subscribe
                selector={(state) => state.values.notifications?.use_custom_emoji}
              >
                {(useCustomEmoji) =>
                  useCustomEmoji ? (
                    <>
                      <Grid size={{ xs: 12, sm: 4 }}>
                        <form.Field name="notifications.custom_emoji_id_bird">
                          {(field) => (
                            <TextField
                              fullWidth
                              value={field.state.value ?? ''}
                              onChange={(e) => field.handleChange(e.target.value)}
                              label={t('settings.telegramCustomEmojiBird')}
                              helperText={t('settings.telegramCustomEmojiHint')}
                              disabled={!notificationsEnabled}
                            />
                          )}
                        </form.Field>
                      </Grid>
                      <Grid size={{ xs: 12, sm: 4 }}>
                        <form.Field name="notifications.custom_emoji_id_chipmunk">
                          {(field) => (
                            <TextField
                              fullWidth
                              value={field.state.value ?? ''}
                              onChange={(e) => field.handleChange(e.target.value)}
                              label={t('settings.telegramCustomEmojiChipmunk')}
                              helperText={t('settings.telegramCustomEmojiHint')}
                              disabled={!notificationsEnabled}
                            />
                          )}
                        </form.Field>
                      </Grid>
                      <Grid size={{ xs: 12, sm: 4 }}>
                        <form.Field name="notifications.custom_emoji_id_open_live">
                          {(field) => (
                            <TextField
                              fullWidth
                              value={field.state.value ?? ''}
                              onChange={(e) => field.handleChange(e.target.value)}
                              label={t('settings.telegramCustomEmojiOpenLive')}
                              helperText={t('settings.telegramCustomEmojiHint')}
                              disabled={!notificationsEnabled}
                            />
                          )}
                        </form.Field>
                      </Grid>
                    </>
                  ) : null
                }
              </form.Subscribe>
              <Grid size={{ xs: 12, sm: 6 }}>
                <form.Field name="notifications.paid_media_view_star_count">
                  {(field) => (
                    <TextField
                      fullWidth
                      type="number"
                      inputProps={{ min: 0, max: 25000 }}
                      value={field.state.value ?? 0}
                      onChange={(e) =>
                        field.handleChange(
                          Math.max(0, Math.min(25000, Number(e.target.value) || 0))
                        )
                      }
                      label={t('settings.paidMediaViewStars')}
                      helperText={t('settings.paidMediaViewStarsHint')}
                      disabled={!notificationsEnabled}
                    />
                  )}
                </form.Field>
              </Grid>
              <Grid size={{ xs: 12, sm: 6 }}>
                <form.Field name="notifications.paid_media_forward_star_count">
                  {(field) => (
                    <TextField
                      fullWidth
                      type="number"
                      inputProps={{ min: 0, max: 25000 }}
                      value={field.state.value ?? 0}
                      onChange={(e) =>
                        field.handleChange(
                          Math.max(0, Math.min(25000, Number(e.target.value) || 0))
                        )
                      }
                      label={t('settings.paidMediaForwardStars')}
                      helperText={t('settings.paidMediaForwardStarsHint')}
                      disabled={!notificationsEnabled}
                    />
                  )}
                </form.Field>
              </Grid>
              <Grid size={{ xs: 12 }}>
                <form.Field name="general.notification_excluded_species">
                  {(field) => (
                    <FormControl fullWidth disabled={!notificationsEnabled}>
                      <InputLabel id="settings-exclude-species-label">{t('settings.excludeSpecies')}</InputLabel>
                      <Select
                        labelId="settings-exclude-species-label"
                        multiple
                        value={field.state.value || []}
                        onChange={(e) => field.handleChange(e.target.value as string[])}
                        label={t('settings.excludeSpecies')}
                        renderValue={(selected) => selected.join(', ')}
                      >
                        {(observedSpecies ?? []).map((species) => (
                          <MenuItem key={species.id} value={species.name}>
                            <Checkbox checked={(field.state.value || []).includes(species.name)} />
                            <ListItemText primary={species.name} secondary={t('settings.foundCount', { count: species.count })} />
                          </MenuItem>
                        ))}
                      </Select>
                    </FormControl>
                  )}
                </form.Field>
              </Grid>
            </>
          )}
        </form.Subscribe>
          </Grid>
          </ServiceBlock>

          <ServiceBlock title={t('settings.serviceWebhook')}>
            <Grid container spacing={2}>
        <Grid size={{ xs: 12 }}>
          <form.Field name="webhook.url">
            {(field) => (
              <TextField
                fullWidth
                value={field.state.value ?? ''}
                onChange={(e) => field.handleChange(e.target.value)}
                label={t('settings.webhookUrl')}
                helperText={t('settings.webhookUrlHint')}
                placeholder="https://maker.ifttt.com/trigger/bird_detected/with/key/xxx"
              />
            )}
          </form.Field>
        </Grid>
            </Grid>
          </ServiceBlock>

          <ServiceBlock title={t('settings.serviceGallery')}>
            <Grid container spacing={2}>
        <Grid size={{ xs: 12 }}>
          <form.Field name="gallery.enabled">
            {(field) => (
              <FormControlLabel
                control={
                  <Switch
                    checked={field.state.value ?? false}
                    onChange={(e) => field.handleChange(e.target.checked)}
                  />
                }
                label={t('settings.galleryEnabled')}
              />
            )}
          </form.Field>
        </Grid>
        <form.Subscribe selector={(state) => state.values.gallery?.enabled}>
          {(enabled) => (
            <>
              {enabled && (
                <>
                  <Grid size={{ xs: 12 }}>
                    <form.Field name="gallery.upload_url">
                      {(field) => (
                        <TextField
                          fullWidth
                          value={field.state.value ?? ''}
                          onChange={(e) => field.handleChange(e.target.value)}
                          label={t('settings.galleryUploadUrl')}
                          helperText={t('settings.galleryUploadUrlHint')}
                          placeholder="https://gallery.example.com/api/upload"
                        />
                      )}
                    </form.Field>
                  </Grid>
                  <Grid size={{ xs: 12, sm: 6 }}>
                    <form.Field name="gallery.min_confidence">
                      {(field) => (
                        <TextField
                          fullWidth
                          type="number"
                          inputProps={{ min: 0, max: 1, step: 0.05 }}
                          value={field.state.value ?? 0.5}
                          onChange={(e) => field.handleChange(parseFloat(e.target.value) || 0.5)}
                          label={t('settings.galleryMinConfidence')}
                          helperText={t('settings.galleryMinConfidenceHint')}
                        />
                      )}
                    </form.Field>
                  </Grid>
                  <Grid size={{ xs: 12 }}>
                    <form.Field name="gallery.only_manually_corrected">
                      {(field) => (
                        <FormControlLabel
                          control={
                            <Checkbox
                              checked={field.state.value ?? false}
                              onChange={(e) => field.handleChange(e.target.checked)}
                            />
                          }
                          label={t('settings.galleryOnlyCorrected')}
                        />
                      )}
                    </form.Field>
                  </Grid>
                </>
              )}
            </>
          )}
        </form.Subscribe>
            </Grid>
          </ServiceBlock>

          <form.Subscribe selector={(state) => state.values.general?.enable_notifications}>
            {(notificationsEnabled) => (
              <Box sx={{ mt: 2 }}>
                <WebPushSubscribeButton notificationsEnabled={!!notificationsEnabled} />
              </Box>
            )}
          </form.Subscribe>
          </Box>
        </AccordionDetails>
      </Accordion>

      {/* ========== 5. ПОГОДА ========== */}
      <Accordion>
        <AccordionSummary expandIcon={<ExpandMoreIcon />}>
          {t('settings.accordionWeather')}
        </AccordionSummary>
        <AccordionDetails>
          <Box
            component="fieldset"
            sx={{ border: 'none', p: 0, m: 0, minWidth: 0 }}
          >
            <Box component="legend" sx={{ clip: 'rect(0,0,0,0)', position: 'absolute', width: 1, height: 1, overflow: 'hidden' }}>
              {t('settings.accordionWeather')}
            </Box>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
              {t('settings.accordionWeatherDesc')}
            </Typography>
      <Grid container spacing={2}>
        <Grid size={{ xs: 12 }}>
          <form.Field name="weather.source">
            {(field) => (
              <FormControl fullWidth>
                <InputLabel id="settings-weather-source-label">{t('settings.weatherSource')}</InputLabel>
                <Select
                  labelId="settings-weather-source-label"
                  value={field.state.value ?? 'openweather'}
                  label={t('settings.weatherSource')}
                  onChange={(e) => field.handleChange(e.target.value)}
                >
                  <MenuItem value="openweather">{t('settings.weatherOpenWeather')}</MenuItem>
                  <MenuItem value="homeassistant">{t('settings.weatherHomeAssistant')}</MenuItem>
                </Select>
              </FormControl>
            )}
          </form.Field>
        </Grid>
        <form.Subscribe selector={(state) => state.values.weather?.source}>
          {(source) => (
            <>
              {source !== 'homeassistant' && (
                <>
                  <Grid size={{ xs: 12 }}>
                    <form.Field name="secrets.openweather_api_key">
                      {(field) => (
                        <PasswordField
                          value={field.state.value ?? ''}
                          onChange={(v) => field.handleChange(v)}
                          label={t('settings.openWeatherApiKey')}
                          helperText={t('settings.weatherHint')}
                        />
                      )}
                    </form.Field>
                  </Grid>
                  <Grid size={{ xs: 6 }}>
                    <form.Field name="secrets.zip">
                      {(field) => (
                        <TextField fullWidth value={field.state.value ?? ''} onChange={(e) => field.handleChange(e.target.value)} label={t('settings.zip')} />
                      )}
                    </form.Field>
                  </Grid>
                  <Grid size={{ xs: 6 }}>
                    <Button fullWidth variant="outlined" onClick={handleZipLookup}>
                      {t('settings.zipLookup')}
                    </Button>
                  </Grid>
                  <Grid size={{ xs: 6 }}>
                    <form.Field name="secrets.latitude">
                      {(field) => (
                        <TextField
                          fullWidth
                          value={field.state.value ?? ''}
                          onChange={(e) => field.handleChange((e.target.value ?? '').replace(',', '.'))}
                          label={t('settings.latitude')}
                          helperText={t('settings.latitudeHint')}
                        />
                      )}
                    </form.Field>
                  </Grid>
                  <Grid size={{ xs: 6 }}>
                    <form.Field name="secrets.longitude">
                      {(field) => (
                        <TextField
                          fullWidth
                          value={field.state.value ?? ''}
                          onChange={(e) => field.handleChange((e.target.value ?? '').replace(',', '.'))}
                          label={t('settings.longitude')}
                          helperText={t('settings.longitudeHint')}
                        />
                      )}
                    </form.Field>
                  </Grid>
                </>
              )}
              {source === 'homeassistant' && (
                <>
                  <Grid size={{ xs: 12 }}>
                    <Alert severity="info" sx={{ mb: 2 }}>
                      {t('settings.weatherHaAlert')}
                    </Alert>
                  </Grid>
                  <Grid size={{ xs: 12 }}>
                    <form.Field name="weather.ha_url">
                      {(field) => (
                        <TextField
                          fullWidth
                          value={field.state.value ?? ''}
                          onChange={(e) => field.handleChange(e.target.value)}
                          label={t('settings.weatherHaUrl')}
                          placeholder="http://homeassistant:8123"
                          helperText={t('settings.weatherHaUrlHint')}
                        />
                      )}
                    </form.Field>
                  </Grid>
                  <Grid size={{ xs: 12, sm: 6 }}>
                    <form.Field name="weather.ha_entity_id">
                      {(field) => (
                        <TextField
                          fullWidth
                          value={field.state.value ?? ''}
                          onChange={(e) => field.handleChange(e.target.value)}
                          label={t('settings.weatherHaEntity')}
                          placeholder="weather.home"
                          helperText={t('settings.weatherHaEntityHint')}
                        />
                      )}
                    </form.Field>
                  </Grid>
                  <Grid size={{ xs: 12, sm: 6 }}>
                    <form.Field name="weather.ha_token">
                      {(field) => (
                        <PasswordField
                          value={field.state.value ?? ''}
                          onChange={(v) => field.handleChange(v)}
                          label={t('settings.weatherHaToken')}
                          placeholder={t('settings.weatherHaTokenPlaceholder')}
                          helperText={t('settings.weatherHaTokenHint')}
                        />
                      )}
                    </form.Field>
                  </Grid>
                </>
              )}
            </>
          )}
        </form.Subscribe>
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
          <Box
            component="fieldset"
            sx={{ border: 'none', p: 0, m: 0, minWidth: 0 }}
          >
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

      {/* ========== 7. ИНТЕГРАЦИИ ========== */}
      <Accordion>
        <AccordionSummary expandIcon={<ExpandMoreIcon />}>
          {t('settings.accordionIntegrations')}
        </AccordionSummary>
        <AccordionDetails>
          <Box
            component="fieldset"
            sx={{ border: 'none', p: 0, m: 0, minWidth: 0 }}
          >
            <Box component="legend" sx={{ clip: 'rect(0,0,0,0)', position: 'absolute', width: 1, height: 1, overflow: 'hidden' }}>
              {t('settings.accordionIntegrations')}
            </Box>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
              {t('settings.accordionIntegrationsDesc')}
            </Typography>

          <ServiceBlock title={t('settings.serviceXenoCanto')}>
            <Grid container spacing={2}>
        <Grid size={{ xs: 12 }}>
          <form.Field name="secrets.xeno_canto_api_key">
            {(field) => (
              <PasswordField
                value={field.state.value ?? ''}
                onChange={(v) => field.handleChange(v)}
                label={t('settings.xenoCantoApiKey')}
                helperText={t('settings.xenoCantoApiKeyHint')}
              />
            )}
          </form.Field>
        </Grid>
            </Grid>
          </ServiceBlock>

          <ServiceBlock title={t('settings.serviceEbird')}>
            <Grid container spacing={2}>
        <Grid size={{ xs: 12 }}>
          <form.Field name="secrets.ebird_api_key">
            {(field) => (
              <PasswordField
                value={field.state.value ?? ''}
                onChange={(v) => field.handleChange(v)}
                label={t('settings.ebirdApiKey')}
                helperText={t('settings.ebirdApiKeyHint')}
              />
            )}
          </form.Field>
        </Grid>
        <Grid size={{ xs: 12 }}>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                {t('settings.ebirdSection')}
              </Typography>
              <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
                <form.Field name="ebird.country">
                  {(field) => (
                    <TextField
                      sx={{ minWidth: 100, flex: 1 }}
                      size="small"
                      value={field.state.value ?? ''}
                      onChange={(e) => field.handleChange(e.target.value)}
                      label={t('settings.ebirdCountry')}
                      placeholder="US"
                      helperText={t('settings.ebirdCountryHint')}
                    />
                  )}
                </form.Field>
                <form.Field name="ebird.state">
                  {(field) => (
                    <TextField
                      sx={{ minWidth: 100, flex: 1 }}
                      size="small"
                      value={field.state.value ?? ''}
                      onChange={(e) => field.handleChange(e.target.value)}
                      label={t('settings.ebirdState')}
                      placeholder="NY"
                      helperText={t('settings.ebirdStateHint')}
                    />
                  )}
                </form.Field>
              </Box>
            </Grid>
            <Grid size={{ xs: 12 }}>
              <form.Field name="ebird.location_name">
                {(field) => (
                  <TextField
                    fullWidth
                    value={field.state.value ?? ''}
                    onChange={(e) => field.handleChange(e.target.value)}
                    label={t('settings.ebirdLocation')}
                    helperText={t('settings.ebirdLocationHint')}
                  />
                )}
              </form.Field>
            </Grid>
            <Grid size={{ xs: 12 }}>
              <form.Field name="ebird.species_mapping">
                {(field) => {
                  const val = field.state.value;
                  const str = val && typeof val === 'object' && !Array.isArray(val)
                    ? Object.entries(val).map(([k, v]) => `${k}: ${v}`).join('\n')
                    : '';
                  return (
                    <TextField
                      fullWidth
                      multiline
                      minRows={2}
                      value={str}
                      onChange={(e) => {
                        const lines = e.target.value.split('\n').filter(Boolean);
                        const obj: Record<string, string> = {};
                        for (const line of lines) {
                          const idx = line.indexOf(':');
                          if (idx > 0) {
                            const k = line.slice(0, idx).trim();
                            const v = line.slice(idx + 1).trim();
                            if (k && v) obj[k] = v;
                          }
                        }
                        field.handleChange(Object.keys(obj).length ? obj : {});
                      }}
                      label={t('settings.ebirdSpeciesMapping')}
                      placeholder="Gray-headed Woodpecker: Grey-headed Woodpecker"
                      helperText={t('settings.ebirdSpeciesMappingHint')}
                    />
                  );
                }}
              </form.Field>
            </Grid>
            </Grid>
          </ServiceBlock>

          <ServiceBlock title="MCP">
            <Grid container spacing={2}>
        <Grid size={{ xs: 12 }}>
          <form.Field name="mcp.enabled">
            {(field) => (
              <>
                <FormControlLabel
                  control={
                    <Switch
                      checked={field.state.value ?? false}
                      onChange={(e) => field.handleChange(e.target.checked)}
                    />
                  }
                  label={t('settings.mcpEnabled')}
                />
                <FormHelperText>{t('settings.mcpHint')}</FormHelperText>
              </>
            )}
          </form.Field>
        </Grid>
        <Grid size={{ xs: 12, sm: 6 }}>
          <form.Field name="mcp.token">
            {(field) => (
              <PasswordField
                value={field.state.value ?? ''}
                onChange={(v) => field.handleChange(v)}
                label={t('settings.mcpToken')}
                placeholder={t('settings.mcpTokenPlaceholder')}
                helperText={t('settings.mcpTokenHint')}
              />
            )}
          </form.Field>
        </Grid>
            </Grid>
          </ServiceBlock>
          </Box>
        </AccordionDetails>
      </Accordion>

      {/* ========== 8. ПРОЦЕССОР И ДЕТЕКЦИЯ ========== */}
      <Accordion>
        <AccordionSummary expandIcon={<ExpandMoreIcon />}>
          {t('settings.accordionProcessor')}
        </AccordionSummary>
        <AccordionDetails>
          <Box
            component="fieldset"
            sx={{ border: 'none', p: 0, m: 0, minWidth: 0 }}
          >
            <Box component="legend" sx={{ clip: 'rect(0,0,0,0)', position: 'absolute', width: 1, height: 1, overflow: 'hidden' }}>
              {t('settings.accordionProcessor')}
            </Box>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
              {t('settings.accordionProcessorDesc')}
            </Typography>

          <ServiceBlock title={t('settings.confidenceThresholdsTitle')}>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
              {t('settings.confidenceThresholdsDesc')}
            </Typography>
            <Grid container spacing={2}>
            <Grid size={{ xs: 12, sm: 4 }}>
              <form.Field name="processor.min_confidence_binary">
                {(field) => (
                  <TextField
                    fullWidth
                    type="number"
                    inputProps={{ min: 0.05, max: 0.9, step: 0.05 }}
                    value={field.state.value ?? 0.15}
                    onChange={(e) =>
                      field.handleChange(Number(e.target.value) || undefined)
                    }
                    label={t('settings.confidenceDetector')}
                    helperText={t('settings.confidenceDetectorHelp')}
                  />
                )}
              </form.Field>
            </Grid>
            <Grid size={{ xs: 12, sm: 4 }}>
              <form.Field name="processor.min_confidence_to_process">
                {(field) => (
                  <TextField
                    fullWidth
                    type="number"
                    inputProps={{ min: 0, max: 1, step: 0.05 }}
                    value={field.state.value ?? 0.30}
                    onChange={(e) =>
                      field.handleChange(Number(e.target.value) || undefined)
                    }
                    label={t('settings.confidenceClassifier')}
                    helperText={t('settings.confidenceClassifierHelp')}
                  />
                )}
              </form.Field>
            </Grid>
            <Grid size={{ xs: 12, sm: 4 }}>
              <form.Field name="processor.dataset_min_confidence">
                {(field) => (
                  <TextField
                    fullWidth
                    type="number"
                    inputProps={{ min: 0, max: 1, step: 0.05 }}
                    value={field.state.value ?? 0.50}
                    onChange={(e) =>
                      field.handleChange(Number(e.target.value) || undefined)
                    }
                    label={t('settings.confidenceDataset')}
                    helperText={t('settings.confidenceDatasetHelp')}
                  />
                )}
              </form.Field>
            </Grid>
            </Grid>
          </ServiceBlock>

          <ServiceBlock title={t('settings.serviceProcessor')}>
            <Grid container spacing={2}>
            <Grid size={{ xs: 12, sm: 6 }}>
              <form.Field name="processor.max_record_seconds">
                {(field) => (
                  <TextField
                    fullWidth
                    type="number"
                    value={field.state.value ?? 60}
                    onChange={(e) => field.handleChange(Number(e.target.value))}
                    label={t('settings.maxRecordSeconds')}
                  />
                )}
              </form.Field>
            </Grid>
            <Grid size={{ xs: 12, sm: 6 }}>
              <form.Field name="processor.max_inactive_seconds">
                {(field) => (
                  <TextField
                    fullWidth
                    type="number"
                    value={field.state.value ?? 10}
                    onChange={(e) => field.handleChange(Number(e.target.value))}
                    label={t('settings.inactiveSeconds')}
                  />
                )}
              </form.Field>
            </Grid>
            <Grid size={{ xs: 12, sm: 6 }}>
              <form.Field name="processor.min_track_duration">
                {(field) => (
                  <TextField
                    fullWidth
                    type="number"
                    value={field.state.value ?? 3}
                    onChange={(e) => field.handleChange(Number(e.target.value))}
                    label={t('settings.minTrackDuration')}
                    helperText={t('settings.minTrackDurationHelp')}
                  />
                )}
              </form.Field>
            </Grid>
            </Grid>
          </ServiceBlock>

          <ServiceBlock title={t('settings.confidenceAdvanced')}>
            <Grid container spacing={2}>
            <Grid size={{ xs: 12 }}>
              <form.Field name="processor.species_confidence_overrides">
                {(field) => {
                  const val = field.state.value;
                  const str = val && typeof val === 'object' && !Array.isArray(val)
                    ? Object.entries(val).map(([k, v]) => `${k}: ${v}`).join('\n')
                    : '';
                  return (
                    <TextField
                      fullWidth
                      multiline
                      minRows={2}
                      value={str}
                      onChange={(e) => {
                        const lines = e.target.value.split('\n').filter(Boolean);
                        const obj: Record<string, number> = {};
                        for (const line of lines) {
                          const idx = line.indexOf(':');
                          if (idx > 0) {
                            const k = line.slice(0, idx).trim();
                            const v = parseFloat(line.slice(idx + 1).trim());
                            if (!isNaN(v) && v >= 0 && v <= 1) obj[k] = v;
                          }
                        }
                        field.handleChange(Object.keys(obj).length ? obj : {});
                      }}
                      label={t('settings.speciesConfidenceOverrides')}
                      placeholder="Pileated Woodpecker: 0.05"
                      helperText={t('settings.speciesConfidenceOverridesHint')}
                    />
                  );
                }}
              </form.Field>
            </Grid>
            <Grid size={{ xs: 12, sm: 6 }}>
              <form.Field name="ui.unknown_confidence_threshold">
                {(field) => (
                  <TextField
                    fullWidth
                    type="number"
                    inputProps={{ min: 0, max: 1, step: 0.05 }}
                    value={field.state.value ?? 0.5}
                    onChange={(e) =>
                      field.handleChange(Number(e.target.value) || undefined)
                    }
                    label={t('settings.unknownConfidenceThreshold')}
                    helperText={t('settings.unknownConfidenceThresholdHelp')}
                  />
                )}
              </form.Field>
            </Grid>
            </Grid>
          </ServiceBlock>

          <ServiceBlock title={t('settings.serviceProcessor')}>
            <Grid container spacing={2}>
            <Grid size={{ xs: 12, sm: 6 }}>
              <form.Field name="processor.spectrogram_px_per_sec">
                {(field) => (
                  <TextField
                    fullWidth
                    type="number"
                    value={field.state.value ?? 200}
                    onChange={(e) => field.handleChange(Number(e.target.value))}
                    label={t('settings.spectrogramDetail')}
                    helperText={t('settings.spectrogramDetailHelp')}
                  />
                )}
              </form.Field>
            </Grid>
            <Grid size={{ xs: 12, sm: 6 }}>
              <form.Field name="processor.tracker">
                {(field) => (
                  <TextField fullWidth value={field.state.value ?? ''} onChange={(e) => field.handleChange(e.target.value)} label={t('settings.objectTracker')} />
                )}
              </form.Field>
            </Grid>
            <Grid size={{ xs: 12, sm: 6 }}>
              <form.Field name="processor.save_dataset_crops">
                {(field) => (
                  <FormControl fullWidth>
                    <FormControlLabel
                      control={
                        <Checkbox
                          checked={!!field.state.value}
                          onChange={(e) => field.handleChange(e.target.checked)}
                        />
                      }
                      label={t('settings.saveDatasetCrops')}
                    />
                    <FormHelperText>{t('settings.saveDatasetCropsHelp')}</FormHelperText>
                  </FormControl>
                )}
              </form.Field>
            </Grid>
            </Grid>
          </ServiceBlock>

          <ServiceBlock title={t('settings.serviceFrigate')}>
            <Grid container spacing={2}>
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
            </Grid>
          </ServiceBlock>

          <ServiceBlock title={t('settings.serviceVideo')}>
            <Grid container spacing={2}>
            <Grid size={{ xs: 12 }}>
              <form.Field name="video.video_width">
                {(widthField) => (
                  <form.Field name="video.video_height">
                    {(heightField) => {
                      const w = widthField.state.value;
                      const h = heightField.state.value;
                      const sel = resolutions.find((r) => r.width === w && r.height === h);
                      return (
                        <FormControl fullWidth>
                          <InputLabel id="settings-resolution-label">{t('settings.resolution')}</InputLabel>
                          <Select
                            labelId="settings-resolution-label"
                            value={sel ? `${sel.width}x${sel.height}` : ''}
                            label={t('settings.resolution')}
                            onChange={(e) => {
                              const [a, b] = (e.target.value as string).split('x').map(Number);
                              widthField.handleChange(a);
                              heightField.handleChange(b);
                            }}
                          >
                            {resolutions.map((r) => (
                              <MenuItem key={r.label} value={`${r.width}x${r.height}`}>
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
          </Box>
        </AccordionDetails>
      </Accordion>

      <Button variant="contained" fullWidth type="submit" sx={{ mt: 4 }}>
        {t('settings.save')}
      </Button>
    </Box>
  );
};
